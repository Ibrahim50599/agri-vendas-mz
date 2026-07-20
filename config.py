import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'agri_vendas_mz_secret_key_2024'
    UPLOAD_FOLDER = 'static/uploads'
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB
    DATABASE = 'agri_vendas.db'
    DEBUG = os.environ.get('DEBUG') == 'True'
    HOST = os.environ.get('HOST') or '0.0.0.0'
    PORT = int(os.environ.get('PORT') or 5000)

    # Sessão — funciona atrás de qualquer proxy (Render, Railway, Heroku, etc.)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    # Secure só activo quando HTTPS está confirmado (em produção via env var)
    SESSION_COOKIE_SECURE = os.environ.get('HTTPS_ENABLED') == 'true'
    PERMANENT_SESSION_LIFETIME = 60 * 60 * 24 * 7  # 7 dias
