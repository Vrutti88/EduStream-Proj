import datetime


def create_notification(conn, user_id, ntype, title, message, related_id=None):
    conn.execute(
        '''INSERT INTO notifications (user_id, type, title, message, is_read, created_at, related_id)
           VALUES (?,?,?,?,0,?,?)''',
        (user_id, ntype, title, message, datetime.datetime.utcnow().isoformat(), related_id)
    )


def notify_course_students(conn, course_id, ntype, title, message, related_id=None, exclude_user_id=None):
    rows = conn.execute(
        'SELECT student_id FROM enrollments WHERE course_id=?', (course_id,)
    ).fetchall()
    for row in rows:
        if exclude_user_id and row['student_id'] == exclude_user_id:
            continue
        create_notification(conn, row['student_id'], ntype, title, message, related_id)
