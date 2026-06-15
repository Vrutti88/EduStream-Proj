import datetime
from flask import Blueprint, jsonify, g

from db import get_db
from auth_utils import login_required

notifications_bp = Blueprint('notifications', __name__)


@notifications_bp.route('/api/notifications', methods=['GET'])
@login_required
def list_notifications():
    conn = get_db()
    rows = conn.execute(
        'SELECT * FROM notifications WHERE user_id=%s ORDER BY created_at DESC LIMIT 50',
        (g.user['id'],)
    ).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@notifications_bp.route('/api/notifications/unread-count', methods=['GET'])
@login_required
def unread_count():
    conn = get_db()
    count = conn.execute(
        'SELECT COUNT(*) AS cnt FROM notifications WHERE user_id=%s AND is_read=0',
        (g.user['id'],)
    ).fetchone()['cnt']
    conn.close()
    return jsonify(count=count)


@notifications_bp.route('/api/notifications/<int:notif_id>/read', methods=['POST'])
@login_required
def mark_read(notif_id):
    conn = get_db()
    conn.execute(
        'UPDATE notifications SET is_read=1 WHERE id=%s AND user_id=%s',
        (notif_id, g.user['id'])
    )
    conn.commit()
    conn.close()
    return jsonify(message='Marked as read')


@notifications_bp.route('/api/notifications/read-all', methods=['POST'])
@login_required
def mark_all_read():
    conn = get_db()
    conn.execute(
        'UPDATE notifications SET is_read=1 WHERE user_id=%s',
        (g.user['id'],)
    )
    conn.commit()
    conn.close()
    return jsonify(message='All notifications marked as read')
