"""Backward-compatible API endpoints for existing integrations and tests."""
import datetime
from flask import Blueprint, request, jsonify, g

from db import get_db
from auth_utils import get_current_user, login_required
from services.sessions import sync_session_status, can_join_session, session_to_dict, sync_all_sessions

legacy_bp = Blueprint('legacy', __name__)


@legacy_bp.route('/api/courses/<int:course_id>/classes', methods=['GET'])
def list_classes(course_id):
    conn = get_db()
    sync_all_sessions(conn)
    conn.commit()
    rows = conn.execute(
        'SELECT id, title, session_date, start_time, end_time, status, meeting_link FROM sessions WHERE course_id=%s ORDER BY session_date, start_time',
        (course_id,)
    ).fetchall()
    conn.close()
    result = []
    for r in rows:
        s = session_to_dict(r)
        result.append({
            'id': s['id'],
            'title': s['title'],
            'start_time': f"{s['session_date']}T{s['start_time']}",
            'end_time': f"{s['session_date']}T{s['end_time']}",
            'status': s['effective_status'],
            'can_join': s['can_join'],
            'meeting_link': s.get('meeting_link'),
        })
    return jsonify(result)


@legacy_bp.route('/api/courses/<int:course_id>/classes', methods=['POST'])
def create_class(course_id):
    data = request.get_json() or {}
    start = data.get('start_time', '')
    end = data.get('end_time', '')
    session_date = start[:10] if start else datetime.datetime.utcnow().strftime('%Y-%m-%d')
    start_time = start[11:16] if len(start) > 10 else '09:00'
    if len(end) > 10:
        end_time = end[11:16]
    else:
        sh, sm = (int(x) for x in start_time.split(':'))
        end_time = f'{(sh + 1) % 24:02d}:{sm:02d}'

    user = get_current_user(optional=True)
    conn = get_db()
    course = conn.execute('SELECT * FROM courses WHERE id=%s', (course_id,)).fetchone()
    if not course:
        conn.close()
        return jsonify(error='Course not found'), 404
    instructor_id = course['instructor_id']
    if user and user['role'] in ('teacher', 'admin'):
        instructor_id = user['id'] if user['role'] == 'teacher' else instructor_id

    conn.execute(
        '''INSERT INTO sessions (course_id, title, description, instructor_id, session_date,
           start_time, end_time, meeting_link, status) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)''',
        (course_id, data.get('title', 'Class'), data.get('description', ''),
         instructor_id, session_date, start_time, end_time,
         data.get('meeting_link', f'https://meet.edustream.edu/{course_id}'), 'scheduled')
    )
    conn.commit()
    conn.close()
    return jsonify(message='Class scheduled'), 201


@legacy_bp.route('/api/classes/<int:class_id>/join', methods=['POST'])
def join_class_legacy(class_id):
    data = request.get_json() or {}
    user = get_current_user(optional=True)
    conn = get_db()
    sync_session_status(conn, class_id)
    row = conn.execute('SELECT * FROM sessions WHERE id=%s', (class_id,)).fetchone()
    if not row:
        conn.close()
        return jsonify(error='Class not found'), 404

    session = dict(row)
    allowed, reason = can_join_session(session)
    if not allowed:
        conn.close()
        return jsonify(error=reason), 403

    if user:
        student_id = user['id']
        student_name = user['name']
    else:
        student_name = data.get('name', 'Guest')
        guest = conn.execute('SELECT id FROM users WHERE email=%s', (f'{student_name.lower().replace(" ","")}@guest.local',)).fetchone()
        if not guest:
            conn.close()
            return jsonify(error='Authentication required to join sessions'), 401
        student_id = guest['id']

    now = datetime.datetime.utcnow().isoformat()
    existing = conn.execute(
        'SELECT id FROM attendance WHERE session_id=%s AND student_id=%s',
        (class_id, student_id)
    ).fetchone()
    if not existing:
        conn.execute(
            'INSERT INTO attendance (student_id, course_id, session_id, join_time, status) VALUES (%s,%s,%s,%s,%s)',
            (student_id, session['course_id'], class_id, now, 'present')
        )
    conn.execute("UPDATE sessions SET status='live' WHERE id=%s AND status='scheduled'", (class_id,))
    conn.commit()
    conn.close()
    return jsonify(message='Joined class'), 201
