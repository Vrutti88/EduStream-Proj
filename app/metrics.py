from prometheus_client import Gauge, Counter

ACTIVE_SESSIONS = Gauge('edustream_active_sessions', 'Number of live sessions')
ACTIVE_USERS = Gauge('edustream_active_users', 'Total registered users')
ATTENDANCE_REQUESTS = Counter('edustream_attendance_requests_total', 'Total attendance join requests')
API_REQUESTS = Counter('edustream_api_requests_total', 'Total API requests', ['method', 'endpoint'])
