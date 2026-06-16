import os
import datetime
import mysql.connector
from mysql.connector import pooling
from werkzeug.security import generate_password_hash

from config import (
    MYSQL_HOST, MYSQL_PORT, MYSQL_USER,
    MYSQL_PASSWORD, MYSQL_DATABASE, UPLOAD_DIR
)

_pool = None


def _get_pool():
    global _pool
    if _pool is None:
        _pool = pooling.MySQLConnectionPool(
            pool_name="edustream_pool",
            pool_size=3,
            host=MYSQL_HOST,
            port=MYSQL_PORT,
            user=MYSQL_USER,
            password=MYSQL_PASSWORD,
            database=MYSQL_DATABASE,
            autocommit=False,
        )
    return _pool


class _CursorWrapper:
    """Wraps a MySQL dictionary cursor to mimic sqlite3's row access style."""

    def __init__(self, cursor):
        self._cursor = cursor

    def execute(self, sql, params=None):
        self._cursor.execute(sql, params or ())
        return self

    def executemany(self, sql, params):
        self._cursor.executemany(sql, params)
        return self

    def fetchone(self):
        return self._cursor.fetchone()

    def fetchall(self):
        return self._cursor.fetchall()

    @property
    def lastrowid(self):
        return self._cursor.lastrowid

    @property
    def rowcount(self):
        return self._cursor.rowcount

    def __iter__(self):
        return iter(self._cursor.fetchall())

    def close(self):
        self._cursor.close()


class _ConnectionWrapper:
    """Wraps a MySQL connection to mimic the sqlite3 connection API used in routes."""

    def __init__(self, conn):
        self._conn = conn
        self._cursor = conn.cursor(dictionary=True)
        self._wrapper = _CursorWrapper(self._cursor)

    def execute(self, sql, params=None):
        self._wrapper.execute(sql, params)
        return self._wrapper

    def executescript(self, script):
        # executescript is only called in init_db which we handle differently
        for statement in script.strip().split(';'):
            s = statement.strip()
            if s:
                self._cursor.execute(s)

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        # print("Closing DB connection")
        self._cursor.close()
        self._conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self.rollback()
        else:
            self.commit()
        self.close()


def get_db():
    # print("Getting DB connection")
    conn = _get_pool().get_connection()
    return _ConnectionWrapper(conn)


