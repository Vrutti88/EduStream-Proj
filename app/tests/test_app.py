import os
import sys
import tempfile
import datetime
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import app as app_module
import db as db_module


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


def auth_header(client, email, password):
    resp = client.post('/api/auth/login', json={'email': email, 'password': password})
    token = resp.get_json()['token']
    return {'Authorization': f'Bearer {token}'}


def test_health(client):
    resp = client.get('/health')
    assert resp.status_code == 200
    assert resp.get_json()['status'] == 'healthy'


def test_register_and_login(client):
    resp = client.post('/api/auth/register', json={
        'email': 'newstudent@test.edu',
        'password': 'secret123',
        'name': 'New Student',
        'role': 'student',
    })
    assert resp.status_code == 201
    assert 'token' in resp.get_json()

    resp = client.post('/api/auth/login', json={
        'email': 'newstudent@test.edu',
        'password': 'secret123',
    })
    assert resp.status_code == 200
    assert resp.get_json()['user']['role'] == 'student'


def test_create_and_list_course(client):
    headers = auth_header(client, 'teacher@edustream.edu', 'Teacher@123')
    resp = client.post('/api/courses', json={
        'title': 'Intro to Algebra',
        'course_code': 'ALG101',
        'instructor': 'Ms. Iyer',
        'description': 'Basics of algebra',
        'category': 'Mathematics',
    }, headers=headers)
    assert resp.status_code == 201

    resp = client.get('/api/courses')
    data = resp.get_json()
    assert len(data) >= 1
    course = next(c for c in data if c['title'] == 'Intro to Algebra')
    assert course['class_count'] == 0
    assert course['enrolled_count'] == 0


def test_create_session_and_join(client):
    teacher_headers = auth_header(client, 'teacher@edustream.edu', 'Teacher@123')
    student_headers = auth_header(client, 'student@edustream.edu', 'Student@123')

    resp = client.post('/api/courses', json={
        'title': 'Physics 101', 'course_code': 'PHY101'
    }, headers=teacher_headers)
    course_id = resp.get_json()['id']

    client.post(f'/api/courses/{course_id}/enroll', json={}, headers=student_headers)

    now = datetime.datetime.utcnow()
    start = (now - datetime.timedelta(minutes=5)).strftime('%H:%M')
    end = (now + datetime.timedelta(hours=1)).strftime('%H:%M')
    date = now.strftime('%Y-%m-%d')

    resp = client.post(f'/api/courses/{course_id}/sessions', json={
        'title': 'Lecture 1 - Motion',
        'session_date': date,
        'start_time': start,
        'end_time': end,
    }, headers=teacher_headers)
    assert resp.status_code == 201
    session_id = resp.get_json()['id']

    resp = client.post(f'/api/sessions/{session_id}/join', json={}, headers=student_headers)
    assert resp.status_code == 201

    sessions = client.get(f'/api/courses/{course_id}/sessions').get_json()
    live = next(s for s in sessions if s['id'] == session_id)
    assert live['effective_status'] == 'live'


def test_enroll_student(client):
    teacher_headers = auth_header(client, 'teacher@edustream.edu', 'Teacher@123')
    client.post('/api/courses', json={'title': 'Chemistry', 'course_code': 'CHEM101'}, headers=teacher_headers)
    courses = client.get('/api/courses').get_json()
    course_id = next(c for c in courses if c['title'] == 'Chemistry')['id']

    resp = client.post('/api/auth/register', json={
        'email': 'bob@student.edu', 'password': 'bob123', 'name': 'Bob', 'role': 'student'
    })
    bob_headers = {'Authorization': f"Bearer {resp.get_json()['token']}"}

    resp = client.post(f'/api/courses/{course_id}/enroll', json={}, headers=bob_headers)
    assert resp.status_code == 201

    students = client.get(f'/api/courses/{course_id}/students', headers=teacher_headers).get_json()
    assert any(s['student_name'] == 'Bob' for s in students)


def test_stats(client):
    teacher_headers = auth_header(client, 'teacher@edustream.edu', 'Teacher@123')
    client.post('/api/courses', json={'title': 'Biology', 'course_code': 'BIO101'}, headers=teacher_headers)
    courses = client.get('/api/courses').get_json()
    course_id = next(c for c in courses if c['title'] == 'Biology')['id']
    client.post(f'/api/courses/{course_id}/sessions', json={
        'title': 'Cell Biology',
        'session_date': '2026-06-21',
        'start_time': '09:00',
        'end_time': '10:00',
    }, headers=teacher_headers)

    stats = client.get('/api/stats').get_json()
    assert stats['total_courses'] >= 1
    assert stats['total_sessions'] >= 1
    assert 'total_enrollments' in stats


def test_session_time_blocking(client):
    teacher_headers = auth_header(client, 'teacher@edustream.edu', 'Teacher@123')
    student_headers = auth_header(client, 'student@edustream.edu', 'Student@123')

    resp = client.post('/api/courses', json={'title': 'Future Class', 'course_code': 'FUT101'}, headers=teacher_headers)
    course_id = resp.get_json()['id']
    client.post(f'/api/courses/{course_id}/enroll', json={}, headers=student_headers)

    future = (datetime.datetime.utcnow() + datetime.timedelta(days=7)).strftime('%Y-%m-%d')
    resp = client.post(f'/api/courses/{course_id}/sessions', json={
        'title': 'Future Session',
        'session_date': future,
        'start_time': '10:00',
        'end_time': '11:00',
    }, headers=teacher_headers)
    session_id = resp.get_json()['id']

    resp = client.post(f'/api/sessions/{session_id}/join', json={}, headers=student_headers)
    assert resp.status_code == 403


def test_admin_dashboard(client):
    headers = auth_header(client, 'admin@edustream.edu', 'Admin@123')
    resp = client.get('/api/dashboard/admin', headers=headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert 'stats' in data
    assert data['stats']['total_users'] >= 3


def test_unauthorized_course_create(client):
    resp = client.post('/api/courses', json={'title': 'Hack', 'course_code': 'HACK'})
    assert resp.status_code == 401
