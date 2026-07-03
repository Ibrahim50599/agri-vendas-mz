import pytest
import json

class TestAuthRoutes:
    """Test authentication routes"""
    
    def test_login_page(self, client):
        """Test login page access"""
        response = client.get('/login')
        assert response.status_code == 200
    
    def test_register_page(self, client):
        """Test registration page access"""
        response = client.get('/cadastro')
        assert response.status_code == 200
    
    def test_homepage(self, client):
        """Test homepage access"""
        response = client.get('/')
        assert response.status_code == 200

class TestProductRoutes:
    """Test product routes"""
    
    def test_products_page(self, client):
        """Test products listing page"""
        response = client.get('/produtos')
        assert response.status_code == 200
    
    def test_loja_page(self, client):
        """Test store page"""
        response = client.get('/loja')
        assert response.status_code == 200

class TestEquipmentRoutes:
    """Test equipment routes"""
    
    def test_equipment_listing(self, client):
        """Test equipment listing"""
        response = client.get('/equipamentos')
        assert response.status_code in [200, 302]  # May redirect if not logged in
