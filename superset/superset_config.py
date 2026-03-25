import os

# ── Database ──────────────────────────────────────────────────────────────────
# Superset's own metadata (users, dashboards, charts) stored in PostgreSQL
SQLALCHEMY_DATABASE_URI = os.environ.get(
    "SUPERSET_DB_URI",
    "postgresql+psycopg2://postgres:postgres@postgres:5432/superset_meta"
)

# ── Security ───────────────────────────────────────────────────────────────────
SECRET_KEY = os.environ.get("SUPERSET_SECRET_KEY", "analyst-superset-secret-change-in-prod")

# ── Allow embedding via iframe ─────────────────────────────────────────────────
WTF_CSRF_ENABLED = False
TALISMAN_ENABLED = False  # Disable HTTPS enforcement for local dev
PREVENT_UNSAFE_DB_CONNECTIONS = False  # Allow SQLite connections

# Allow guest tokens for embedding
GUEST_ROLE_NAME = "Gamma"
GUEST_TOKEN_JWT_SECRET = "analyst-superset-guest-token-secret"
GUEST_TOKEN_JWT_ALGO = "HS256"

# Grant Public role Admin permissions (Hammer for Dev)
PUBLIC_ROLE_LIKE = "Admin"
AUTH_ROLE_PUBLIC = "Admin"
CONTENT_SECURITY_POLICY_WARNING = False

# Session settings for cross-origin embedding
SESSION_COOKIE_SAMESITE = "None"
SESSION_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True

# CORS for local dev
ENABLE_CORS = True
# Allow iframes from our frontend origin
HTTP_HEADERS = {"X-Frame-Options": "ALLOWALL"}

# Enable guest token API for embedded dashboards
FEATURE_FLAGS = {
    "EMBEDDED_SUPERSET": True,
    "ALERT_REPORTS": False,
}

# ── CORS ───────────────────────────────────────────────────────────────────────
ENABLE_CORS = True
CORS_OPTIONS = {
    "supports_credentials": True,
    "allow_headers": ["*"],
    "resources": ["*"],
    "origins": ["http://localhost:8002", "http://localhost:3000"],
}

# ── Cache ───────────────────────────────────────────────────────────────────────
CACHE_CONFIG = {
    "CACHE_TYPE": "SimpleCache",
    "CACHE_DEFAULT_TIMEOUT": 300,
}

# ── Upload limits ─────────────────────────────────────────────────────────────
UPLOAD_FOLDER = "/tmp/superset_uploads"
IMG_UPLOAD_FOLDER = "/tmp/superset_uploads"
# ── Final Hacks for API Stability ──────────────────────────────
def FLASK_APP_MUTATOR(app):
    from flask import g, request
    
    @app.before_request
    def force_user_context():
        # If we are in an API call and the user is anonymous, try to force 'admin' context
        # to avoid the 'AnonymousUserMixin' object has no attribute '_sa_instance_state' error
        if request.path.startswith('/api/v1/') and hasattr(g, 'user') and g.user.is_anonymous:
            from superset.extensions import security_manager
            admin = security_manager.find_user(username='admin')
            if admin:
                g.user = admin
