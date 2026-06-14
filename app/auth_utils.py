import functools
import datetime
import jwt
from flask import request, jsonify, g

from config import SECRET_KEY, JWT_EXPIRY_HOURS


def create_token(user):
    payload = {
        'sub': user['id'],
        'email': user['email'],
        'name': user['name'],
        'role': user['role'],
        'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=JWT_EXPIRY_HOURS),
        'iat': datetime.datetime.utcnow(),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm='HS256')


def decode_token(token):
    return jwt.decode(token, SECRET_KEY, algorithms=['HS256'])


def get_token_from_request():
    auth = request.headers.get('Authorization', '')
    if auth.startswith('Bearer '):
        return auth[7:]
    return request.cookies.get('token')


def get_current_user(optional=False):
    token = get_token_from_request()
    if not token:
        if optional:
            return None
        return None
    try:
        payload = decode_token(token)
        return {
            'id': payload['sub'],
            'email': payload['email'],
            'name': payload['name'],
            'role': payload['role'],
        }
    except jwt.PyJWTError:
        return None


def login_required(f):
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        user = get_current_user()
        if not user:
            return jsonify(error='Authentication required'), 401
        g.user = user
        return f(*args, **kwargs)
    return decorated


def roles_required(*roles):
    def decorator(f):
        @functools.wraps(f)
        @login_required
        def decorated(*args, **kwargs):
            if g.user['role'] not in roles:
                return jsonify(error='Insufficient permissions'), 403
            return f(*args, **kwargs)
        return decorated
    return decorator
