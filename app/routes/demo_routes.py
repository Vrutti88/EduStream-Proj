from flask import Blueprint, jsonify
from werkzeug.security import generate_password_hash

from db import get_db

import datetime
# import random

demo_bp = Blueprint('demo', __name__)


@demo_bp.route('/api/demo/seed', methods=['POST'])
def seed_demo_data():

    conn = get_db()

    now = datetime.datetime.utcnow().isoformat()

    # --------------------------------------------------
    # FIND TEACHER
    # --------------------------------------------------

    teacher = conn.execute(
        """
        SELECT id
        FROM users
        WHERE role='teacher'
        LIMIT 1
        """
    ).fetchone()

    if not teacher:
        conn.close()
        return jsonify(error='Teacher not found'), 400

    teacher_id = teacher['id']

    # --------------------------------------------------
    # STUDENTS
    # --------------------------------------------------

    students = [
        ('John Doe', 'john@test.com'),
        ('Alice Smith', 'alice@test.com'),
        ('Bob Johnson', 'bob@test.com'),
        ('Emma Wilson', 'emma@test.com'),
        ('David Brown', 'david@test.com'),
        ('Sophia Davis', 'sophia@test.com'),
        ('Michael Lee', 'michael@test.com'),
        ('Sarah White', 'sarah@test.com'),
        ('Chris Taylor', 'chris@test.com'),
        ('Olivia Martin', 'olivia@test.com')
    ]

    for name, email in students:

        existing = conn.execute(
            """
            SELECT id
            FROM users
            WHERE email=?
            """,
            (email,)
        ).fetchone()

        if not existing:

            conn.execute(
                """
                INSERT INTO users
                (
                    email,
                    password_hash,
                    name,
                    role,
                    created_at
                )
                VALUES (?,?,?,?,?)
                """,
                (
                    email,
                    generate_password_hash('Student@123'),
                    name,
                    'student',
                    now
                )
            )

    conn.commit()

    # --------------------------------------------------
    # COURSES
    # --------------------------------------------------

    courses = [
        ('Python Programming', 'PY101', 'Programming'),
        ('Database Management', 'DB101', 'Database'),
        ('Cloud Computing', 'CC101', 'Cloud'),
        ('DevOps Engineering', 'DEV101', 'DevOps'),
        ('Machine Learning', 'ML101', 'AI')
    ]

    course_ids = []

    for title, code, category in courses:

        course = conn.execute(
            """
            SELECT id
            FROM courses
            WHERE course_code=?
            """,
            (code,)
        ).fetchone()

        if course:

            course_ids.append(course['id'])

        else:

            conn.execute(
                """
                INSERT INTO courses
                (
                    title,
                    course_code,
                    description,
                    instructor_id,
                    category,
                    created_at
                )
                VALUES (?,?,?,?,?,?)
                """,
                (
                    title,
                    code,
                    f'{title} complete course',
                    teacher_id,
                    category,
                    now
                )
            )

            course_ids.append(
                conn.execute(
                    "SELECT last_insert_rowid()"
                ).fetchone()[0]
            )

    conn.commit()

    # --------------------------------------------------
    # ENROLLMENTS
    # --------------------------------------------------

    students = conn.execute(
        """
        SELECT id
        FROM users
        WHERE role='student'
        """
    ).fetchall()

    for course_id in course_ids:

        for student in students:

            conn.execute(
                """
                INSERT OR IGNORE INTO enrollments
                (
                    course_id,
                    student_id,
                    enrolled_at
                )
                VALUES (?,?,?)
                """,
                (
                    course_id,
                    student['id'],
                    now
                )
            )

    conn.commit()

    # --------------------------------------------------
    # SESSIONS
    # --------------------------------------------------

    today = datetime.date.today()

    for course_id in course_ids:

        # COMPLETED SESSIONS

        for i in range(3):

            date = today - datetime.timedelta(days=i + 1)

            conn.execute(
                """
                INSERT INTO sessions
                (
                    course_id,
                    title,
                    description,
                    instructor_id,
                    session_date,
                    start_time,
                    end_time,
                    meeting_link,
                    status
                )
                VALUES
                (
                    ?,?,?,?,?,?,?,?,?
                )
                """,
                (
                    course_id,
                    f'Completed Lecture {i+1}',
                    'Completed Session',
                    teacher_id,
                    date.strftime('%Y-%m-%d'),
                    '10:00',
                    '11:00',
                    'https://meet.google.com/demo',
                    'completed'
                )
            )

        # LIVE SESSION

        conn.execute(
            """
            INSERT INTO sessions
            (
                course_id,
                title,
                description,
                instructor_id,
                session_date,
                start_time,
                end_time,
                meeting_link,
                status
            )
            VALUES
            (
                ?,?,?,?,?,?,?,?,?
            )
            """,
            (
                course_id,
                'Live Lecture',
                'Live Session',
                teacher_id,
                today.strftime('%Y-%m-%d'),
                '10:00',
                '11:00',
                'https://meet.google.com/demo',
                'live'
            )
        )

        # UPCOMING SESSION

        future = today + datetime.timedelta(days=2)

        conn.execute(
            """
            INSERT INTO sessions
            (
                course_id,
                title,
                description,
                instructor_id,
                session_date,
                start_time,
                end_time,
                meeting_link,
                status
            )
            VALUES
            (
                ?,?,?,?,?,?,?,?,?
            )
            """,
            (
                course_id,
                'Upcoming Lecture',
                'Scheduled Session',
                teacher_id,
                future.strftime('%Y-%m-%d'),
                '10:00',
                '11:00',
                'https://meet.google.com/demo',
                'scheduled'
            )
        )

    conn.commit()

    # --------------------------------------------------
    # ATTENDANCE
    # --------------------------------------------------

    sessions = conn.execute("""
    SELECT *
    FROM sessions
    WHERE status='completed'
    ORDER BY id
    """).fetchall()

    attendance_patterns = [
        [0,1,2,3,4,5,6,7],
        [1,2,3,4,5,6,7,8],
        [0,2,4,5,6,8,9],
        [0,1,3,4,6,7,8],
        [1,2,4,5,7,8,9],
    ]

    for index, session in enumerate(sessions):

        students = conn.execute("""
        SELECT student_id
        FROM enrollments
        WHERE course_id=?
        ORDER BY student_id
        """, (session['course_id'],)).fetchall()

        student_ids = [s['student_id'] for s in students]

        pattern = attendance_patterns[index % len(attendance_patterns)]

        for pos in pattern:

            if pos < len(student_ids):

                conn.execute("""
                INSERT OR IGNORE INTO attendance
                (
                    student_id,
                    course_id,
                    session_id,
                    join_time,
                    status
                )
                VALUES (?,?,?,?,?)
                """, (
                    student_ids[pos],
                    session['course_id'],
                    session['id'],
                    now,
                    'present'
                ))

    # conn.commit()

    # --------------------------------------------------
    # ANNOUNCEMENTS
    # --------------------------------------------------

    for course_id in course_ids:

        conn.execute(
            """
            INSERT INTO announcements
            (
                course_id,
                author_id,
                title,
                content,
                created_at
            )
            VALUES
            (
                ?,?,?,?,?
            )
            """,
            (
                course_id,
                teacher_id,
                'Welcome',
                'Welcome to the course.',
                now
            )
        )

    conn.commit()

    conn.close()

    return jsonify(
        success=True,
        message='Demo data generated successfully'
    )