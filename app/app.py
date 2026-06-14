import datetime
from flask import Flask, jsonify
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from prometheus_flask_exporter import PrometheusMetrics
import db
import metrics
from config import SECRET_KEY, MAX_CONTENT_LENGTH
from routes.auth import auth_bp
from routes.courses import courses_bp
from routes.sessions import sessions_bp
from routes.enrollments import enrollments_bp
from routes.attendance import attendance_bp
from routes.materials import materials_bp
from routes.announcements import announcements_bp
from routes.notifications import notifications_bp
from routes.admin import admin_bp
from routes.analytics import analytics_bp
from routes.legacy import legacy_bp
from routes.pages import pages_bp
from services.sessions import sync_all_sessions
from routes.demo_routes import demo_bp

def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = SECRET_KEY
    app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH

    CORS(app, origins=['*'], supports_credentials=True)
    Limiter(get_remote_address, app=app, default_limits=['200 per minute'], storage_uri='memory://')
    PrometheusMetrics(app)

    app.register_blueprint(pages_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(courses_bp)
    app.register_blueprint(sessions_bp)
    app.register_blueprint(enrollments_bp)
    app.register_blueprint(attendance_bp)
    app.register_blueprint(materials_bp)
    app.register_blueprint(announcements_bp)
    app.register_blueprint(notifications_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(analytics_bp)
    app.register_blueprint(legacy_bp)
    app.register_blueprint(demo_bp)

    @app.before_request
    def track_metrics():
        from flask import request
        if request.path.startswith('/api/'):
            metrics.API_REQUESTS.labels(method=request.method, endpoint=request.path).inc()

    @app.after_request
    def refresh_gauges(response):
        try:
            conn = db.get_db()
            sync_all_sessions(conn)
            conn.commit()
            metrics.ACTIVE_SESSIONS.set(
                conn.execute("SELECT COUNT(*) FROM sessions WHERE status='live'").fetchone()[0]
            )
            metrics.ACTIVE_USERS.set(conn.execute('SELECT COUNT(*) FROM users').fetchone()[0])
            conn.close()
        except Exception:
            pass
        return response

    @app.route('/health')
    def health():
        return jsonify(status='healthy', time=datetime.datetime.utcnow().isoformat())

    db.init_db()
    return app


app = create_app()
db.DB = db.DB_PATH

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)
