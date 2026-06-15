import datetime
import re
from flask import Blueprint, request, jsonify, g

from db import get_db
from auth_utils import login_required, roles_required
from services.notifications import notify_course_students

courses_bp = Blueprint('courses', __name__)


def _course_code(title):
    base = re.sub(r'[^A-Za-z0-9]', '', title.upper())[:6] or 'COURSE'
    return f'{base}{datetime.datetime.utcnow().strftime("%m%d")}'


def _course_dict(row):
    return dict(row)


def _can_manage_course(conn, course_id, user):
    if user['role'] == 'admin':
        return True
    if user['role'] == 'teacher':
        row = conn.execute('SELECT instructor_id FROM courses WHERE id=%s', (course_id,)).fetchone()
        return row and row['instructor_id'] == user['id']
    return False


@courses_bp.route('/api/courses', methods=['GET'])
def list_courses():
    search = request.args.get('search', '').strip()
    category = request.args.get('category', '').strip()
    conn = get_db()
    query = '''
        SELECT c.*, u.name AS instructor_name,
               (SELECT COUNT(*) FROM enrollments e WHERE e.course_id = c.id) AS enrolled_count,
               (SELECT COUNT(*) FROM sessions s WHERE s.course_id = c.id) AS session_count
        FROM courses c
        JOIN users u ON u.id = c.instructor_id
        WHERE 1=1
    '''
    params = []
    if search:
        query += ' AND (c.title LIKE %s OR c.course_code LIKE %s OR c.description LIKE %s)'
        params.extend([f'%{search}%'] * 3)
    if category:
        query += ' AND c.category = %s'
        params.append(category)
    query += ' ORDER BY c.id DESC'
    rows = conn.execute(query, params).fetchall()
    conn.close()
    result = []
    for r in rows:
        d = _course_dict(r)
        d['class_count'] = d.get('session_count', 0)
        result.append(d)
    return jsonify(result)


@courses_bp.route('/api/courses', methods=['POST'])
@roles_required('admin', 'teacher')
def create_course():
    data = request.get_json() or {}
    title = (data.get('title') or '').strip()
    if not title:
        return jsonify(error='Course title is required'), 400

    instructor_id = g.user['id']
    if g.user['role'] == 'admin' and data.get('instructor_id'):
        instructor_id = data['instructor_id']

    conn = get_db()
    code = (data.get('course_code') or _course_code(title)).strip().upper()
    try:
        conn.execute(
            '''INSERT INTO courses (title, course_code, description, instructor_id, category, thumbnail, created_at)
               VALUES (%s,%s,%s,%s,%s,%s,%s)''',
            (title, code, data.get('description', ''), instructor_id,
             data.get('category', 'General'), data.get('thumbnail', ''),
             datetime.datetime.utcnow().isoformat())
        )
        conn.commit()
        course_id = conn.execute('SELECT LAST_INSERT_ID()').fetchone()['LAST_INSERT_ID()']
        row = conn.execute('''
            SELECT c.*, u.name AS instructor_name, 0 AS enrolled_count, 0 AS session_count
            FROM courses c JOIN users u ON u.id = c.instructor_id WHERE c.id=%s
        ''', (course_id,)).fetchone()
        conn.close()
        return jsonify(_course_dict(row)), 201
    except Exception:
        conn.close()
        return jsonify(error='Course code already exists'), 409


@courses_bp.route('/api/courses/<int:course_id>', methods=['GET'])
def get_course(course_id):
    conn = get_db()
    row = conn.execute('''
        SELECT c.*, u.name AS instructor_name,
               (SELECT COUNT(*) FROM enrollments e WHERE e.course_id = c.id) AS enrolled_count,
               (SELECT COUNT(*) FROM sessions s WHERE s.course_id = c.id) AS session_count
        FROM courses c JOIN users u ON u.id = c.instructor_id WHERE c.id=%s
    ''', (course_id,)).fetchone()
    conn.close()
    if not row:
        return jsonify(error='Course not found'), 404
    return jsonify(_course_dict(row))


@courses_bp.route('/api/courses/<int:course_id>', methods=['PUT'])
@login_required
def update_course(course_id):
    conn = get_db()
    if not _can_manage_course(conn, course_id, g.user):
        conn.close()
        return jsonify(error='Insufficient permissions'), 403

    data = request.get_json() or {}
    fields = []
    values = []
    for key in ('title', 'description', 'category', 'thumbnail', 'course_code'):
        if key in data:
            fields.append(f'{key}=%s')
            values.append(data[key])
    if not fields:
        conn.close()
        return jsonify(error='No fields to update'), 400
    values.append(course_id)
    conn.execute(f'UPDATE courses SET {", ".join(fields)} WHERE id=%s', values)
    conn.commit()
    row = conn.execute('''
        SELECT c.*, u.name AS instructor_name,
               (SELECT COUNT(*) FROM enrollments e WHERE e.course_id = c.id) AS enrolled_count,
               (SELECT COUNT(*) FROM sessions s WHERE s.course_id = c.id) AS session_count
        FROM courses c JOIN users u ON u.id = c.instructor_id WHERE c.id=%s
    ''', (course_id,)).fetchone()
    conn.close()
    return jsonify(_course_dict(row))


@courses_bp.route('/api/courses/<int:course_id>', methods=['DELETE'])
@login_required
def delete_course(course_id):
    conn = get_db()
    if not _can_manage_course(conn, course_id, g.user):
        conn.close()
        return jsonify(error='Insufficient permissions'), 403
    conn.execute('DELETE FROM courses WHERE id=%s', (course_id,))
    conn.commit()
    conn.close()
    return jsonify(message='Course deleted')


@courses_bp.route('/api/courses/categories', methods=['GET'])
def categories():
    conn = get_db()
    rows = conn.execute(
        'SELECT DISTINCT category FROM courses WHERE category IS NOT NULL ORDER BY category'
    ).fetchall()
    conn.close()
    return jsonify([r['category'] for r in rows])
