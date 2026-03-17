import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'agri_vendas_mz_secret_key_2024'
    UPLOAD_FOLDER = 'static/uploads'
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB
    DATABASE = 'agri_vendas.db'
    DEBUG = os.environ.get('DEBUG') == 'True'
    HOST = os.environ.get('HOST') or '0.0.0.0'
    PORT = int(os.environ.get('PORT') or 5000)