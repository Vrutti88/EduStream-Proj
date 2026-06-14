import datetime


def parse_datetime(value):
    if not value:
        return None
    cleaned = value.replace('Z', '').strip()
    try:
        return datetime.datetime.fromisoformat(cleaned)
    except ValueError:
        pass
    for fmt in ('%Y-%m-%dT%H:%M:%S', '%Y-%m-%dT%H:%M', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M'):
        try:
            return datetime.datetime.strptime(cleaned[:19], fmt)
        except ValueError:
            continue
    return None


def combine_date_time(session_date, time_str):
    date_part = session_date[:10] if session_date else ''
    time_part = time_str[:5] if time_str else '00:00'
    return parse_datetime(f'{date_part}T{time_part}')


def compute_session_status(session, now=None):
    if session['status'] == 'cancelled':
        return 'cancelled'
    now = now or datetime.datetime.utcnow()
    start = combine_date_time(session['session_date'], session['start_time'])
    end = combine_date_time(session['session_date'], session['end_time'])
    if not start or not end:
        return session['status'] or 'scheduled'
    if session['status'] == 'live':
        return 'live'

    if session['status'] == 'completed':
        return 'completed'

    if session['status'] == 'cancelled':
        return 'cancelled'

    if now < start:
        return 'scheduled'

    if start <= now <= end:
        return 'live'

    return 'completed'


def sync_session_status(conn, session_id):
    row = conn.execute('SELECT * FROM sessions WHERE id=?', (session_id,)).fetchone()
    if not row:
        return None
    session = dict(row)
    if session['status'] == 'cancelled':
        return session
    effective = compute_session_status(session)
    if effective != session['status']:
        conn.execute('UPDATE sessions SET status=? WHERE id=?', (effective, session_id))
        session['status'] = effective
    return session


def sync_all_sessions(conn):
    rows = conn.execute('SELECT id FROM sessions WHERE status != ?', ('cancelled',)).fetchall()
    for row in rows:
        sync_session_status(conn, row['id'])


def can_join_session(session, now=None):
    if session['status'] == 'cancelled':
        return False, 'Session has been cancelled'
    
    if session['status'] == 'live':
        return True, None

    if session['status'] == 'completed':
        return False, 'Session has ended'
    
    if session['status'] == 'scheduled':
        return False, 'Session has not started yet'

    return False, 'Session not started'


def session_to_dict(row):
    session = dict(row)
    session['effective_status'] = compute_session_status(session)
    session['can_join'] = can_join_session(session)[0]
    return session
