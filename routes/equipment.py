"""Equipment routes"""
from flask import render_template, request, session, redirect, url_for, jsonify
from functools import wraps
import os
from models import Database
from robust_system import SecurityManager
from utils import save_uploaded_file

db = Database(os.environ.get('DATABASE', 'agri_vendas.db'))
security = SecurityManager()

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or session.get('tipo') != 'admin':
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

from routes import equipment_bp

@equipment_bp.route('/equipamentos/filtrar')
def filtrar_equipamentos():
    """
    Filter equipment
    ---
    get:
      summary: Filter equipment by category and price
      parameters:
        - name: categoria
          in: query
          type: string
        - name: preco_max
          in: query
          type: float
      responses:
        200:
          description: Filtered equipment list
    """
    categoria = request.args.get('categoria')
    preco_max = request.args.get('preco_max')
    
    equipamentos = db.get_filtered_equipments(categoria, preco_max)
    return render_template('loja.html', equipamentos=equipamentos)

@equipment_bp.route('/api/equipamentos/<int:equip_id>')
def get_equipment(equip_id):
    """
    Get equipment details
    ---
    get:
      summary: Get specific equipment details
      parameters:
        - name: equip_id
          in: path
          type: integer
          required: true
      responses:
        200:
          description: Equipment details
        404:
          description: Equipment not found
    """
    equipment = db.get_equipment_by_id(equip_id)
    if not equipment:
        return {'error': 'Equipment not found'}, 404
    return dict(equipment), 200

@equipment_bp.route('/api/equipamentos', methods=['POST'])
@admin_required
def criar_equipamento():
    """
    Create new equipment
    ---
    post:
      summary: Create new equipment (admin only)
      security:
        - bearer: []
      parameters:
        - name: nome
          in: json
          type: string
          required: true
        - name: descricao
          in: json
          type: string
        - name: preco
          in: json
          type: float
          required: true
        - name: categoria
          in: json
          type: string
        - name: estoque
          in: json
          type: integer
      responses:
        201:
          description: Equipment created
        400:
          description: Invalid input
    """
    data = request.get_json()
    
    # Validate input
    try:
        security.validate_input(data, {
            'nome': {'required': True, 'min_length': 3},
            'preco': {'required': True, 'min': 0},
            'categoria': {'required': True}
        })
    except ValueError as e:
        return {'error': str(e)}, 400
    
    db.create_equipment(
        data['nome'],
        data.get('descricao', ''),
        float(data['preco']),
        data['categoria'],
        data.get('estoque', 1),
        data.get('foto_url', ''),
        data.get('localizacao', ''),
        data.get('contato', ''),
        session['user_id']
    )
    
    return {'message': 'Equipment created'}, 201