def init_db():
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    raw_conn = _get_pool().get_connection()
    cursor = raw_conn.cursor(dictionary=True)

    statements = [
        '''CREATE TABLE IF NOT EXISTS users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            email VARCHAR(255) UNIQUE NOT NULL,
            password_hash VARCHAR(255) NOT NULL,
            name VARCHAR(255) NOT NULL,
            role ENUM('admin', 'teacher', 'student') NOT NULL,
            created_at VARCHAR(50) NOT NULL
        )''',
        '''CREATE TABLE IF NOT EXISTS courses (
            id INT AUTO_INCREMENT PRIMARY KEY,
            title VARCHAR(255) NOT NULL,
            course_code VARCHAR(100) UNIQUE NOT NULL,
            description TEXT,
            instructor_id INT NOT NULL,
            category VARCHAR(100),
            thumbnail VARCHAR(255),
            created_at VARCHAR(50) NOT NULL,
            FOREIGN KEY (instructor_id) REFERENCES users(id)
        )''',
        '''CREATE TABLE IF NOT EXISTS enrollments (
            id INT AUTO_INCREMENT PRIMARY KEY,
            course_id INT NOT NULL,
            student_id INT NOT NULL,
            enrolled_at VARCHAR(50) NOT NULL,
            UNIQUE KEY uq_enrollment (course_id, student_id),
            FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE CASCADE,
            FOREIGN KEY (student_id) REFERENCES users(id) ON DELETE CASCADE
        )''',
        '''CREATE TABLE IF NOT EXISTS sessions (
            id INT AUTO_INCREMENT PRIMARY KEY,
            course_id INT NOT NULL,
            title VARCHAR(255) NOT NULL,
            description TEXT,
            instructor_id INT NOT NULL,
            session_date VARCHAR(50) NOT NULL,
            start_time VARCHAR(50) NOT NULL,
            end_time VARCHAR(50) NOT NULL,
            meeting_link VARCHAR(500),
            status VARCHAR(50) DEFAULT 'scheduled',
            FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE CASCADE,
            FOREIGN KEY (instructor_id) REFERENCES users(id)
        )''',
        '''CREATE TABLE IF NOT EXISTS attendance (
            id INT AUTO_INCREMENT PRIMARY KEY,
            student_id INT NOT NULL,
            course_id INT NOT NULL,
            session_id INT NOT NULL,
            join_time VARCHAR(50),
            status VARCHAR(50) DEFAULT 'present',
            UNIQUE KEY uq_attendance (session_id, student_id),
            FOREIGN KEY (student_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE CASCADE,
            FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
        )''',
        '''CREATE TABLE IF NOT EXISTS announcements (
            id INT AUTO_INCREMENT PRIMARY KEY,
            course_id INT NOT NULL,
            author_id INT NOT NULL,
            title VARCHAR(255) NOT NULL,
            content TEXT NOT NULL,
            created_at VARCHAR(50) NOT NULL,
            FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE CASCADE,
            FOREIGN KEY (author_id) REFERENCES users(id)
        )''',
        '''CREATE TABLE IF NOT EXISTS materials (
            id INT AUTO_INCREMENT PRIMARY KEY,
            course_id INT NOT NULL,
            uploaded_by INT NOT NULL,
            filename VARCHAR(255) NOT NULL,
            original_name VARCHAR(255) NOT NULL,
            file_type VARCHAR(100) NOT NULL,
            file_size INT,
            uploaded_at VARCHAR(50) NOT NULL,
            FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE CASCADE,
            FOREIGN KEY (uploaded_by) REFERENCES users(id)
        )''',
        '''CREATE TABLE IF NOT EXISTS notifications (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            type VARCHAR(100) NOT NULL,
            title VARCHAR(255) NOT NULL,
            message TEXT NOT NULL,
            is_read TINYINT(1) DEFAULT 0,
            created_at VARCHAR(50) NOT NULL,
            related_id INT,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )''',
    ]

    for stmt in statements:
        cursor.execute(stmt)
    raw_conn.commit()

    _seed_defaults(raw_conn, cursor)
    cursor.close()
    raw_conn.close()


def _seed_defaults(conn, cursor):
    now = datetime.datetime.utcnow().isoformat()
    defaults = [
        ('admin@edustream.edu', 'Platform Admin', 'admin', 'Admin@123'),
        ('teacher@edustream.edu', 'Dr. Sarah Chen', 'teacher', 'Teacher@123'),
        ('student@edustream.edu', 'Alex Johnson', 'student', 'Student@123'),
    ]
    for email, name, role, password in defaults:
        cursor.execute('SELECT id FROM users WHERE email=%s', (email,))
        if not cursor.fetchone():
            cursor.execute(
                'INSERT INTO users (email, password_hash, name, role, created_at) VALUES (%s,%s,%s,%s,%s)',
                (email, generate_password_hash(password), name, role, now)
            )

    cursor.execute("SELECT id FROM users WHERE email='teacher@edustream.edu'")
    teacher = cursor.fetchone()
    cursor.execute('SELECT COUNT(*) as cnt FROM courses')
    count = cursor.fetchone()['cnt']
    if teacher and count == 0:
        cursor.execute(
            '''INSERT INTO courses (title, course_code, description, instructor_id, category, created_at)
               VALUES (%s,%s,%s,%s,%s,%s)''',
            ('Introduction to Computer Science', 'CS101',
             'Fundamentals of programming and algorithms',
             teacher['id'], 'Technology', now)
        )
        course_id = cursor.lastrowid
        cursor.execute("SELECT id FROM users WHERE email='student@edustream.edu'")
        student = cursor.fetchone()
        if student:
            cursor.execute(
                'INSERT INTO enrollments (course_id, student_id, enrolled_at) VALUES (%s,%s,%s)',
                (course_id, student['id'], now)
            )
    conn.commit()
