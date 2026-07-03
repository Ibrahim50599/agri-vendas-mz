"""Admin routes"""
from flask import render_template, request, redirect, url_for, session, jsonify
from functools import wraps
import os
from models import Database
from robust_system import SecurityManager

db = Database(os.environ.get('DATABASE', 'agri_vendas.db'))
security = SecurityManager()

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or session.get('tipo') != 'admin':
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

from routes import admin_bp

@admin_bp.route('/')
@admin_required
def admin_dashboard():
    """
    Admin dashboard
    ---
    get:
      summary: Get admin dashboard
      security:
        - bearer: []
      responses:
        200:
          description: Admin dashboard
        401:
          description: Unauthorized
    """
    stats = db.get_stats()
    return render_template('admin.html', stats=stats)

@admin_bp.route('/usuarios')
@admin_required
def gerenciar_usuarios():
    """Manage users"""
    usuarios = db.get_users()
    return render_template('admin_usuarios.html', usuarios=usuarios)

@admin_bp.route('/produtos')
@admin_required
def gerenciar_produtos():
    """Manage products"""
    # Implementation for managing products
    return render_template('admin_produtos.html')

@admin_bp.route('/equipamentos')
@admin_required
def gerenciar_equipamentos():
    """Manage equipment"""
    equipamentos = db.get_equipments()
    return render_template('admin_equipamentos.html', equipamentos=equipamentos)

@admin_bp.route('/relatorios')
@admin_required
def relatorios():
    """View reports"""
    reports = db.get_reports()
    return render_template('admin_relatorios.html', reports=reports)

@admin_bp.route('/api/usuario/<int:user_id>/banir', methods=['POST'])
@admin_required
def banir_usuario(user_id):
    """
    Ban user API endpoint
    ---
    post:
      summary: Ban a user
      security:
        - bearer: []
      responses:
        200:
          description: User banned
        404:
          description: User not found
    """
    try:
        db.ban_user(user_id)
        return {'message': 'User banned successfully'}, 200
    except Exception as e:
        return {'error': str(e)}, 400

@admin_bp.route('/api/usuario/<int:user_id>/premium', methods=['POST'])
@admin_required
def ativar_premium(user_id):
    """
    Activate premium for user
    ---
    post:
      summary: Activate premium subscription
      security:
        - bearer: []
      responses:
        200:
          description: Premium activated
    """
    try:
        db.activate_premium(user_id)
        return {'message': 'Premium activated'}, 200
    except Exception as e:
        return {'error': str(e)}, 400
