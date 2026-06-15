import datetime
from flask import Blueprint, request, jsonify, g

from db import get_db
from auth_utils import login_required, roles_required
from services.sessions import (
    sync_all_sessions, sync_session_status, can_join_session,
    session_to_dict, combine_date_time,
)
from services.notifications import create_notification, notify_course_students

sessions_bp = Blueprint('sessions', __name__)


def _can_manage_session(conn, session_id, user):
    if user['role'] == 'admin':
        return True
    row = conn.execute('SELECT instructor_id, course_id FROM sessions WHERE id=%s', (session_id,)).fetchone()
    if not row:
        return False
    if user['role'] == 'teacher' and row['instructor_id'] == user['id']:
        return True
    course = conn.execute('SELECT instructor_id FROM courses WHERE id=%s', (row['course_id'],)).fetchone()
    return course and course['instructor_id'] == user['id']


def _is_enrolled(conn, course_id, student_id):
    return conn.execute(
        'SELECT id FROM enrollments WHERE course_id=%s AND student_id=%s',
        (course_id, student_id)
    ).fetchone() is not None


@sessions_bp.route('/api/courses/<int:course_id>/sessions', methods=['GET'])
def list_sessions(course_id):
    conn = get_db()
    sync_all_sessions(conn)
    conn.commit()
    rows = conn.execute('''
        SELECT s.*, u.name AS instructor_name
        FROM sessions s JOIN users u ON u.id = s.instructor_id
        WHERE s.course_id=%s ORDER BY s.session_date, s.start_time
    ''', (course_id,)).fetchall()
    conn.close()
    return jsonify([session_to_dict(r) for r in rows])


@sessions_bp.route('/api/courses/<int:course_id>/sessions', methods=['POST'])
@roles_required('admin', 'teacher')
def create_session(course_id):
    data = request.get_json() or {}
    title = (data.get('title') or '').strip()
    session_date = (data.get('session_date') or data.get('date') or '').strip()
    start_time = (data.get('start_time') or '').strip()
    end_time = (data.get('end_time') or '').strip()

    if not title or not session_date or not start_time or not end_time:
        return jsonify(error='Title, date, start time, and end time are required'), 400

    conn = get_db()
    course = conn.execute('SELECT * FROM courses WHERE id=%s', (course_id,)).fetchone()
    if not course:
        conn.close()
        return jsonify(error='Course not found'), 404

    instructor_id = g.user['id']
    if g.user['role'] == 'admin' and data.get('instructor_id'):
        instructor_id = data['instructor_id']
    elif g.user['role'] == 'teacher' and course['instructor_id'] != g.user['id']:
        conn.close()
        return jsonify(error='Insufficient permissions'), 403

    meeting_link = data.get('meeting_link') or f'https://meet.edustream.edu/session/{course_id}'
    conn.execute(
        '''INSERT INTO sessions (course_id, title, description, instructor_id, session_date,
           start_time, end_time, meeting_link, status) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)''',
        (course_id, title, data.get('description', ''), instructor_id, session_date[:10],
         start_time[:5], end_time[:5], meeting_link, 'scheduled')
    )
    conn.commit()
    session_id = conn.execute('SELECT LAST_INSERT_ID()').fetchone()['LAST_INSERT_ID()']
    notify_course_students(
        conn, course_id, 'session_reminder', f'New session: {title}',
        f'A new session "{title}" has been scheduled for {session_date[:10]}.',
        session_id, exclude_user_id=g.user['id']
    )
    conn.commit()
    row = conn.execute('SELECT s.*, u.name AS instructor_name FROM sessions s JOIN users u ON u.id = s.instructor_id WHERE s.id=%s', (session_id,)).fetchone()
    conn.close()
    return jsonify(session_to_dict(row)), 201


@sessions_bp.route('/api/sessions/<int:session_id>', methods=['GET'])
def get_session(session_id):
    conn = get_db()
    sync_session_status(conn, session_id)
    conn.commit()
    row = conn.execute('SELECT s.*, u.name AS instructor_name FROM sessions s JOIN users u ON u.id = s.instructor_id WHERE s.id=%s', (session_id,)).fetchone()
    conn.close()
    if not row:
        return jsonify(error='Session not found'), 404
    return jsonify(session_to_dict(row))


@sessions_bp.route('/api/sessions/<int:session_id>', methods=['PUT'])
@login_required
def update_session(session_id):
    conn = get_db()
    if not _can_manage_session(conn, session_id, g.user):
        conn.close()
        return jsonify(error='Insufficient permissions'), 403
    data = request.get_json() or {}
    fields = []
    values = []
    for key in ('title', 'description', 'session_date', 'start_time', 'end_time', 'meeting_link'):
        if key in data:
            val = data[key]
            if key == 'session_date':
                val = val[:10]
            elif key in ('start_time', 'end_time'):
                val = val[:5]
            fields.append(f'{key}=%s')
            values.append(val)
    if not fields:
        conn.close()
        return jsonify(error='No fields to update'), 400
    values.append(session_id)
    conn.execute(f'UPDATE sessions SET {", ".join(fields)} WHERE id=%s', values)
    conn.commit()
    row = conn.execute('SELECT s.*, u.name AS instructor_name FROM sessions s JOIN users u ON u.id = s.instructor_id WHERE s.id=%s', (session_id,)).fetchone()
    conn.close()
    return jsonify(session_to_dict(row))


