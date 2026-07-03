"""Consulting routes with Google GenAI integration"""
from flask import render_template, request, jsonify, session
from functools import wraps
import os
import google.generativeai as genai
from robust_system import SecurityManager

security = SecurityManager()

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return {'error': 'Not authenticated'}, 401
        return f(*args, **kwargs)
    return decorated_function

# Configure Google GenAI
api_key = os.environ.get('GEMINI_API_KEY')
if api_key:
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-pro')
else:
    model = None

from routes import consulting_bp

@consulting_bp.route('/consultoria')
def consultoria():
    """
    Consulting page with AI
    ---
    get:
      summary: Get consulting page
      responses:
        200:
          description: Consulting page
    """
    return render_template('consultoria.html')

@consulting_bp.route('/api/consultoria', methods=['POST'])
@login_required
def api_consultoria():
    """
    AI Consulting API endpoint
    ---
    post:
      summary: Get AI consulting advice for agricultural topics
      parameters:
        - name: pergunta
          in: json
          type: string
          required: true
          description: Question about agriculture
        - name: cultura
          in: json
          type: string
          description: Crop type
      responses:
        200:
          description: AI response
        400:
          description: Missing question
        503:
          description: AI service unavailable
    """
    if not model:
        return {'error': 'AI service not configured'}, 503
    
    data = request.get_json()
    pergunta = data.get('pergunta')
    cultura = data.get('cultura', '')
    
    if not pergunta:
        return {'error': 'Question required'}, 400
    
    # Validate input
    try:
        security.validate_input({
            'pergunta': pergunta
        }, {
            'pergunta': {'required': True, 'min_length': 5, 'max_length': 500}
        })
    except ValueError as e:
        return {'error': str(e)}, 400
    
    try:
        # Build prompt with agricultural context
        prompt = f"""Você é um assistente agrícola especializado em Moçambique.
        
Cultura: {cultura if cultura else 'Geral'}
Pergunta: {pergunta}

Forneca uma resposta prática e útil em português."""
        
        response = model.generate_content(prompt)
        
        return {
            'resposta': response.text,
            'cultura': cultura,
            'pergunta': pergunta
        }, 200
    
    except Exception as e:
        return {'error': f'AI service error: {str(e)}'}, 503

@consulting_bp.route('/api/consultoria/culturas', methods=['GET'])
def get_culturas():
    """
    Get list of supported crops
    ---
    get:
      summary: Get supported crops for consulting
      responses:
        200:
          description: List of crops
    """
    from utils import DADOS_CULTURAS
    
    culturas = list(DADOS_CULTURAS.keys())
    return {'culturas': culturas}, 200

@consulting_bp.route('/api/consultoria/cultura/<cultura>', methods=['GET'])
def get_cultura_info(cultura):
    """
    Get specific crop information
    ---
    get:
      summary: Get detailed information about a specific crop
      parameters:
        - name: cultura
          in: path
          type: string
          required: true
      responses:
        200:
          description: Crop information
        404:
          description: Crop not found
    """
    from utils import DADOS_CULTURAS
    
    if cultura not in DADOS_CULTURAS:
        return {'error': 'Crop not found'}, 404
    
    return DADOS_CULTURAS[cultura], 200
