import os
from urllib.parse import urlparse
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Config:
    """Base application configuration."""
    SECRET_KEY = os.getenv('SECRET_KEY', 'default-dev-secret-key-12345')
    
    # Check for DATABASE_URL / MYSQL_URL connection strings
    db_url = os.getenv('MYSQL_URL') or os.getenv('DATABASE_URL')
    if db_url and db_url.startswith(('mysql://', 'mysql+pymysql://')):
        parsed = urlparse(db_url)
        DB_HOST = parsed.hostname or '127.0.0.1'
        DB_PORT = parsed.port or 3306
        DB_USER = parsed.username or 'root'
        DB_PASSWORD = parsed.password or ''
        DB_NAME = parsed.path.lstrip('/') or 'library_db'
    else:
        # Standard individual environment variables
        DB_HOST = os.getenv('DB_HOST', '127.0.0.1')
        DB_PORT = int(os.getenv('DB_PORT', 3306))
        DB_USER = os.getenv('DB_USER', 'root')
        DB_PASSWORD = os.getenv('DB_PASSWORD', '')
        DB_NAME = os.getenv('DB_NAME', 'library_db')

    DB_SSL_REQUIRED = os.getenv('DB_SSL_REQUIRED', '0') == '1'
    
    # Session security
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    PERMANENT_SESSION_LIFETIME = 3600 * 4  # 4 hours
