import datetime
from flask import Blueprint, jsonify, g

from db import get_db
from auth_utils import login_required, roles_required
from services.sessions import sync_all_sessions, compute_session_status

analytics_bp = Blueprint('analytics', __name__)


@analytics_bp.route('/api/stats', methods=['GET'])
def platform_stats():
    conn = get_db()
    sync_all_sessions(conn)
    conn.commit()
    total_users = conn.execute('SELECT COUNT(*) FROM users').fetchone()[0]
    total_teachers = conn.execute("SELECT COUNT(*) FROM users WHERE role='teacher'").fetchone()[0]
    total_students = conn.execute("SELECT COUNT(*) FROM users WHERE role='student'").fetchone()[0]
    total_courses = conn.execute('SELECT COUNT(*) FROM courses').fetchone()[0]
    total_sessions = conn.execute('SELECT COUNT(*) FROM sessions').fetchone()[0]
    total_enrollments = conn.execute('SELECT COUNT(*) FROM enrollments').fetchone()[0]
    live_sessions = conn.execute("SELECT COUNT(*) FROM sessions WHERE status='live'").fetchone()[0]
    conn.close()
    return jsonify(
        total_users=total_users,
        total_teachers=total_teachers,
        total_students=total_students,
        total_courses=total_courses,
        total_sessions=total_sessions,
        total_classes=total_sessions,
        total_enrollments=total_enrollments,
        live_sessions=live_sessions,
        active_sessions=live_sessions,
    )


@analytics_bp.route('/api/dashboard/admin', methods=['GET'])
@roles_required('admin')
def admin_dashboard():
    conn = get_db()
    sync_all_sessions(conn)
    conn.commit()
    stats = {
        'total_users': conn.execute('SELECT COUNT(*) FROM users').fetchone()[0],
        'total_teachers': conn.execute("SELECT COUNT(*) FROM users WHERE role='teacher'").fetchone()[0],
        'total_students': conn.execute("SELECT COUNT(*) FROM users WHERE role='student'").fetchone()[0],
        'total_courses': conn.execute('SELECT COUNT(*) FROM courses').fetchone()[0],
        'total_sessions': conn.execute('SELECT COUNT(*) FROM sessions').fetchone()[0],
        'active_sessions': conn.execute("SELECT COUNT(*) FROM sessions WHERE status='live'").fetchone()[0],
        'total_enrollments': conn.execute('SELECT COUNT(*) FROM enrollments').fetchone()[0],
        'total_attendance': conn.execute("SELECT COUNT(*) FROM attendance WHERE status='present'").fetchone()[0],
    }
    enrollment_by_course = conn.execute('''
        SELECT c.title, COUNT(e.id) AS count
        FROM courses c LEFT JOIN enrollments e ON e.course_id = c.id
        GROUP BY c.id ORDER BY count DESC LIMIT 10
    ''').fetchall()
    attendance_trend = conn.execute('''
        SELECT DATE(join_time) AS day, COUNT(*) AS count
        FROM attendance WHERE join_time IS NOT NULL
        GROUP BY DATE(join_time) ORDER BY day DESC LIMIT 14
    ''').fetchall()
    session_activity = conn.execute('''
        SELECT status, COUNT(*) AS count FROM sessions GROUP BY status
    ''').fetchall()
    conn.close()
    return jsonify(
        stats=stats,
        enrollment_by_course=[dict(r) for r in enrollment_by_course],
        attendance_trend=[dict(r) for r in reversed(list(attendance_trend))],
        session_activity=[dict(r) for r in session_activity],
    )


