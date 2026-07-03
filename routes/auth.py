"""Authentication routes"""
from flask import render_template, request, session, redirect, url_for, jsonify
from werkzeug.security import check_password_hash
import jwt
import os
from functools import wraps
from models import Database
from utils import validate_email, validate_phone
from robust_system import SecurityManager

db = Database(os.environ.get('DATABASE', 'agri_vendas.db'))
security = SecurityManager()

def login_required(f):
    """Decorator to require login"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    """Decorator to require admin role"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or session.get('tipo') != 'admin':
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

from routes import auth_bp

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """
    User login endpoint
    ---
    post:
      summary: Authenticate user
      parameters:
        - name: login_field
          in: form
          type: string
          required: true
          description: Email or phone
        - name: senha
          in: form
          type: string
          required: true
          description: Password
      responses:
        200:
          description: Login successful
        401:
          description: Invalid credentials
    """
    if request.method == 'POST':
        login_field = request.form.get('login_field')
        senha = request.form.get('senha')
        
        # Validate input
        try:
            security.validate_input({
                'login_field': login_field,
                'senha': senha
            }, {
                'login_field': {'required': True, 'min_length': 3},
                'senha': {'required': True, 'min_length': 6}
            })
        except ValueError as e:
            return {'error': str(e)}, 400
        
        user = db.get_user_by_credentials(login_field, senha)
        
        if user and check_password_hash(user['senha_hash'], senha):
            session['user_id'] = user['id']
            session['nome'] = user['nome_completo']
            session['tipo'] = user['tipo']
            return redirect(url_for('index'))
        
        return render_template('login.html', error='Credenciais inválidas')
    
    return render_template('login.html')

@auth_bp.route('/cadastro', methods=['GET', 'POST'])
def cadastro():
    """
    User registration endpoint
    ---
    post:
      summary: Register new user
      parameters:
        - name: nome_completo
          in: form
          type: string
          required: true
        - name: email
          in: form
          type: string
          required: true
        - name: telefone
          in: form
          type: string
          required: true
        - name: senha
          in: form
          type: string
          required: true
        - name: tipo
          in: form
          type: string
          required: true
          enum: ['comprador', 'vendedor']
      responses:
        201:
          description: User created successfully
        400:
          description: Invalid input
    """
    if request.method == 'POST':
        nome = request.form.get('nome_completo')
        email = request.form.get('email')
        telefone = request.form.get('telefone')
        senha = request.form.get('senha')
        tipo = request.form.get('tipo', 'comprador')
        
        # Validate input
        try:
            security.validate_input({
                'nome': nome,
                'email': email,
                'telefone': telefone,
                'senha': senha
            }, {
                'nome': {'required': True, 'min_length': 3, 'max_length': 100},
                'email': {'required': True},
                'telefone': {'required': True},
                'senha': {'required': True, 'min_length': 6}
            })
            
            if not validate_email(email):
                raise ValueError('Email inválido')
            if not validate_phone(telefone):
                raise ValueError('Telefone inválido')
        except ValueError as e:
            return render_template('cadastro.html', error=str(e))
        
        try:
            db.create_user(nome, email, telefone, senha, tipo)
            return redirect(url_for('auth.login'))
        except Exception as e:
            return render_template('cadastro.html', error=f'Erro: {str(e)}')
    
    return render_template('cadastro.html')

@auth_bp.route('/logout')
def logout():
    """Logout user"""
    session.clear()
    return redirect(url_for('index'))
