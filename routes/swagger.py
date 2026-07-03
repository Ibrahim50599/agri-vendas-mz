"""API Documentation"""
from flasgger import Swagger

def init_swagger(app):
    """
    Initialize Swagger documentation
    """
    swagger_config = {
        "headers": [],
        "specs": [
            {
                "endpoint": 'apispec',
                "route": '/apispec.json',
                "rule_filter": lambda rule: True,
                "model_filter": lambda tag: True,
            }
        ],
        "static_url_path": "/flasgger_static",
        "swagger_ui": True,
        "specs_route": "/api/docs"
    }
    
    swagger_template = {
        "swagger": "2.0",
        "info": {
            "title": "AGRI.Vendas MZ API",
            "description": "Plataforma web para anúncios de produtos agrícolas",
            "version": "1.0.0",
            "contact": {
                "name": "AGRI.Vendas MZ",
                "url": "https://agrivendas.mz"
            }
        },
        "host": "localhost:5000",
        "basePath": "/",
        "schemes": ["http", "https"],
        "securityDefinitions": {
            "bearer": {
                "type": "apiKey",
                "name": "Authorization",
                "in": "header"
            }
        }
    }
    
    swagger = Swagger(app, config=swagger_config, template=swagger_template)
    return swagger
