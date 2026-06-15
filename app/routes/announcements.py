import datetime
from flask import Blueprint, request, jsonify, g

from db import get_db
from auth_utils import login_required, roles_required
from services.notifications import notify_course_students

announcements_bp = Blueprint('announcements', __name__)


@announcements_bp.route('/api/courses/<int:course_id>/announcements', methods=['GET'])
@login_required
def list_announcements(course_id):
    conn = get_db()
    if g.user['role'] == 'student':
        enrolled = conn.execute(
            'SELECT id FROM enrollments WHERE course_id=%s AND student_id=%s',
            (course_id, g.user['id'])
        ).fetchone()
        if not enrolled:
            conn.close()
            return jsonify(error='Enrollment required'), 403
    rows = conn.execute('''
        SELECT a.*, u.name AS author_name, c.title AS course_title
        FROM announcements a
        JOIN users u ON u.id = a.author_id
        JOIN courses c ON c.id = a.course_id
        WHERE a.course_id=%s ORDER BY a.created_at DESC
    ''', (course_id,)).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@announcements_bp.route('/api/courses/<int:course_id>/announcements', methods=['POST'])
@roles_required('admin', 'teacher')
def create_announcement(course_id):
    data = request.get_json() or {}
    title = (data.get('title') or '').strip()
    content = (data.get('content') or '').strip()
    if not title or not content:
        return jsonify(error='Title and content are required'), 400

    conn = get_db()
    course = conn.execute('SELECT * FROM courses WHERE id=%s', (course_id,)).fetchone()
    if not course:
        conn.close()
        return jsonify(error='Course not found'), 404
    if g.user['role'] == 'teacher' and course['instructor_id'] != g.user['id']:
        conn.close()
        return jsonify(error='Insufficient permissions'), 403

    conn.execute(
        'INSERT INTO announcements (course_id, author_id, title, content, created_at) VALUES (%s,%s,%s,%s,%s)',
        (course_id, g.user['id'], title, content, datetime.datetime.utcnow().isoformat())
    )
    ann_id = conn.execute('SELECT LAST_INSERT_ID()').fetchone()['LAST_INSERT_ID()']
    notify_course_students(
        conn, course_id, 'announcement', title, content, ann_id, exclude_user_id=g.user['id']
    )
    conn.commit()
    row = conn.execute('''
        SELECT a.*, u.name AS author_name, c.title AS course_title
        FROM announcements a JOIN users u ON u.id = a.author_id JOIN courses c ON c.id = a.course_id
        WHERE a.id=%s
    ''', (ann_id,)).fetchone()
    conn.close()
    return jsonify(dict(row)), 201


@announcements_bp.route('/api/announcements/<int:ann_id>', methods=['DELETE'])
@login_required
def delete_announcement(ann_id):
    conn = get_db()
    row = conn.execute('SELECT * FROM announcements WHERE id=%s', (ann_id,)).fetchone()
    if not row:
        conn.close()
        return jsonify(error='Not found'), 404
    if g.user['role'] != 'admin' and row['author_id'] != g.user['id']:
        conn.close()
        return jsonify(error='Insufficient permissions'), 403
    conn.execute('DELETE FROM announcements WHERE id=%s', (ann_id,))
    conn.commit()
    conn.close()
    return jsonify(message='Announcement deleted')


@announcements_bp.route('/api/my/announcements', methods=['GET'])
@roles_required('student')
def my_announcements():
    conn = get_db()
    rows = conn.execute('''
        SELECT a.*, u.name AS author_name, c.title AS course_title
        FROM announcements a
        JOIN users u ON u.id = a.author_id
        JOIN courses c ON c.id = a.course_id
        JOIN enrollments e ON e.course_id = a.course_id AND e.student_id = %s
        ORDER BY a.created_at DESC LIMIT 20
    ''', (g.user['id'],)).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])
