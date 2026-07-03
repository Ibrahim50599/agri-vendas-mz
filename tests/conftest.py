import pytest
import os
from models import Database

@pytest.fixture
def db():
    """Create test database"""
    test_db = Database(':memory:')
    test_db.init_db()
    yield test_db

@pytest.fixture
def app():
    """Create Flask app for testing"""
    from routes import app
    app.config['TESTING'] = True
    return app

@pytest.fixture
def client(app):
    """Create test client"""
    return app.test_client()
