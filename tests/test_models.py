import pytest
from models import Database

class TestDatabase:
    """Test Database class"""
    
    def test_database_initialization(self, db):
        """Test database initialization"""
        assert db is not None
        assert db.db_path == ':memory:'
    
    def test_get_connection(self, db):
        """Test database connection"""
        conn = db.get_connection()
        assert conn is not None
        conn.close()
    
    def test_create_user(self, db):
        """Test user creation"""
        db.create_user('Test User', 'test@example.com', '258828123456', 'password123', 'vendedor')
        user = db.get_user_by_credentials('test@example.com', 'password123')
        assert user is not None
        assert user['nome_completo'] == 'Test User'
    
    def test_get_user_by_id(self, db):
        """Test getting user by ID"""
        db.create_user('Test User', 'test@example.com', '258828123456', 'password123', 'vendedor')
        user = db.get_user_by_id(1)
        assert user is not None
    
    def test_create_product(self, db):
        """Test product creation"""
        db.create_user('Vendor', 'vendor@example.com', '258828123456', 'pass123', 'vendedor')
        db.create_product(1, 'Milho', 250.00, 'Milho de qualidade', 'Maputo', 'url', 'cereais')
        products = db.get_user_products(1)
        assert len(products) > 0
        assert products[0]['nome'] == 'Milho'
    
    def test_get_products(self, db):
        """Test getting all products"""
        db.create_user('Vendor', 'vendor@example.com', '258828123456', 'pass123', 'vendedor')
        db.create_product(1, 'Milho', 250.00, 'Milho', 'Maputo', 'url', 'cereais')
        products = db.get_products()
        assert len(products) > 0
    
    def test_get_stats(self, db):
        """Test statistics"""
        stats = db.get_stats()
        assert 'total_usuarios' in stats
        assert 'total_produtos' in stats
        assert stats['total_usuarios'] >= 1  # Admin user
    
    def test_filter_products(self, db):
        """Test product filtering"""
        db.create_user('Vendor', 'vendor@example.com', '258828123456', 'pass123', 'vendedor')
        db.create_product(1, 'Milho', 250.00, 'Milho', 'Maputo', 'url', 'cereais')
        db.create_product(1, 'Arroz', 300.00, 'Arroz', 'Maputo', 'url', 'cereais')
        
        products = db.get_filtered_products(categoria='cereais')
        assert len(products) == 2
        
        products = db.get_filtered_products(preco_max=275)
        assert len(products) == 1
    
    def test_premium_activation(self, db):
        """Test premium activation"""
        db.create_user('Premium User', 'premium@example.com', '258828123456', 'pass123', 'vendedor')
        db.activate_premium(2)  # ID 2 (after admin)
        users = db.get_users()
        premium_user = [u for u in users if u['premium'] == 1]
        assert len(premium_user) > 0
