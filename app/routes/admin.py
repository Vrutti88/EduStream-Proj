import datetime
from flask import Blueprint, request, jsonify, g
from werkzeug.security import generate_password_hash

from db import get_db
from auth_utils import roles_required
from services.sessions import sync_all_sessions

admin_bp = Blueprint('admin', __name__)


@admin_bp.route('/api/admin/users', methods=['GET'])
@roles_required('admin')
def list_users():
    role = request.args.get('role')
    conn = get_db()
    query = 'SELECT id, email, name, role, created_at FROM users'
    params = []
    if role:
        query += ' WHERE role=%s'
        params.append(role)
    query += ' ORDER BY id DESC'
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@admin_bp.route('/api/admin/users', methods=['POST'])
@roles_required('admin')
def create_user():
    data = request.get_json() or {}
    email = (data.get('email') or '').strip().lower()
    name = (data.get('name') or '').strip()
    role = (data.get('role') or 'student').strip()
    password = data.get('password') or 'ChangeMe123'
    if not email or not name:
        return jsonify(error='Email and name required'), 400
    if role not in ('admin', 'teacher', 'student'):
        return jsonify(error='Invalid role'), 400
    conn = get_db()
    try:
        conn.execute(
            'INSERT INTO users (email, password_hash, name, role, created_at) VALUES (%s,%s,%s,%s,%s)',
            (email, generate_password_hash(password), name, role,
             datetime.datetime.utcnow().isoformat())
        )
        conn.commit()
        user_id = conn.execute('SELECT LAST_INSERT_ID()').fetchone()['LAST_INSERT_ID()']
        row = conn.execute(
            'SELECT id, email, name, role, created_at FROM users WHERE id=%s', (user_id,)
        ).fetchone()
        conn.close()
        return jsonify(dict(row)), 201
    except Exception:
        conn.close()
        return jsonify(error='Email already exists'), 409


@admin_bp.route('/api/admin/users/<int:user_id>', methods=['PUT'])
@roles_required('admin')
def update_user(user_id):
    data = request.get_json() or {}
    conn = get_db()
    fields = []
    values = []
    for key in ('name', 'role', 'email'):
        if key in data:
            fields.append(f'{key}=%s')
            values.append(data[key])
    if data.get('password'):
        fields.append('password_hash=%s')
        values.append(generate_password_hash(data['password']))
    if not fields:
        conn.close()
        return jsonify(error='No fields to update'), 400
    values.append(user_id)
    conn.execute(f'UPDATE users SET {", ".join(fields)} WHERE id=%s', values)
    conn.commit()
    row = conn.execute(
        'SELECT id, email, name, role, created_at FROM users WHERE id=%s', (user_id,)
    ).fetchone()
    conn.close()
    if not row:
        return jsonify(error='User not found'), 404
    return jsonify(dict(row))


@admin_bp.route('/api/admin/users/<int:user_id>', methods=['DELETE'])
@roles_required('admin')
def delete_user(user_id):
    if user_id == g.user['id']:
        return jsonify(error='Cannot delete your own account'), 400
    conn = get_db()
    conn.execute('DELETE FROM users WHERE id=%s', (user_id,))
    conn.commit()
    conn.close()
    return jsonify(message='User deleted')


@admin_bp.route('/api/admin/sessions', methods=['GET'])
@roles_required('admin')
def all_sessions():
    conn = get_db()
    sync_all_sessions(conn)
    conn.commit()
    rows = conn.execute('''
        SELECT s.*, c.title AS course_title, u.name AS instructor_name
        FROM sessions s
        JOIN courses c ON c.id = s.course_id
        JOIN users u ON u.id = s.instructor_id
        ORDER BY s.session_date DESC
    ''').fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])