@sessions_bp.route('/api/sessions/<int:session_id>', methods=['DELETE'])
@login_required
def delete_session(session_id):
    conn = get_db()
    if not _can_manage_session(conn, session_id, g.user):
        conn.close()
        return jsonify(error='Insufficient permissions'), 403
    conn.execute('DELETE FROM sessions WHERE id=%s', (session_id,))
    conn.commit()
    conn.close()
    return jsonify(message='Session deleted')


@sessions_bp.route('/api/sessions/<int:session_id>/cancel', methods=['POST'])
@login_required
def cancel_session(session_id):
    conn = get_db()
    if not _can_manage_session(conn, session_id, g.user):
        conn.close()
        return jsonify(error='Insufficient permissions'), 403
    row = conn.execute('SELECT * FROM sessions WHERE id=%s', (session_id,)).fetchone()
    if not row:
        conn.close()
        return jsonify(error='Session not found'), 404
    conn.execute("UPDATE sessions SET status='cancelled' WHERE id=%s", (session_id,))
    notify_course_students(
        conn, row['course_id'], 'session_cancelled', f'Session cancelled: {row["title"]}',
        f'The session "{row["title"]}" has been cancelled.', session_id
    )
    conn.commit()
    conn.close()
    return jsonify(message='Session cancelled')


@sessions_bp.route('/api/sessions/<int:session_id>/start', methods=['POST'])
@login_required
def start_session(session_id):
    conn = get_db()
    if not _can_manage_session(conn, session_id, g.user):
        conn.close()
        return jsonify(error='Insufficient permissions'), 403
    row = conn.execute('SELECT * FROM sessions WHERE id=%s', (session_id,)).fetchone()
    if not row:
        conn.close()
        return jsonify(error='Session not found'), 404
    conn.execute("UPDATE sessions SET status='live' WHERE id=%s", (session_id,))
    notify_course_students(
        conn, row['course_id'], 'session_live', f'Session live: {row["title"]}',
        f'"{row["title"]}" is now live. Join now!', session_id
    )
    conn.commit()
    row = conn.execute('SELECT s.*, u.name AS instructor_name FROM sessions s JOIN users u ON u.id = s.instructor_id WHERE s.id=%s', (session_id,)).fetchone()
    conn.close()
    return jsonify(session_to_dict(row))


@sessions_bp.route('/api/sessions/<int:session_id>/end', methods=['POST'])
@login_required
def end_session(session_id):
    conn = get_db()
    if not _can_manage_session(conn, session_id, g.user):
        conn.close()
        return jsonify(error='Insufficient permissions'), 403
    conn.execute("UPDATE sessions SET status='completed' WHERE id=%s", (session_id,))
    conn.commit()
    row = conn.execute('SELECT s.*, u.name AS instructor_name FROM sessions s JOIN users u ON u.id = s.instructor_id WHERE s.id=%s', (session_id,)).fetchone()
    conn.close()
    if not row:
        return jsonify(error='Session not found'), 404
    return jsonify(session_to_dict(row))


@sessions_bp.route('/api/sessions/<int:session_id>/join', methods=['POST'])
@login_required
def join_session(session_id):
    conn = get_db()
    sync_session_status(conn, session_id)
    row = conn.execute('SELECT * FROM sessions WHERE id=%s', (session_id,)).fetchone()
    if not row:
        conn.close()
        return jsonify(error='Session not found'), 404

    session = dict(row)
    allowed, reason = can_join_session(session)
    if not allowed:
        conn.close()
        return jsonify(error=reason), 403

    if g.user['role'] == 'student':
        if not _is_enrolled(conn, session['course_id'], g.user['id']):
            conn.close()
            return jsonify(error='You must be enrolled in this course to join'), 403

    import metrics
    metrics.ATTENDANCE_REQUESTS.inc()

    existing = conn.execute(
        'SELECT id FROM attendance WHERE session_id=%s AND student_id=%s',
        (session_id, g.user['id'])
    ).fetchone()
    now = datetime.datetime.utcnow().isoformat()
    if not existing:
        conn.execute(
            '''INSERT INTO attendance (student_id, course_id, session_id, join_time, status)
               VALUES (%s,%s,%s,%s,%s)''',
            (g.user['id'], session['course_id'], session_id, now, 'present')
        )
    conn.execute("UPDATE sessions SET status='live' WHERE id=%s AND status='scheduled'", (session_id,))
    conn.commit()
    conn.close()
    return jsonify(
        message='Joined session successfully',
        meeting_link=session['meeting_link'],
        join_time=now
    ), 201
