import os
import datetime
from flask import Blueprint, request, jsonify, send_from_directory, g
from werkzeug.utils import secure_filename

from config import UPLOAD_DIR, ALLOWED_EXTENSIONS, MAX_CONTENT_LENGTH
from db import get_db
from auth_utils import login_required, roles_required
from services.notifications import notify_course_students

materials_bp = Blueprint('materials', __name__)


def _allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def _can_manage_course_materials(conn, course_id, user):
    if user['role'] == 'admin':
        return True
    row = conn.execute('SELECT instructor_id FROM courses WHERE id=%s', (course_id,)).fetchone()
    return row and row['instructor_id'] == user['id']


def _is_enrolled(conn, course_id, student_id):
    return conn.execute(
        'SELECT id FROM enrollments WHERE course_id=%s AND student_id=%s',
        (course_id, student_id)
    ).fetchone() is not None


@materials_bp.route('/api/courses/<int:course_id>/materials', methods=['GET'])
@login_required
def list_materials(course_id):
    conn = get_db()
    if g.user['role'] == 'student' and not _is_enrolled(conn, course_id, g.user['id']):
        conn.close()
        return jsonify(error='Enrollment required to view materials'), 403
    rows = conn.execute('''
        SELECT m.*, u.name AS uploaded_by_name
        FROM materials m JOIN users u ON u.id = m.uploaded_by
        WHERE m.course_id=%s ORDER BY m.uploaded_at DESC
    ''', (course_id,)).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@materials_bp.route('/api/courses/<int:course_id>/materials', methods=['POST'])
@roles_required('admin', 'teacher')
def upload_material(course_id):
    conn = get_db()
    if not _can_manage_course_materials(conn, course_id, g.user):
        conn.close()
        return jsonify(error='Insufficient permissions'), 403

    if 'file' not in request.files:
        conn.close()
        return jsonify(error='No file provided'), 400
    file = request.files['file']
    if not file.filename:
        conn.close()
        return jsonify(error='No file selected'), 400
    if not _allowed_file(file.filename):
        conn.close()
        return jsonify(error='File type not allowed. Use PDF, PPT, or DOCX'), 400

    original = secure_filename(file.filename)
    ext = original.rsplit('.', 1)[1].lower()
    stored = f'{course_id}_{datetime.datetime.utcnow().strftime("%Y%m%d%H%M%S")}_{original}'
    filepath = os.path.join(UPLOAD_DIR, stored)
    file.save(filepath)
    size = os.path.getsize(filepath)

    conn.execute(
        '''INSERT INTO materials (course_id, uploaded_by, filename, original_name, file_type, file_size, uploaded_at)
           VALUES (%s,%s,%s,%s,%s,%s,%s)''',
        (course_id, g.user['id'], stored, original, ext, size,
         datetime.datetime.utcnow().isoformat())
    )
    material_id = conn.execute('SELECT LAST_INSERT_ID()').fetchone()['LAST_INSERT_ID()']
    notify_course_students(
        conn, course_id, 'material', 'New study material uploaded',
        f'New material "{original}" is available.', material_id, exclude_user_id=g.user['id']
    )
    conn.commit()
    row = conn.execute('SELECT m.*, u.name AS uploaded_by_name FROM materials m JOIN users u ON u.id = m.uploaded_by WHERE m.id=%s', (material_id,)).fetchone()
    conn.close()
    return jsonify(dict(row)), 201


@materials_bp.route('/api/materials/<int:material_id>/download', methods=['GET'])
@login_required
def download_material(material_id):
    conn = get_db()
    row = conn.execute('SELECT * FROM materials WHERE id=%s', (material_id,)).fetchone()
    if not row:
        conn.close()
        return jsonify(error='Material not found'), 404
    if g.user['role'] == 'student' and not _is_enrolled(conn, row['course_id'], g.user['id']):
        conn.close()
        return jsonify(error='Enrollment required'), 403
    conn.close()
    return send_from_directory(UPLOAD_DIR, row['filename'], as_attachment=True, download_name=row['original_name'])


@materials_bp.route('/api/materials/<int:material_id>', methods=['DELETE'])
@login_required
def delete_material(material_id):
    conn = get_db()
    row = conn.execute('SELECT * FROM materials WHERE id=%s', (material_id,)).fetchone()
    if not row:
        conn.close()
        return jsonify(error='Material not found'), 404
    if not _can_manage_course_materials(conn, row['course_id'], g.user):
        conn.close()
        return jsonify(error='Insufficient permissions'), 403
    filepath = os.path.join(UPLOAD_DIR, row['filename'])
    if os.path.exists(filepath):
        os.remove(filepath)
    conn.execute('DELETE FROM materials WHERE id=%s', (material_id,))
    conn.commit()
    conn.close()
    return jsonify(message='Material deleted')
