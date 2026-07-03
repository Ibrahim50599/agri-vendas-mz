import os
import secrets
from dotenv import load_dotenv

load_dotenv()

class Config:
    """Configuration class for AGRI.vendas application"""
    
    # Flask
    FLASK_ENV = os.environ.get('FLASK_ENV', 'development')
    SECRET_KEY = os.environ.get('SECRET_KEY') or secrets.token_urlsafe(32)
    DEBUG = os.environ.get('DEBUG', 'False').lower() == 'true'
    
    # Database
    DATABASE = os.environ.get('DATABASE', 'agri_vendas.db')
    
    # Upload
    UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER', 'static/uploads')
    MAX_CONTENT_LENGTH = int(os.environ.get('MAX_CONTENT_LENGTH', 16 * 1024 * 1024))  # 16MB
    
    # Server
    HOST = os.environ.get('HOST', '0.0.0.0')
    PORT = int(os.environ.get('PORT', 5000))
    
    # Google GenAI (Consultoria IA)
    GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
    
    # Security
    SESSION_TIMEOUT = int(os.environ.get('SESSION_TIMEOUT', 3600))
    
    @classmethod
    def init_app(cls, app):
        """Initialize configuration for Flask app"""
        app.config['SECRET_KEY'] = cls.SECRET_KEY
        app.config['MAX_CONTENT_LENGTH'] = cls.MAX_CONTENT_LENGTH
        app.config['UPLOAD_FOLDER'] = cls.UPLOAD_FOLDER


class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    TESTING = False


class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    TESTING = False


class TestingConfig(Config):
    """Testing configuration"""
    DEBUG = True
    TESTING = True
    DATABASE = ':memory:'


config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}
