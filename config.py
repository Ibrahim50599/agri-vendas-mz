import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'agri_vendas_mz_secret_key_2024'

    # DATA_DIR: em produção (Render, Railway, etc.) aponta para disco persistente.
    # Exemplo: DATA_DIR=/data  → base de dados em /data/agri_vendas.db
    # Em desenvolvimento fica vazio e usa a pasta local.
    _DATA_DIR = os.environ.get('DATA_DIR', '').strip()
    DATABASE = os.path.join(_DATA_DIR, 'agri_vendas.db') if _DATA_DIR else 'agri_vendas.db'

    # Pasta de uploads — sempre dentro de static/ para o Flask servir os ficheiros.
    # Em produção, montar o disco também em static/uploads/ resolve a persistência das imagens.
    UPLOAD_FOLDER = 'static/uploads'

    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB
    DEBUG = os.environ.get('DEBUG') == 'True'
    HOST = os.environ.get('HOST') or '0.0.0.0'
    PORT = int(os.environ.get('PORT') or 5000)

    # Sessão — funciona atrás de qualquer proxy (Render, Railway, Heroku, etc.)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    SESSION_COOKIE_SECURE = os.environ.get('HTTPS_ENABLED') == 'true'
    PERMANENT_SESSION_LIFETIME = 60 * 60 * 24 * 7  # 7 dias
