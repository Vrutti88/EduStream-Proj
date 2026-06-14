import os
import sys
import tempfile
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import app as app_module
import db as db_module
from services.sessions import compute_session_status, can_join_session


@pytest.fixture
def client():
    db_fd, db_path = tempfile.mkstemp()
    db_module.DB = db_path
    db_module.DB_PATH = db_path
    app_module.db.DB = db_path
    db_module.init_db()
    app_module.app.config['TESTING'] = True
    with app_module.app.test_client() as client:
        yield client
    os.close(db_fd)
    os.unlink(db_path)


def test_jwt_required_endpoints(client):
    resp = client.get('/api/auth/me')
    assert resp.status_code == 401

    resp = client.post('/api/auth/login', json={
        'email': 'admin@edustream.edu', 'password': 'Admin@123'
    })
    token = resp.get_json()['token']
    headers = {'Authorization': f'Bearer {token}'}
    resp = client.get('/api/auth/me', headers=headers)
    assert resp.status_code == 200
    assert resp.get_json()['user']['role'] == 'admin'


def test_role_based_access(client):
    resp = client.post('/api/auth/login', json={
        'email': 'student@edustream.edu', 'password': 'Student@123'
    })
    headers = {'Authorization': f"Bearer {resp.get_json()['token']}"}
    resp = client.get('/api/dashboard/admin', headers=headers)
    assert resp.status_code == 403


def test_compute_session_status():
    session = {
        'status': 'scheduled',
        'session_date': '2020-01-01',
        'start_time': '09:00',
        'end_time': '10:00',
    }
    assert compute_session_status(session) == 'completed'

    session['session_date'] = '2099-01-01'
    assert compute_session_status(session) == 'scheduled'

    session['status'] = 'cancelled'
    assert compute_session_status(session) == 'cancelled'
