import datetime
from flask import Blueprint, request, jsonify, g

from db import get_db
from auth_utils import login_required, roles_required
from services.notifications import create_notification, notify_course_students

enrollments_bp = Blueprint('enrollments', __name__)


@enrollments_bp.route('/api/courses/<int:course_id>/enroll', methods=['POST'])
@roles_required('student', 'admin')
def enroll(course_id):
    conn = get_db()
    course = conn.execute('SELECT * FROM courses WHERE id=%s', (course_id,)).fetchone()
    if not course:
        conn.close()
        return jsonify(error='Course not found'), 404

    student_id = g.user['id']
    if g.user['role'] == 'admin' and request.get_json():
        data = request.get_json() or {}
        if data.get('student_id'):
            student_id = data['student_id']

    existing = conn.execute(
        'SELECT id FROM enrollments WHERE course_id=%s AND student_id=%s',
        (course_id, student_id)
    ).fetchone()
    if existing:
        conn.close()
        return jsonify(error='Already enrolled'), 409

    now = datetime.datetime.utcnow().isoformat()
    conn.execute(
        'INSERT INTO enrollments (course_id, student_id, enrolled_at) VALUES (%s,%s,%s)',
        (course_id, student_id, now)
    )
    create_notification(
        conn, student_id, 'enrollment', f'Enrolled in {course["title"]}',
        f'You have successfully enrolled in {course["title"]}.', course_id
    )
    create_notification(
        conn, course['instructor_id'], 'new_enrollment', 'New student enrolled',
        f'A student enrolled in {course["title"]}.', course_id
    )
    conn.commit()
    conn.close()
    return jsonify(message='Enrolled successfully'), 201


@enrollments_bp.route('/api/courses/<int:course_id>/students', methods=['GET'])
@login_required
def course_students(course_id):
    conn = get_db()
    rows = conn.execute('''
        SELECT e.id, e.enrolled_at, u.id AS student_id, u.name AS student_name, u.email AS student_email
        FROM enrollments e JOIN users u ON u.id = e.student_id
        WHERE e.course_id=%s ORDER BY e.enrolled_at DESC
    ''', (course_id,)).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@enrollments_bp.route('/api/courses/<int:course_id>/enrollments/<int:student_id>', methods=['DELETE'])
@login_required
def remove_enrollment(course_id, student_id):
    conn = get_db()
    course = conn.execute('SELECT instructor_id FROM courses WHERE id=%s', (course_id,)).fetchone()
    if not course:
        conn.close()
        return jsonify(error='Course not found'), 404
    if g.user['role'] not in ('admin',) and not (
        g.user['role'] == 'teacher' and course['instructor_id'] == g.user['id']
    ):
        conn.close()
        return jsonify(error='Insufficient permissions'), 403
    conn.execute('DELETE FROM enrollments WHERE course_id=%s AND student_id=%s', (course_id, student_id))
    conn.commit()
    conn.close()
    return jsonify(message='Enrollment removed')


@enrollments_bp.route('/api/my/enrollments', methods=['GET'])
@roles_required('student')
def my_enrollments():
    conn = get_db()
    rows = conn.execute('''
        SELECT e.*, c.title, c.course_code, c.category, u.name AS instructor_name
        FROM enrollments e
        JOIN courses c ON c.id = e.course_id
        JOIN users u ON u.id = c.instructor_id
        WHERE e.student_id=%s ORDER BY e.enrolled_at DESC
    ''', (g.user['id'],)).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])
