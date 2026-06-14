from flask import Blueprint, request, jsonify, g

from db import get_db
from auth_utils import login_required, roles_required

attendance_bp = Blueprint('attendance', __name__)


@attendance_bp.route('/api/sessions/<int:session_id>/attendance', methods=['GET'])
@login_required
def session_attendance(session_id):
    conn = get_db()
    rows = conn.execute('''
        SELECT a.*, u.name AS student_name, u.email AS student_email
        FROM attendance a JOIN users u ON u.id = a.student_id
        WHERE a.session_id=? ORDER BY a.join_time
    ''', (session_id,)).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@attendance_bp.route('/api/courses/<int:course_id>/attendance', methods=['GET'])
@login_required
def course_attendance(course_id):
    conn = get_db()
    rows = conn.execute('''
        SELECT a.*, u.name AS student_name, s.title AS session_title, s.session_date
        FROM attendance a
        JOIN users u ON u.id = a.student_id
        JOIN sessions s ON s.id = a.session_id
        WHERE a.course_id=? ORDER BY a.join_time DESC
    ''', (course_id,)).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@attendance_bp.route('/api/my/attendance', methods=['GET'])
@roles_required('student')
def my_attendance():
    conn = get_db()
    rows = conn.execute('''
        SELECT a.*, c.title AS course_title, s.title AS session_title, s.session_date
        FROM attendance a
        JOIN courses c ON c.id = a.course_id
        JOIN sessions s ON s.id = a.session_id
        WHERE a.student_id=? ORDER BY a.join_time DESC
    ''', (g.user['id'],)).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@attendance_bp.route('/api/attendance/reports', methods=['GET'])
@roles_required('admin', 'teacher')
def attendance_reports():
    course_id = request.args.get('course_id')
    conn = get_db()
    query = query = '''
    SELECT
        s.id AS session_id,
        c.title AS course_title,
        s.title AS session_title,
        s.session_date,
        COUNT(a.id) AS present_count,
        (
            SELECT COUNT(*)
            FROM enrollments e
            WHERE e.course_id = s.course_id
        ) AS enrolled_count

    FROM sessions s

    JOIN courses c
    ON c.id = s.course_id

    LEFT JOIN attendance a
    ON a.session_id = s.id
    AND a.status = 'present'
    WHERE s.status = 'completed'
'''
    params = []
    if course_id:
        query += ' AND s.course_id = ?'
        params.append(course_id)

    if g.user['role'] == 'teacher':
        query += ' AND c.instructor_id = ?'
        params.append(g.user['id'])
    query += ' GROUP BY s.id ORDER BY s.session_date DESC'
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

@attendance_bp.route('/api/sessions/<int:session_id>/attendance-details')
@login_required
def attendance_details(session_id):

    conn = get_db()

    session = conn.execute(
        '''
        SELECT *
        FROM sessions
        WHERE id=?
        ''',
        (session_id,)
    ).fetchone()

    if not session:
        conn.close()
        return jsonify(error='Session not found'), 404

    rows = conn.execute(
        '''
        SELECT
            u.id,
            u.name,
            u.email,

            CASE
                WHEN a.id IS NOT NULL
                THEN 'Present'
                ELSE 'Absent'
            END AS status

        FROM enrollments e

        JOIN users u
        ON u.id = e.student_id

        LEFT JOIN attendance a
        ON a.student_id = u.id
        AND a.session_id = ?

        WHERE e.course_id = ?

        ORDER BY u.name
        ''',
        (
            session_id,
            session['course_id']
        )
    ).fetchall()

    conn.close()

    return jsonify(
        [dict(r) for r in rows]
    )