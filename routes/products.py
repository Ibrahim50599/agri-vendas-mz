"""Product routes"""
from flask import render_template, request, session, redirect, url_for
from functools import wraps
import os
from models import Database
from utils import validate_phone, save_uploaded_file
from robust_system import SecurityManager

db = Database(os.environ.get('DATABASE', 'agri_vendas.db'))
security = SecurityManager()

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

from routes import products_bp

@products_bp.route('/produtos')
def produtos():
    """
    List all products
    ---
    get:
      summary: Get all products
      parameters:
        - name: categoria
          in: query
          type: string
        - name: preco_max
          in: query
          type: float
        - name: regiao
          in: query
          type: string
      responses:
        200:
          description: List of products
    """
    categoria = request.args.get('categoria')
    preco_max = request.args.get('preco_max')
    regiao = request.args.get('regiao')
    
    produtos = db.get_filtered_products(categoria, preco_max, regiao)
    return render_template('produtos.html', produtos=produtos)

@products_bp.route('/loja')
def loja():
    """Equipment store"""
    equipamentos = db.get_equipments()
    return render_template('loja.html', equipamentos=equipamentos)

@products_bp.route('/publicar', methods=['GET', 'POST'])
@login_required
def publicar():
    """
    Publish new product
    ---
    post:
      summary: Create new product
      parameters:
        - name: nome
          in: form
          type: string
          required: true
        - name: preco
          in: form
          type: float
          required: true
        - name: descricao
          in: form
          type: string
        - name: localizacao
          in: form
          type: string
        - name: categoria
          in: form
          type: string
        - name: foto
          in: form
          type: file
      responses:
        201:
          description: Product created
        400:
          description: Invalid input
    """
    if request.method == 'POST':
        nome = request.form.get('nome')
        preco = request.form.get('preco')
        descricao = request.form.get('descricao')
        localizacao = request.form.get('localizacao')
        categoria = request.form.get('categoria')
        foto = request.files.get('foto')
        
        # Validate input
        try:
            security.validate_input({
                'nome': nome,
                'preco': float(preco),
                'categoria': categoria
            }, {
                'nome': {'required': True, 'min_length': 3},
                'preco': {'required': True, 'min': 0},
                'categoria': {'required': True}
            })
        except ValueError as e:
            return render_template('publicar.html', error=str(e))
        
        foto_url = ''
        if foto:
            foto_url = save_uploaded_file(foto, os.environ.get('UPLOAD_FOLDER', 'static/uploads'))
        
        db.create_product(
            session['user_id'],
            nome,
            float(preco),
            descricao,
            localizacao,
            foto_url,
            categoria
        )
        
        return redirect(url_for('dashboard'))
    
    return render_template('publicar.html')
