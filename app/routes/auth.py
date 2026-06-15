import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from flask import Blueprint, request, jsonify, g

from db import get_db
from auth_utils import create_token, login_required
from services.notifications import create_notification

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/api/auth/register', methods=['POST'])
def register():
    data = request.get_json() or {}
    email = (data.get('email') or '').strip().lower()
    password = data.get('password') or ''
    name = (data.get('name') or '').strip()
    role = (data.get('role') or 'student').strip().lower()

    if not email or not password or not name:
        return jsonify(error='Email, password, and name are required'), 400
    if len(password) < 6:
        return jsonify(error='Password must be at least 6 characters'), 400
    if role not in ('student', 'teacher'):
        role = 'student'

    conn = get_db()
    if conn.execute('SELECT id FROM users WHERE email=%s', (email,)).fetchone():
        conn.close()
        return jsonify(error='Email already registered'), 409

    conn.execute(
        'INSERT INTO users (email, password_hash, name, role, created_at) VALUES (%s,%s,%s,%s,%s)',
        (email, generate_password_hash(password), name, role,
         datetime.datetime.utcnow().isoformat())
    )
    conn.commit()
    user_id = conn.execute('SELECT LAST_INSERT_ID()').fetchone()['LAST_INSERT_ID()']
    user = {'id': user_id, 'email': email, 'name': name, 'role': role}
    create_notification(conn, user_id, 'welcome', 'Welcome to EduStream',
                        f'Your {role} account has been created successfully.')
    conn.commit()
    conn.close()
    token = create_token(user)
    return jsonify(user=user, token=token), 201


@auth_bp.route('/api/auth/login', methods=['POST'])
def login():
    data = request.get_json() or {}
    email = (data.get('email') or '').strip().lower()
    password = data.get('password') or ''

    conn = get_db()
    row = conn.execute('SELECT * FROM users WHERE email=%s', (email,)).fetchone()
    conn.close()
    if not row or not check_password_hash(row['password_hash'], password):
        return jsonify(error='Invalid email or password'), 401

    user = {'id': row['id'], 'email': row['email'], 'name': row['name'], 'role': row['role']}
    return jsonify(user=user, token=create_token(user))


@auth_bp.route('/api/auth/logout', methods=['POST'])
@login_required
def logout():
    return jsonify(message='Logged out successfully')


@auth_bp.route('/api/auth/me', methods=['GET'])
@login_required
def me():
    return jsonify(user=g.user)
