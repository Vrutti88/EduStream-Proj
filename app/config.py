import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.environ.get('UPLOAD_DIR', os.path.join(BASE_DIR, 'uploads'))
SECRET_KEY = os.environ.get('SECRET_KEY', 'edustream-dev-secret-change-in-production')
JWT_EXPIRY_HOURS = int(os.environ.get('JWT_EXPIRY_HOURS', '24'))
ALLOWED_EXTENSIONS = {'pdf', 'ppt', 'pptx', 'doc', 'docx'}
MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB

# MySQL connection settings
MYSQL_HOST = os.environ.get('MYSQL_HOST', 'edustream-db.clc8o48041xi.ap-south-1.rds.amazonaws.com')
MYSQL_PORT = int(os.environ.get('MYSQL_PORT', '3306'))
MYSQL_USER = os.environ.get('MYSQL_USER', 'edustream_admin')
MYSQL_PASSWORD = os.environ.get('MYSQL_PASSWORD', 'edustream123')
MYSQL_DATABASE = os.environ.get('MYSQL_DATABASE', 'edustream_db')