@analytics_bp.route('/api/dashboard/teacher', methods=['GET'])
@roles_required('teacher', 'admin')
def teacher_dashboard():
    conn = get_db()
    sync_all_sessions(conn)
    conn.commit()
    teacher_id = g.user['id']
    my_courses = conn.execute(
        'SELECT COUNT(*) FROM courses WHERE instructor_id=?', (teacher_id,)
    ).fetchone()[0]
    my_sessions = conn.execute(
        'SELECT COUNT(*) FROM sessions WHERE instructor_id=?', (teacher_id,)
    ).fetchone()[0]
    upcoming = conn.execute('''
        SELECT COUNT(*) FROM sessions s
        JOIN courses c ON c.id = s.course_id
        WHERE c.instructor_id=? AND s.status='scheduled'
    ''', (teacher_id,)).fetchone()[0]
    student_count = conn.execute('''
        SELECT COUNT(DISTINCT e.student_id) FROM enrollments e
        JOIN courses c ON c.id = e.course_id WHERE c.instructor_id=?
    ''', (teacher_id,)).fetchone()[0]
    # attendance_stats = conn.execute('''
    #     SELECT COUNT(a.id) AS present,
    #            (SELECT COUNT(*) FROM sessions s JOIN courses c ON c.id=s.course_id WHERE c.instructor_id=?) AS total_sessions
    #     FROM attendance a
    #     JOIN courses c ON c.id = a.course_id
    #     WHERE c.instructor_id=?
    # ''', (teacher_id, teacher_id)).fetchone()
    # attendance_percentage = round(
    #     (
    #         attendance_stats['present']
    #         / my_sessions
    #     ) * 100,
    #     1
    # ) if my_sessions else 0
    upcoming_sessions = conn.execute('''
        SELECT s.*, c.title AS course_title FROM sessions s
        JOIN courses c ON c.id = s.course_id
        WHERE c.instructor_id=? AND s.status IN ('scheduled','live')
        ORDER BY s.session_date, s.start_time LIMIT 5
    ''', (teacher_id,)).fetchall()
    conn.close()
    return jsonify(
        my_courses=my_courses,
        my_sessions=my_sessions,
        upcoming_sessions_count=upcoming,
        student_count=student_count,
        # attendance_present=attendance_stats['present'] if attendance_stats else 0,
        # attendance_percentage=attendance_percentage,
        upcoming_sessions=[dict(r) for r in upcoming_sessions],
    )


@analytics_bp.route('/api/dashboard/student', methods=['GET'])
@roles_required('student')
def student_dashboard():
    conn = get_db()
    sync_all_sessions(conn)
    conn.commit()
    student_id = g.user['id']
    enrolled = conn.execute(
        'SELECT COUNT(*) FROM enrollments WHERE student_id=?', (student_id,)
    ).fetchone()[0]
    upcoming = conn.execute('''
        SELECT s.*, c.title AS course_title FROM sessions s
        JOIN courses c ON c.id = s.course_id
        JOIN enrollments e ON e.course_id = c.id AND e.student_id=?
        WHERE s.status IN ('scheduled','live')
        ORDER BY s.session_date, s.start_time LIMIT 5
    ''', (student_id,)).fetchall()
    attended = conn.execute(
        "SELECT COUNT(*) FROM attendance WHERE student_id=? AND status='present'", (student_id,)
    ).fetchone()[0]
    total_sessions = conn.execute('''
        SELECT COUNT(*) FROM sessions s
        JOIN enrollments e ON e.course_id = s.course_id AND e.student_id=?
    ''', (student_id,)).fetchone()[0]
    pct = round((attended / total_sessions * 100) if total_sessions else 0, 1)
    announcements = conn.execute('''
        SELECT a.*, c.title AS course_title FROM announcements a
        JOIN courses c ON c.id = a.course_id
        JOIN enrollments e ON e.course_id = a.course_id AND e.student_id=?
        ORDER BY a.created_at DESC LIMIT 5
    ''', (student_id,)).fetchall()
    conn.close()
    return jsonify(
    enrolled_courses=enrolled,
    upcoming_sessions=[dict(r) for r in upcoming],

    attendance_percentage=pct,
    present_sessions=attended,
    total_sessions=total_sessions,

    recent_announcements=[dict(r) for r in announcements],
)


@analytics_bp.route('/api/analytics/enrollments', methods=['GET'])
@login_required
def enrollment_analytics():
    conn = get_db()
    rows = conn.execute('''
        SELECT c.title, c.category, COUNT(e.id) AS enrollments
        FROM courses c LEFT JOIN enrollments e ON e.course_id = c.id
        GROUP BY c.id ORDER BY enrollments DESC
    ''').fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@analytics_bp.route('/api/analytics/attendance-trends', methods=['GET'])
@login_required
def attendance_trends():
    conn = get_db()
    rows = conn.execute('''
        SELECT DATE(a.join_time) AS date, COUNT(*) AS count
        FROM attendance a WHERE a.status='present'
        GROUP BY DATE(a.join_time) ORDER BY date DESC LIMIT 30
    ''').fetchall()
    conn.close()
    return jsonify([dict(r) for r in reversed(list(rows))])
