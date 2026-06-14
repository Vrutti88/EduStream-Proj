import os
import sqlite3
import datetime
from werkzeug.security import generate_password_hash

from config import DB_PATH, UPLOAD_DIR

DB = DB_PATH


def get_db():
    conn = sqlite3.connect(
        DB,
        timeout=30
    )
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
    return conn


def _table_exists(conn, name):
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone()
    return row is not None


def _migrate_legacy(conn):
    if not _table_exists(conn, 'courses'):
        return
    if _table_exists(conn, 'users'):
        return
    if not _table_exists(conn, 'classes'):
        return
    try:
        conn.executescript('''
            ALTER TABLE courses RENAME TO courses_legacy;
            ALTER TABLE classes RENAME TO classes_legacy;
            ALTER TABLE enrollments RENAME TO enrollments_legacy;
            ALTER TABLE attendance RENAME TO attendance_legacy;
        ''')
    except sqlite3.OperationalError:
        pass


def init_db():
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    conn = get_db()
    _migrate_legacy(conn)

    conn.executescript('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            name TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('admin', 'teacher', 'student')),
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS courses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            course_code TEXT UNIQUE NOT NULL,
            description TEXT,
            instructor_id INTEGER NOT NULL,
            category TEXT,
            thumbnail TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (instructor_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS enrollments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            course_id INTEGER NOT NULL,
            student_id INTEGER NOT NULL,
            enrolled_at TEXT NOT NULL,
            UNIQUE(course_id, student_id),
            FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE CASCADE,
            FOREIGN KEY (student_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            course_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            instructor_id INTEGER NOT NULL,
            session_date TEXT NOT NULL,
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL,
            meeting_link TEXT,
            status TEXT DEFAULT 'scheduled',
            FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE CASCADE,
            FOREIGN KEY (instructor_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            course_id INTEGER NOT NULL,
            session_id INTEGER NOT NULL,
            join_time TEXT,
            status TEXT DEFAULT 'present',
            UNIQUE(session_id, student_id),
            FOREIGN KEY (student_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE CASCADE,
            FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS announcements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            course_id INTEGER NOT NULL,
            author_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE CASCADE,
            FOREIGN KEY (author_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS materials (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            course_id INTEGER NOT NULL,
            uploaded_by INTEGER NOT NULL,
            filename TEXT NOT NULL,
            original_name TEXT NOT NULL,
            file_type TEXT NOT NULL,
            file_size INTEGER,
            uploaded_at TEXT NOT NULL,
            FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE CASCADE,
            FOREIGN KEY (uploaded_by) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            type TEXT NOT NULL,
            title TEXT NOT NULL,
            message TEXT NOT NULL,
            is_read INTEGER DEFAULT 0,
            created_at TEXT NOT NULL,
            related_id INTEGER,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );
    ''')

    _seed_defaults(conn)
    conn.commit()
    conn.close()


def _seed_defaults(conn):
    now = datetime.datetime.utcnow().isoformat()
    defaults = [
        ('admin@edustream.edu', 'Platform Admin', 'admin', 'Admin@123'),
        ('teacher@edustream.edu', 'Dr. Sarah Chen', 'teacher', 'Teacher@123'),
        ('student@edustream.edu', 'Alex Johnson', 'student', 'Student@123'),
    ]
    for email, name, role, password in defaults:
        existing = conn.execute('SELECT id FROM users WHERE email=?', (email,)).fetchone()
        if not existing:
            conn.execute(
                'INSERT INTO users (email, password_hash, name, role, created_at) VALUES (?,?,?,?,?)',
                (email, generate_password_hash(password), name, role, now)
            )

    teacher = conn.execute(
        "SELECT id FROM users WHERE email='teacher@edustream.edu'"
    ).fetchone()
    if teacher and conn.execute('SELECT COUNT(*) FROM courses').fetchone()[0] == 0:
        conn.execute(
            '''INSERT INTO courses (title, course_code, description, instructor_id, category, created_at)
               VALUES (?,?,?,?,?,?)''',
            ('Introduction to Computer Science', 'CS101', 'Fundamentals of programming and algorithms',
             teacher['id'], 'Technology', now)
        )
        course_id = conn.execute('SELECT last_insert_rowid()').fetchone()[0]
        student = conn.execute(
            "SELECT id FROM users WHERE email='student@edustream.edu'"
        ).fetchone()
        if student:
            conn.execute(
                'INSERT INTO enrollments (course_id, student_id, enrolled_at) VALUES (?,?,?)',
                (course_id, student['id'], now)
            )
