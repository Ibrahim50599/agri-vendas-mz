from flask import Flask, render_template, request, jsonify, redirect, url_for, session, flash
from flask.json.provider import DefaultJSONProvider
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import datetime
import math
import os
import re
import sqlite3
from functools import wraps
from google import genai
from google.genai import types
from config import Config
from models import Database
from utils import validate_email, validate_phone, allowed_file, save_uploaded_file, CODIGOS_ADMIN, NIVEIS_HIERARQUIA, get_nivel_hierarquia, check_admin_access, DADOS_CULTURAS

# Importar sistema robusto
from robust_system import with_error_handling, with_performance_monitoring, with_audit_trail, SecurityManager, RobustDatabase

class CustomJSONProvider(DefaultJSONProvider):
    def default(self, o):
        if isinstance(o, sqlite3.Row):
            return dict(o)
        return super().default(o)

app = Flask(__name__)
app.json_provider_class = CustomJSONProvider
app.json = CustomJSONProvider(app)
app.config.from_object(Config)

# ProxyFix: necessário para sessões funcionarem atrás de qualquer proxy reverso
# (Render, Railway, Heroku, Nginx, etc.) — corrige IP, protocolo e host
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

# Criar pasta de uploads se não existir
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Inicializar banco de dados robusto
db = RobustDatabase(app.config['DATABASE'])
db.init_db()

# Inicializar gerenciador de segurança
security_manager = SecurityManager()

# Decorador para verificar login
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            # Para pedidos AJAX/fetch, devolver JSON em vez de redirect HTML
            if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.accept_mimetypes.best == 'application/json':
                return jsonify({
                    'erro': 'sessao_expirada',
                    'resposta': '⚠️ A sua sessão expirou. Por favor <a href="/login" style="color:#4CAF50;font-weight:bold;">faça login novamente</a> para continuar a usar o Assistente Agrícola.'
                }), 401
            return redirect(url_for('login'))
        conn = db.get_connection()
        c = conn.cursor()
        c.execute("SELECT ativo FROM usuarios WHERE id = ?", (session['user_id'],))
        active_user = c.fetchone()
        conn.close()
        if not active_user or active_user[0] != 1:
            session.clear()
            if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'erro': 'conta_banida', 'resposta': 'Esta conta está banida.'}), 403
            flash('Esta conta está banida ou foi desativada.')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def _global_admin_session_valid():
    """Confirma o acesso do super administrador sem depender de user_id."""
    codigo = session.get('admin_access_code')
    if not codigo:
        return False
    config = db.get_admin_config()
    return bool(config and codigo == config[1])

def login_or_global_admin_required(f):
    """Permite acesso ao utilizador autenticado ou ao super admin global."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if _global_admin_session_valid():
            session['admin_level'] = 'superadmin'
            return f(*args, **kwargs)
        return login_required(f)(*args, **kwargs)
    return decorated_function

# Decorador para verificar admin
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Permitir acesso com código especial (apenas super admin)
        if _global_admin_session_valid():
            session['admin_level'] = 'superadmin'
            return f(*args, **kwargs)

        if 'user_id' not in session:
            flash('Acesso negado. Faça login ou use o código de acesso.')
            return redirect(url_for('login'))

        # Verificar se é admin e qual o nível
        conn = db.get_connection()
        c = conn.cursor()
        c.execute("""SELECT u.tipo, a.nivel_acesso
                    FROM usuarios u
                    LEFT JOIN administradores a ON u.id = a.usuario_id AND a.ativo = 1
                    WHERE u.id = ? AND u.ativo = 1""", (session['user_id'],))
        user = c.fetchone()
        conn.close()

        if not user or (user[0] != 'admin' and not user[1]):
            flash('Acesso negado. Apenas administradores.')
            return redirect(url_for('index'))

        # Definir nível do admin na sessão
        session['admin_level'] = user[1] if user[1] else 'admin'
        return f(*args, **kwargs)
    return decorated_function

# Decorador para super admin apenas
def superadmin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('admin_access_code'):
            config = db.get_admin_config()
            if config and session.get('admin_access_code') == config[1]:
                return f(*args, **kwargs)

        if 'user_id' not in session:
            flash('Acesso negado.')
            return redirect(url_for('login'))

        # Verificar se é super admin
        conn = db.get_connection()
        c = conn.cursor()
        c.execute("SELECT nivel_acesso FROM administradores WHERE usuario_id = ? AND ativo = 1", (session['user_id'],))
        admin = c.fetchone()
        conn.close()

        if not admin or admin[0] != 'superadmin':
            flash('Apenas o super administrador pode acessar esta função.')
            return redirect(url_for('admin_panel'))

        return f(*args, **kwargs)
    return decorated_function

# Decorador para diferentes níveis de admin
def nivel_admin_required(nivel_minimo):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if _global_admin_session_valid():
                session['admin_level'] = 'superadmin'
                return f(*args, **kwargs)

            if session.get('admin_access_code'):
                codigo = session.get('admin_access_code')
                if check_admin_access(codigo, nivel_minimo):
                    session['admin_level'] = CODIGOS_ADMIN.get(codigo, nivel_minimo)
                    return f(*args, **kwargs)

            if 'user_id' not in session:
                flash('Acesso negado.')
                return redirect(url_for('login'))

            conn = db.get_connection()
            c = conn.cursor()
            c.execute("SELECT nivel_acesso FROM administradores WHERE usuario_id = ? AND ativo = 1", (session['user_id'],))
            admin = c.fetchone()
            conn.close()

            if not admin:
                flash('Acesso negado.')
                return redirect(url_for('index'))

            if get_nivel_hierarquia(admin[0]) >= get_nivel_hierarquia(nivel_minimo):
                return f(*args, **kwargs)

            flash('Você não tem permissão para acessar esta área.')
            return redirect(url_for('admin_panel'))
        return decorated_function
    return decorator

def _admin_controls_products():
    """Verifica no servidor se a sessão tem gestão de produtos."""
    if _global_admin_session_valid():
        return True

    user_id = session.get('user_id')
    if not user_id:
        return False

    conn = db.get_connection()
    c = conn.cursor()
    c.execute("""SELECT a.nivel_acesso
                 FROM administradores a
                 JOIN usuarios u ON u.id = a.usuario_id
                 WHERE a.usuario_id = ? AND a.ativo = 1 AND u.ativo = 1""",
              (user_id,))
    admin = c.fetchone()
    conn.close()
    return bool(admin and admin[0] in ('superadmin', 'produtos'))

# Rotas principais
@app.before_request
def update_premium_status():
    if 'user_id' in session:
        conn = db.get_connection()
        c = conn.cursor()
        c.execute("SELECT premium, tipo FROM usuarios WHERE id = ?", (session['user_id'],))
        user = c.fetchone()
        conn.close()
        if user:
            session['is_premium'] = user[0]
            session['user_type'] = user[1]

@app.route('/')
def index():
    produtos = db.get_products()
    return render_template('index.html', produtos=produtos)

@app.route('/cadastro', methods=['GET', 'POST'])
@with_error_handling
@with_performance_monitoring('user_registration')
@with_audit_trail('user_registration')
def cadastro():
    if request.method == 'POST':
        # Coletar dados do formulário
        form_data = {
            'nome_completo': request.form.get('nome_completo', '').strip(),
            'email': request.form.get('email', '').strip(),
            'telefone': request.form.get('telefone', '').strip(),
            'senha': request.form.get('senha', ''),
            'tipo': request.form.get('tipo', 'comprador')
        }

        # Normalizar telefone ANTES de validar (remove espaços, hífens, parênteses, +258, 258, 0)
        if form_data['telefone']:
            tel_clean = re.sub(r'\D', '', form_data['telefone'])
            if tel_clean.startswith('258') and len(tel_clean) > 9:
                tel_clean = tel_clean[3:]
            elif tel_clean.startswith('0') and len(tel_clean) > 9:
                tel_clean = tel_clean[1:]
            form_data['telefone'] = tel_clean

        # Regras de validação robustas
        validation_rules = {
            'nome_completo': {
                'required': True,
                'type': 'string',
                'min_length': 3,
                'max_length': 100,
                'pattern': r'^[a-zA-ZÀ-ÿ\s\-\.\' ]+$'
            },
            'email': {
                'required': False,
                'type': 'string',
                'max_length': 150,
                'pattern': r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            },
            'telefone': {
                'required': False,
                'type': 'string',
                'min_length': 8,
                'max_length': 13,
                # Números moçambicanos: móveis 82-87 (9 dígitos), fixos 21/23/25/26/27 (9 dígitos), formatos alternativos
                'pattern': r'^(8[2-7][0-9]{7}|2[1-9][0-9]{6,7}|[0-9]{8,9})$'
            },
            'senha': {
                'required': True,
                'type': 'string',
                'min_length': 6,
                'max_length': 128,
            },
            'tipo': {
                'required': True,
                'type': 'string',
                'pattern': r'^(comprador|vendedor|admin)$'
            }
        }

        try:
            # Validar entrada usando SecurityManager
            db.security_manager.validate_input(form_data, validation_rules)

            # Verificar se pelo menos email ou telefone foi fornecido
            if not form_data['email'] and not form_data['telefone']:
                raise ValueError("Email ou telefone deve ser fornecido")

            # Verificar rate limiting para cadastros
            client_ip = request.remote_addr
            if not db.security_manager.check_rate_limit(f"register_{client_ip}", max_attempts=3, window_minutes=60):
                flash('Muitas tentativas de cadastro. Tente novamente em 1 hora.')
                db.audit_log('RATE_LIMIT_EXCEEDED', details={'ip': client_ip, 'action': 'registration'})
                return render_template('cadastro.html')

            # Verificar atividade suspeita
            activity_data = {
                'action': 'user_registration',
                'ip': client_ip,
                'user_type': form_data['tipo'],
                'has_email': bool(form_data['email']),
                'has_phone': bool(form_data['telefone'])
            }

            if db.security_manager.detect_suspicious_activity(activity_data):
                db.audit_log('SUSPICIOUS_REGISTRATION', details=activity_data)
                flash('Cadastro suspeito detectado. Verificação adicional necessária.')
                return render_template('cadastro.html')

            # Normalizar telefone
            telefone = re.sub(r'\D', '', form_data['telefone']) if form_data['telefone'] else None

            # Verificar duplicatas
            conn = db.get_connection()
            c = conn.cursor()

            if form_data['email']:
                c.execute("SELECT id FROM usuarios WHERE email = ?", (form_data['email'],))
                if c.fetchone():
                    conn.close()
                    flash('Email já cadastrado')
                    return render_template('cadastro.html')

            if telefone:
                c.execute("SELECT id FROM usuarios WHERE telefone = ?", (telefone,))
                if c.fetchone():
                    conn.close()
                    flash('Telefone já cadastrado')
                    return render_template('cadastro.html')

            conn.close()

            # Criar usuário
            db.create_user(
                form_data['nome_completo'],
                form_data['email'] or None,
                telefone,
                form_data['senha'],
                form_data['tipo']
            )

            # Verificar se deve criar backup após registro
            if db.backup_scheduler.should_backup(interval_hours=12):  # Backup a cada 12 horas
                backup_path = db.backup_scheduler.create_backup('post_registration')
                if backup_path:
                    db.logger.info(f"Backup automático criado após registro: {backup_path}")

            flash('Cadastro realizado com sucesso!')
            return redirect(url_for('login'))

        except ValueError as e:
            flash(f'Dados inválidos: {str(e)}')
            return render_template('cadastro.html')
        except Exception as e:
            db.logger.error(f"Erro no cadastro: {str(e)}")
            flash('Erro interno do servidor. Tente novamente.')
            return render_template('cadastro.html')

    return render_template('cadastro.html')

@app.route('/login', methods=['GET', 'POST'])
@with_error_handling
@with_performance_monitoring('login_attempt')
def login():
    if request.method == 'POST':
        # Validação robusta dos dados de entrada
        login_data = {
            'login': request.form.get('login', '').strip(),
            'senha': request.form.get('senha', '')
        }

        validation_rules = {
            'login': {'required': True, 'min_length': 3, 'max_length': 100},
            'senha': {'required': True, 'min_length': 6}
        }

        try:
            security_manager.validate_input(login_data, validation_rules)
        except ValueError as e:
            flash(str(e))
            return render_template('login.html')

        login_field = login_data['login']
        senha = login_data['senha']

        # Normalizar telefone no login (remover espaços, hífens, prefixo 258/0)
        if re.match(r'^[\d\s\+\-\(\)]+$', login_field):
            tel_clean = re.sub(r'\D', '', login_field)
            if tel_clean.startswith('258') and len(tel_clean) > 9:
                tel_clean = tel_clean[3:]
            elif tel_clean.startswith('0') and len(tel_clean) > 9:
                tel_clean = tel_clean[1:]
            if len(tel_clean) >= 8:
                login_field = tel_clean

        # Verificar rate limiting
        client_ip = request.remote_addr
        if not security_manager.check_rate_limit(f"login_{client_ip}"):
            flash('Muitas tentativas de login. Tente novamente em 15 minutos.')
            db.audit_log('RATE_LIMIT_EXCEEDED', details={'ip': client_ip})
            return render_template('login.html')

        # Verificar atividade suspeita
        if security_manager.detect_suspicious_activity({
            'action': 'login_attempt',
            'ip': client_ip,
            'time': datetime.datetime.now().hour
        }):
            db.audit_log('SUSPICIOUS_ACTIVITY', details={'type': 'unusual_login_time', 'ip': client_ip})

        user = db.get_user_by_credentials(login_field, senha)

        if user and check_password_hash(user[2], senha):
            # Verificar se usuário está ativo
            if not db._check_user_active(user[0]):
                flash('Conta desativada. Entre em contato com o suporte.')
                db.audit_log('LOGIN_BLOCKED_INACTIVE', user[0], {'ip': client_ip})
                return render_template('login.html')

            session['user_id'] = user[0]
            session['user_name'] = user[1]
            session['user_type'] = user[3]
            session['is_premium'] = user[4]

            # Registrar login bem-sucedido
            db.audit_log('LOGIN_SUCCESS', user[0], {
                'ip': client_ip,
                'user_agent': request.headers.get('User-Agent')
            })

            flash(f'Bem-vindo, {user[1]}!')
            return redirect(url_for('dashboard'))
        else:
            # Registrar tentativa falhada
            db.audit_log('LOGIN_FAILED', details={
                'login_field': login_field,
                'ip': client_ip
            })

            flash('Login ou senha incorretos')
            return render_template('login.html')

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Logout realizado com sucesso')
    return redirect(url_for('index'))

@app.route('/dashboard')
@login_required
def dashboard():
    if session.get('user_type') in ['vendedor', 'admin']:
        meus_produtos = db.get_user_products(session['user_id'])
    else:
        meus_produtos = []

    return render_template('dashboard.html', meus_produtos=meus_produtos)

@app.route('/publicar', methods=['GET', 'POST'])
@login_required
@with_error_handling
@with_performance_monitoring('product_publication')
@with_audit_trail('publish_product')
def publicar_produto():
    if session.get('user_type') not in ['vendedor', 'admin']:
        flash('Apenas vendedores podem publicar produtos')
        return redirect(url_for('dashboard'))

    # Verificar limite para usuários não premium
    if not session.get('is_premium'):
        count = db.get_user_count(session['user_id'])
        if count >= 5:
            flash('Limite de 5 anúncios atingido. Assine o Premium para anúncios ilimitados!')
            return redirect(url_for('premium'))

    if request.method == 'POST':
        # Validações de segurança usando SecurityManager
        # Os campos HTML chegam sempre como texto. O preço precisa ser
        # convertido antes da validação, caso contrário a regra `float`
        # rejeita qualquer publicação válida.
        preco_texto = request.form.get('preco', '').strip().replace('\u00a0', '').replace(' ', '')
        if ',' in preco_texto and '.' in preco_texto:
            # Aceitar formatos como 10.000,50 e 10,000.50.
            if preco_texto.rfind(',') > preco_texto.rfind('.'):
                preco_texto = preco_texto.replace('.', '').replace(',', '.')
            else:
                preco_texto = preco_texto.replace(',', '')
        elif ',' in preco_texto:
            preco_texto = preco_texto.replace(',', '.')

        try:
            preco = float(preco_texto) if preco_texto else None
            if isinstance(preco, float) and not math.isfinite(preco):
                preco = preco_texto
        except (TypeError, ValueError):
            # Mantém o valor inválido para o SecurityManager devolver uma
            # mensagem de validação, em vez de gerar erro 500.
            preco = preco_texto

        form_data = {
            'nome': request.form.get('nome', '').strip(),
            'preco': preco,
            'descricao': request.form.get('descricao', '').strip(),
            'localizacao': request.form.get('localizacao', '').strip(),
            'categoria': request.form.get('categoria', '')
        }

        # Regras de validação
        validation_rules = {
            'nome': {
                'required': True,
                'type': 'string',
                'min_length': 3,
                'max_length': 100,
                # \w inclui letras acentuadas em Python (Unicode), além de
                # números e letras ASCII.
                'pattern': r'^[\w\s\-\.\,\(\)]+$'
            },
            'preco': {
                'required': True,
                'type': 'float',
                'min': 0.01,
                'max': 999999.99
            },
            'descricao': {
                'required': True,
                'type': 'string',
                'min_length': 10,
                'max_length': 1000
            },
            'localizacao': {
                'required': True,
                'type': 'string',
                'min_length': 3,
                'max_length': 100
            },
            'categoria': {
                'required': True,
                'type': 'string',
                'min_length': 2,
                'max_length': 50
            }
        }

        try:
            # Validar entrada usando SecurityManager
            db.security_manager.validate_input(form_data, validation_rules)

            # Verificar rate limiting para publicações
            user_id = session['user_id']
            if not db.security_manager.check_rate_limit(f"publish_{user_id}", max_attempts=10, window_minutes=60):
                flash('Muitas publicações em pouco tempo. Aguarde alguns minutos.')
                return redirect(url_for('dashboard'))

            nome = form_data['nome']
            preco = float(form_data['preco'])
            descricao = form_data['descricao']
            localizacao = form_data['localizacao']
            categoria = form_data['categoria']

            # Verificar atividade suspeita
            activity_data = {
                'user_id': user_id,
                'action': 'publish_product',
                'product_name': nome,
                'price': preco
            }

            if db.security_manager.detect_suspicious_activity(activity_data):
                db.audit_log('suspicious_product_publication', user_id, activity_data)
                flash('Atividade suspeita detectada. Publicação em análise.')
                return redirect(url_for('dashboard'))

            foto_url = ''
            if 'foto' in request.files:
                file = request.files['foto']
                foto_url = save_uploaded_file(file, app.config['UPLOAD_FOLDER']) or ''

            # Criar produto com validação de integridade
            db.create_product(session['user_id'], nome, preco, descricao, localizacao, foto_url, categoria)

            # Verificar se deve criar backup após publicação
            if db.backup_scheduler.should_backup(interval_hours=6):  # Backup a cada 6 horas
                backup_path = db.backup_scheduler.create_backup('post_publish')
                if backup_path:
                    db.logger.info(f"Backup automático criado após publicação: {backup_path}")

            flash('Produto publicado com sucesso!')
            return redirect(url_for('dashboard'))

        except ValueError as e:
            flash(f'Dados inválidos: {str(e)}')
            return render_template('publicar.html')
        except Exception as e:
            db.logger.error(f"Erro ao publicar produto: {str(e)}")
            flash(f'Erro ao publicar produto: {str(e)}')
            return render_template('publicar.html')

    return render_template('publicar.html')

@app.route('/produto/<int:produto_id>')
def ver_produto(produto_id):
    produto = db.get_product_by_id(produto_id)
    if not produto:
        return render_template('404.html'), 404
    vendedor = db.get_user_by_id(produto[1])
    return render_template('produto_detalhe.html', produto=produto, vendedor=vendedor)

@app.route('/editar_produto/<int:produto_id>', methods=['GET', 'POST'])
@login_or_global_admin_required
def editar_produto(produto_id):
    produto = db.get_product_by_id(produto_id)
    if not produto:
        flash('Produto não encontrado ou já removido.')
        return redirect(url_for('dashboard'))

    e_admin = _admin_controls_products()
    e_proprietario = session.get('user_id') == produto[1]
    if not e_admin and not e_proprietario:
        flash('Só o agricultor proprietário ou um administrador pode editar este produto.')
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        preco_texto = request.form.get('preco', '').strip().replace(',', '.')
        try:
            preco = float(preco_texto)
        except (TypeError, ValueError):
            preco = None

        dados = {
            'nome': request.form.get('nome', '').strip(),
            'preco': preco,
            'descricao': request.form.get('descricao', '').strip(),
            'localizacao': request.form.get('localizacao', '').strip(),
            'categoria': request.form.get('categoria', '').strip(),
        }
        erros = []
        if len(dados['nome']) < 3 or len(dados['nome']) > 100:
            erros.append('O nome deve ter entre 3 e 100 caracteres.')
        if dados['preco'] is None or not math.isfinite(dados['preco']) or not 0.01 <= dados['preco'] <= 999999.99:
            erros.append('Indique um preço válido entre 0,01 MT e 999.999,99 MT.')
        if len(dados['descricao']) < 10 or len(dados['descricao']) > 1000:
            erros.append('A descrição deve ter entre 10 e 1000 caracteres.')
        if len(dados['localizacao']) < 3 or len(dados['localizacao']) > 100:
            erros.append('Indique uma localização válida.')
        if len(dados['categoria']) < 2 or len(dados['categoria']) > 50:
            erros.append('Indique uma categoria válida.')

        if erros:
            for erro in erros:
                flash(erro)
            return render_template('editar_produto.html', produto=produto, dados=dados)

        foto_url = ''
        if request.files.get('foto') and request.files['foto'].filename:
            foto_url = save_uploaded_file(request.files['foto'], app.config['UPLOAD_FOLDER']) or ''

        if not db.update_product(produto_id, dados['nome'], dados['preco'], dados['descricao'],
                                 dados['localizacao'], dados['categoria'], foto_url):
            flash('O produto não pôde ser atualizado.')
            return render_template('editar_produto.html', produto=produto, dados=dados)

        db.audit_log('PRODUCT_UPDATED', session.get('user_id'), {
            'product_id': produto_id,
            'owner_id': produto[1],
            'edited_by_admin': e_admin and not e_proprietario
        })
        flash('Produto atualizado com sucesso!')
        return redirect(url_for('admin_panel') if e_admin else url_for('dashboard'))

    return render_template('editar_produto.html', produto=produto, dados=None)

@app.route('/remover_produto/<int:produto_id>', methods=['POST'])
@login_required
def remover_produto_proprio(produto_id):
    produto = db.get_product_by_id(produto_id)
    e_admin = _admin_controls_products()
    if not produto:
        return jsonify({'success': False, 'error': 'Produto não encontrado'}), 404
    if produto[1] != session.get('user_id') and not e_admin:
        return jsonify({'success': False, 'error': 'Sem permissão para remover este produto'}), 403

    db.remove_product(produto_id)
    db.audit_log('PRODUCT_REMOVED', session.get('user_id'), {
        'product_id': produto_id,
        'owner_id': produto[1],
        'removed_by_admin': e_admin and produto[1] != session.get('user_id')
    })
    return jsonify({'success': True, 'produto_id': produto_id})

@app.route('/consultoria')
@login_required
def consultoria():
    return render_template('consultoria.html')

GEMINI_SYSTEM_PROMPT = """És o Assistente Agrícola Virtual da plataforma AGRI.vendasMz, especializado em agricultura de Moçambique.

Responde SEMPRE em português de Moçambique. Sê prático, claro e útil.

As tuas áreas de especialização incluem:
- Culturas principais de Moçambique: milho, mandioca, arroz, feijão, amendoim, soja, sorgo, mapira, cajueiro, algodão, tabaco, cana-de-açúcar, tomate, couve, cebola, banana, manga, citrinos, papaia, abacate
- Condições climáticas e solos das províncias moçambicanas (Maputo, Gaza, Inhambane, Sofala, Manica, Tete, Zambézia, Nampula, Cabo Delgado, Niassa)
- Épocas de plantio e colheita para cada região
- Pragas e doenças comuns e como as controlar
- Adubação e fertilização (incluindo fertilizantes locais e orgânicos)
- Técnicas de irrigação adaptadas ao contexto moçambicano
- Pós-colheita, armazenamento e comercialização
- Preços de mercado orientativos
- Acesso a crédito agrícola e subsídios disponíveis em Moçambique

Regras:
- Respostas concisas (máximo 4-5 parágrafos)
- Usa exemplos práticos relevantes para Moçambique
- Se não souberes algo específico, diz honestamente e sugere onde obter ajuda (IIAM, serviços de extensão rural)
- Não faças diagnósticos médicos para humanos ou animais fora do âmbito agrícola
- Quando faltar província, área, cultura ou tipo de solo para uma recomendação, faz no máximo duas perguntas objetivas antes de recomendar
- Nunca inventes preços, produtos ou equipamentos: usa apenas os dados do marketplace fornecidos no contexto
- Diferencia claramente uma estimativa de uma recomendação confirmada
- Quando recomendares um produto ou equipamento, menciona o nome, preço e localização exatamente como aparecem nos dados"""


def _normalizar_contexto_assistente(value, max_length=80):
    """Limita e limpa contexto enviado pelo navegador antes de o usar na IA."""
    if value is None:
        return ''
    return str(value).strip().replace('\x00', '')[:max_length]


def _extrair_contexto_assistente(data):
    contexto = data.get('contexto') if isinstance(data, dict) else {}
    if not isinstance(contexto, dict):
        contexto = {}

    cultura = _normalizar_contexto_assistente(contexto.get('cultura'), 40).lower()
    provincia = _normalizar_contexto_assistente(contexto.get('provincia'), 40)
    distrito = _normalizar_contexto_assistente(contexto.get('distrito'), 60)
    area = _normalizar_contexto_assistente(contexto.get('area'), 30)
    solo = _normalizar_contexto_assistente(contexto.get('solo'), 40)
    irrigacao = _normalizar_contexto_assistente(contexto.get('irrigacao'), 40)
    investimento = _normalizar_contexto_assistente(contexto.get('investimento'), 40)

    return {
        'cultura': cultura,
        'provincia': provincia,
        'distrito': distrito,
        'area': area,
        'solo': solo,
        'irrigacao': irrigacao,
        'investimento': investimento,
    }


def _formatar_contexto_marketplace(pergunta):
    """Consulta dados reais apenas quando a pergunta pede mercado ou produtos."""
    pergunta_normalizada = pergunta.lower()
    termos_mercado = (
        'produto', 'preço', 'preco', 'comprar', 'vender', 'mercado',
        'equipamento', 'trator', 'semente', 'adubo', 'fertilizante',
        'pulverizador', 'irrigação', 'irrigacao'
    )
    if not any(termo in pergunta_normalizada for termo in termos_mercado):
        return ''

    linhas = ['DADOS ATUAIS DO MARKETPLACE (não inventar além destes registos):']
    try:
        produtos = db.get_filtered_products()[:5]
        if produtos:
            linhas.append('Produtos publicados:')
            for produto in produtos:
                linhas.append(
                    f"- {produto[2]} | {produto[3]:.2f} MT | "
                    f"{produto[5] or 'Moçambique'} | categoria: {produto[7] or 'não indicada'}"
                )
        else:
            linhas.append('Produtos publicados: nenhum registo disponível.')

        equipamentos = db.get_filtered_equipments()[:5]
        if equipamentos:
            linhas.append('Equipamentos disponíveis:')
            for equipamento in equipamentos:
                linhas.append(
                    f"- {equipamento[1]} | {equipamento[3]:.2f} MT | "
                    f"{equipamento[7] or 'Moçambique'} | estoque: {equipamento[5]}"
                )
        else:
            linhas.append('Equipamentos disponíveis: nenhum registo disponível.')
    except Exception as error:
        db.logger.warning(f'Não foi possível obter contexto do marketplace para a IA: {error}')
        return 'DADOS DO MARKETPLACE: indisponíveis nesta consulta; informa o utilizador sem inventar resultados.'

    return '\n'.join(linhas)


def _formatar_estimativa_plantio(contexto):
    """Gera uma prévia conservadora para o Assistente com os dados disponíveis."""
    cultura = contexto.get('cultura')
    area_texto = contexto.get('area', '').lower().replace(',', '.')
    if cultura not in DADOS_CULTURAS or not area_texto:
        return ''

    area_match = re.search(r'\d+(?:\.\d+)?', area_texto)
    if not area_match:
        return ''

    try:
        area_valor = float(area_match.group())
    except ValueError:
        return ''

    hectares = area_valor / 10000 if ('m2' in area_texto or 'metro' in area_texto) else area_valor
    if hectares <= 0 or hectares > 10000:
        return ''

    dados = DADOS_CULTURAS[cultura]
    solo = contexto.get('solo') or 'franco'
    irrigacao = contexto.get('irrigacao') or 'manual'
    investimento = contexto.get('investimento') or 'medio'

    rendimento_solo = {'franco': 1.0, 'humifero': 1.15, 'argiloso': 0.95, 'arenoso': 0.80, 'calcario': 0.75}
    rendimento_irrigacao = {'manual': 0.90, 'gotejamento': 1.20, 'aspersao': 1.15, 'inundacao': 1.05, 'nenhuma': 0.68}
    rendimento_investimento = {'baixo': 0.72, 'medio': 1.0, 'alto': 1.35}
    custo_solo = {'franco': 1.0, 'humifero': 0.95, 'argiloso': 1.05, 'arenoso': 1.10, 'calcario': 1.15}
    custo_irrigacao = {'manual': 1.05, 'gotejamento': 1.22, 'aspersao': 1.14, 'inundacao': 1.08, 'nenhuma': 0.88}
    custo_investimento = {'baixo': 0.58, 'medio': 1.0, 'alto': 1.42}

    rendimento = round(
        dados['rendimento_medio'] * hectares
        * rendimento_solo.get(solo, 1.0)
        * rendimento_irrigacao.get(irrigacao, 1.0)
        * rendimento_investimento.get(investimento, 1.0),
        2
    )
    custo = round(
        dados['custo_por_ha'] * hectares
        * custo_solo.get(solo, 1.0)
        * custo_irrigacao.get(irrigacao, 1.0)
        * custo_investimento.get(investimento, 1.0),
        2
    )
    receita = round(rendimento * dados.get('preco_venda', 30), 2)
    lucro = round(receita - custo, 2)

    return (
        'PRÉVIA ESTIMADA (confirma no Calculador de Plantio antes de investir): '
        f'{rendimento:,.2f} kg de produção; custo aproximado de {custo:,.2f} MT; '
        f'receita de referência de {receita:,.2f} MT; lucro estimado de {lucro:,.2f} MT. '
        'Esta prévia não substitui análise de solo nem cotação local.'
    )


def _formatar_contexto_assistente(pergunta, contexto):
    blocos = [
        f"Data atual: {datetime.date.today().isoformat()}",
        f"Perfil do utilizador: {session.get('user_type', 'utilizador autenticado')}.",
    ]

    campos = {
        'provincia': 'Província',
        'distrito': 'Distrito',
        'cultura': 'Cultura',
        'area': 'Área disponível',
        'solo': 'Tipo de solo',
        'irrigacao': 'Irrigação',
        'investimento': 'Nível de investimento',
    }
    preenchidos = [
        f"{label}: {contexto[chave]}"
        for chave, label in campos.items()
        if contexto.get(chave)
    ]
    if preenchidos:
        blocos.append('Contexto fornecido pelo agricultor: ' + '; '.join(preenchidos) + '.')
    else:
        blocos.append('Contexto do agricultor: ainda não fornecido.')

    cultura = contexto.get('cultura')
    if cultura in DADOS_CULTURAS:
        dados = DADOS_CULTURAS[cultura]
        blocos.append(
            'Dados agrícolas locais confirmados para esta cultura: '
            f"rendimento médio {dados.get('rendimento_medio')} kg/ha; "
            f"custo de referência {dados.get('custo_por_ha')} MT/ha; "
            f"colheita aproximada em {dados.get('colheita_dias')} dias; "
            f"época de plantio: {dados.get('epoca_plantio', 'não indicada')}."
        )
        estimativa = _formatar_estimativa_plantio(contexto)
        if estimativa:
            blocos.append(estimativa)

    mercado = _formatar_contexto_marketplace(pergunta)
    if mercado:
        blocos.append(mercado)

    return '\n'.join(blocos)

@app.route('/api/perfil-agricola', methods=['GET', 'POST'])
@login_required
def perfil_agricola():
    """Lê ou guarda o perfil agrícola persistente do utilizador autenticado."""
    if request.method == 'GET':
        return jsonify({'perfil': db.get_agricultural_profile(session['user_id'])})

    data = request.get_json(silent=True) or {}
    perfil = _extrair_contexto_assistente({'contexto': data.get('contexto', data)})
    db.save_agricultural_profile(session['user_id'], perfil)
    session['chat_context'] = perfil
    return jsonify({'ok': True, 'perfil': perfil})

@app.route('/assistente_ia', methods=['POST'])
@login_required
def assistente_ia():
    try:
        data = request.get_json()
        pergunta = data.get('pergunta', '').strip()
        if not pergunta:
            return jsonify({'resposta': 'Por favor escreva uma pergunta.'})

        contexto_enviado = _extrair_contexto_assistente(data)
        perfil_guardado = db.get_agricultural_profile(session['user_id'])
        contexto = {
            chave: contexto_enviado.get(chave) or perfil_guardado.get(chave, '')
            for chave in ('provincia', 'distrito', 'cultura', 'area', 'solo', 'irrigacao', 'investimento')
        }
        session['chat_context'] = contexto
        api_key = os.environ.get('GEMINI_API_KEY')
        if not api_key:
            return jsonify({'resposta': '⚠️ O Assistente IA não está configurado neste servidor. O administrador precisa de adicionar a variável de ambiente <strong>GEMINI_API_KEY</strong> nas definições do hosting (Render → Environment → Add Environment Variable).'})

        historico = session.get('chat_historico', [])

        contents = []
        for msg in historico:
            contents.append({'role': msg['role'], 'parts': [{'text': msg['text']}]})
        contents.append({'role': 'user', 'parts': [{'text': pergunta}]})

        system_instruction = (
            GEMINI_SYSTEM_PROMPT
            + '\n\nCONTEXTO DINÂMICO DA CONSULTA:\n'
            + _formatar_contexto_assistente(pergunta, contexto)
        )
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                max_output_tokens=1024,
            )
        )
        resposta = response.text or 'Não consegui gerar uma resposta. Tente novamente.'

        historico.append({'role': 'user', 'text': pergunta})
        historico.append({'role': 'model', 'text': resposta})
        if len(historico) > 20:
            historico = historico[-20:]
        session['chat_historico'] = historico

        return jsonify({'resposta': resposta})
    except Exception as e:
        erro = str(e)
        if 'API_KEY_INVALID' in erro or 'invalid' in erro.lower():
            return jsonify({'resposta': 'Chave API inválida. Verifique a configuração.'})
        return jsonify({'resposta': 'Ocorreu um erro ao contactar o assistente. Tente novamente mais tarde.'})

@app.route('/api/identificar-planta', methods=['POST'])
@login_required
def identificar_planta():
    """Analisa uma fotografia agrícola com o Gemini Vision."""
    imagem = request.files.get('imagem')
    if not imagem or not imagem.filename:
        return jsonify({
            'ok': False,
            'erro': 'Envie uma fotografia da planta ou da folha.'
        }), 400

    mime_type = (imagem.mimetype or '').lower()
    tipos_permitidos = {'image/jpeg', 'image/png', 'image/webp'}
    if mime_type not in tipos_permitidos:
        return jsonify({
            'ok': False,
            'erro': 'Formato não suportado. Use uma imagem JPG, PNG ou WebP.'
        }), 415

    image_bytes = imagem.read()
    limite_bytes = 8 * 1024 * 1024
    if not image_bytes:
        return jsonify({'ok': False, 'erro': 'A fotografia está vazia.'}), 400
    if len(image_bytes) > limite_bytes:
        return jsonify({
            'ok': False,
            'erro': 'A fotografia é muito grande. Escolha uma imagem com até 8 MB.'
        }), 413

    api_key = os.environ.get('GEMINI_API_KEY')
    if not api_key:
        return jsonify({
            'ok': False,
            'erro': 'O diagnóstico por imagem ainda não está configurado neste servidor.'
        }), 503

    contexto = {
        'província': request.form.get('provincia', '').strip(),
        'distrito': request.form.get('distrito', '').strip(),
        'cultura indicada': request.form.get('cultura', '').strip(),
    }
    contexto_texto = '; '.join(
        f'{chave}: {valor}' for chave, valor in contexto.items() if valor
    ) or 'Nenhum contexto adicional foi fornecido.'

    prompt = f"""És um agrónomo especializado nas culturas de Moçambique.
Analisa cuidadosamente a fotografia agrícola anexada. O contexto fornecido pelo agricultor é:
{contexto_texto}

Responde em português de Moçambique, com linguagem simples e prática, usando exatamente estas secções:
1. IDENTIFICAÇÃO: nome comum, nome científico e nível de confiança. Se a imagem não permitir identificar com segurança, diz isso claramente e apresenta no máximo três possibilidades.
2. OBSERVAÇÕES: descreve apenas o que é visível na planta, nas folhas, no caule, nos frutos ou no solo.
3. DOENÇAS OU PRAGAS: indica se há sinais compatíveis com doença, praga, deficiência nutricional ou stress. Não inventes um diagnóstico quando a evidência visual for insuficiente.
4. MANEJO RECOMENDADO: apresenta passos práticos e seguros, priorizando isolamento das plantas afetadas, higiene, monitorização, manejo integrado e alternativas de baixo risco. Só menciona produtos fitossanitários de forma geral e recomenda seguir sempre o rótulo e a orientação dos serviços agrários locais.
5. PRÓXIMO PASSO: diz que nova fotografia, informação ou observação o agricultor deve fornecer para confirmar a avaliação.

Não apresentes a análise como substituto de um agrónomo no campo. Não inventes preços, nomes de produtos comerciais ou doses. Se a fotografia não for de uma planta ou estiver desfocada, explica a limitação e pede uma fotografia melhor."""

    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model='gemini-1.5-flash',
            contents=[
                types.Part.from_text(text=prompt),
                types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
            ],
            config=types.GenerateContentConfig(
                temperature=0.2,
                max_output_tokens=1200,
            ),
        )
        analise = (response.text or '').strip()
        if not analise:
            return jsonify({
                'ok': False,
                'erro': 'O Gemini não devolveu uma análise. Tente fotografar a folha com mais luz.'
            }), 502
        return jsonify({'ok': True, 'analise': analise})
    except Exception as exc:
        erro = str(exc)
        if 'API_KEY_INVALID' in erro or 'invalid' in erro.lower():
            mensagem = 'A chave do Gemini é inválida ou expirou. Verifique a configuração do servidor.'
        elif 'safety' in erro.lower() or 'blocked' in erro.lower():
            mensagem = 'A imagem não pôde ser analisada. Tente uma fotografia clara apenas da planta.'
        else:
            mensagem = 'Não foi possível analisar a fotografia agora. Tente novamente em instantes.'
        app.logger.error('Falha no diagnóstico agrícola por imagem: %s', erro)
        return jsonify({'ok': False, 'erro': mensagem}), 502

@app.route('/assistente_ia/limpar', methods=['POST'])
@login_required
def assistente_ia_limpar():
    session.pop('chat_historico', None)
    session.pop('chat_context', None)
    return jsonify({'ok': True})

@app.route('/calcular_plantio', methods=['POST'])
@login_required
def calcular_plantio():
    cultura = request.form.get('cultura', '').strip()
    try:
        area_valor = float(request.form.get('area_valor', request.form.get('hectares', 1)))
    except ValueError:
        return jsonify({'erro': 'Valor de área inválido'})

    unidade_area = request.form.get('unidade_area', 'hectares')
    provincia = request.form.get('provincia', '').strip()
    distrito = request.form.get('distrito', '').strip()
    tipo_solo = request.form.get('tipo_solo', 'franco').strip()
    irrigacao = request.form.get('irrigacao', 'manual').strip()
    nivel_investimento = request.form.get('nivel_investimento', 'medio').strip()
    tipo_semente = request.form.get('tipo_semente', 'melhorada').strip()
    controle_pragas = request.form.get('controle_pragas', 'quimico_basico').strip()

    if cultura not in DADOS_CULTURAS:
        return jsonify({'erro': f'Cultura "{cultura}" não encontrada na base de dados'})

    dados = DADOS_CULTURAS[cultura]
    preco_venda = dados.get('preco_venda', 30)

    if unidade_area == 'metros':
        hectares = area_valor / 10000
        metros_quadrados = area_valor
    else:
        hectares = area_valor
        metros_quadrados = area_valor * 10000

    # ---- Multiplicadores por condições do campo ----
    mult_solo_rend   = {'franco': 1.0, 'humifero': 1.15, 'argiloso': 0.95, 'arenoso': 0.80, 'calcario': 0.75}
    mult_solo_fert   = {'franco': 1.0, 'humifero': 0.85, 'argiloso': 1.10, 'arenoso': 1.25, 'calcario': 1.30}
    mult_solo_custo  = {'franco': 1.0, 'humifero': 0.95, 'argiloso': 1.05, 'arenoso': 1.10, 'calcario': 1.15}

    mult_irrig_rend  = {'manual': 0.90, 'gotejamento': 1.20, 'aspersao': 1.15, 'inundacao': 1.05, 'nenhuma': 0.68}
    mult_irrig_custo = {'manual': 1.05, 'gotejamento': 1.22, 'aspersao': 1.14, 'inundacao': 1.08, 'nenhuma': 0.88}

    mult_inv_rend    = {'baixo': 0.72, 'medio': 1.0, 'alto': 1.35}
    mult_inv_custo   = {'baixo': 0.58, 'medio': 1.0, 'alto': 1.42}
    mult_inv_sem     = {'baixo': 0.70, 'medio': 1.0, 'alto': 1.20}

    mult_sem_rend    = {'local': 0.82, 'melhorada': 1.10, 'hibrida': 1.38}
    mult_sem_custo   = {'local': 0.78, 'melhorada': 1.10, 'hibrida': 1.32}

    mult_pragas_rend = {'nenhum': 0.72, 'natural': 0.90, 'quimico_basico': 1.05, 'quimico_avancado': 1.18}
    mult_pragas_custo= {'nenhum': 0.88, 'natural': 1.05, 'quimico_basico': 1.12, 'quimico_avancado': 1.22}

    r_rend  = (mult_solo_rend .get(tipo_solo, 1.0) * mult_irrig_rend .get(irrigacao, 1.0)
               * mult_inv_rend.get(nivel_investimento, 1.0) * mult_sem_rend .get(tipo_semente, 1.0)
               * mult_pragas_rend.get(controle_pragas, 1.0))
    r_custo = (mult_solo_custo.get(tipo_solo, 1.0) * mult_irrig_custo.get(irrigacao, 1.0)
               * mult_inv_custo.get(nivel_investimento, 1.0) * mult_sem_custo.get(tipo_semente, 1.0)
               * mult_pragas_custo.get(controle_pragas, 1.0))
    r_fert  = mult_solo_fert.get(tipo_solo, 1.0) * mult_inv_sem.get(nivel_investimento, 1.0)

    rendimento_ajustado = round(dados['rendimento_medio'] * hectares * r_rend, 2)
    custo_ajustado      = round(dados['custo_por_ha'] * hectares * r_custo, 2)
    receita_ajustada    = round(rendimento_ajustado * preco_venda, 2)
    lucro_ajustado      = round(receita_ajustada - custo_ajustado, 2)
    sementes_ajustadas  = round(dados['sementes_por_ha'] * hectares * mult_inv_sem.get(nivel_investimento, 1.0), 2)
    fertilizante_ajust  = round(dados['fertilizante_npk'] * hectares * r_fert, 2)

    # ---- Alertas de pragas personalizados por controle ----
    alertas_pragas_map = {
        'nenhum': [
            {'estagio': 'Germinação',  'risco': 'Lagarta-rosca',  'acao': 'Alto risco — sem controlo, pode perder 30% da germinação'},
            {'estagio': 'Crescimento', 'risco': 'Pulgões/Tripes', 'acao': 'Alto risco — recomenda-se pelo menos óleo de neem'},
            {'estagio': 'Floração',    'risco': 'Percevejos',     'acao': 'Monitoramento diário obrigatório'}
        ],
        'natural': [
            {'estagio': 'Germinação',  'risco': 'Lagarta-rosca',  'acao': 'Aplicar Bacillus thuringiensis no solo'},
            {'estagio': 'Crescimento', 'risco': 'Pulgões',        'acao': 'Óleo de neem 2% a cada 10 dias'},
            {'estagio': 'Floração',    'risco': 'Percevejos',     'acao': 'Armadilhas amarelas + extrato de alho'}
        ],
        'quimico_basico': [
            {'estagio': 'Germinação',  'risco': 'Lagarta-rosca',  'acao': 'Inseticida clorpirifós no plantio'},
            {'estagio': 'Crescimento', 'risco': 'Pulgões',        'acao': 'Imidacloprido sistémico se necessário'},
            {'estagio': 'Floração',    'risco': 'Percevejos',     'acao': 'Piretroide ao amanhecer'}
        ],
        'quimico_avancado': [
            {'estagio': 'Germinação',  'risco': 'Pragas do solo', 'acao': 'Tratamento de sementes + nematicida preventivo'},
            {'estagio': 'Crescimento', 'risco': 'Complexo de pragas', 'acao': 'Monitoramento semanal + rotação de princípios ativos'},
            {'estagio': 'Floração',    'risco': 'Percevejos/Mosca', 'acao': 'Programa IPM integrado com fungicida preventivo'}
        ]
    }

    # ---- Aviso climático por província ----
    info_clima_provincia = {
        'maputo':       {'estacao': 'Subtropical',  'chuva': 'Out–Abr', 'risco': 'Ciclones Jan–Mar, Seca Jun–Ago'},
        'gaza':         {'estacao': 'Semiárido',    'chuva': 'Nov–Mar', 'risco': 'Secas prolongadas, cheias do Limpopo'},
        'inhambane':    {'estacao': 'Tropical',     'chuva': 'Out–Abr', 'risco': 'Ciclones, ventos salinos'},
        'sofala':       {'estacao': 'Tropical',     'chuva': 'Nov–Abr', 'risco': 'Cheias do Búzi e Pungwe'},
        'manica':       {'estacao': 'Temperado',    'chuva': 'Nov–Abr', 'risco': 'Granizo Jan–Fev, Geadas Jun–Jul'},
        'tete':         {'estacao': 'Semiárido',    'chuva': 'Nov–Mar', 'risco': 'Calor extremo até 40°C, Secas'},
        'zambezia':     {'estacao': 'Tropical',     'chuva': 'Nov–Abr', 'risco': 'Ciclones, cheias do Zambeze'},
        'nampula':      {'estacao': 'Tropical',     'chuva': 'Nov–Abr', 'risco': 'Ciclones, chuvas irregulares'},
        'cabo-delgado': {'estacao': 'Tropical',     'chuva': 'Nov–Abr', 'risco': 'Ciclones'},
        'niassa':       {'estacao': 'Temperado',    'chuva': 'Nov–Abr', 'risco': 'Geadas Jun–Jul, solo ácido'},
    }

    # Nomes legíveis para o resultado
    nomes_legiveis = {
        'tipo_solo':    {'franco': 'Franco', 'humifero': 'Humífero', 'argiloso': 'Argiloso', 'arenoso': 'Arenoso', 'calcario': 'Calcário'},
        'irrigacao':    {'manual': 'Manual', 'gotejamento': 'Gotejamento', 'aspersao': 'Aspersão', 'inundacao': 'Inundação', 'nenhuma': 'Sem irrigação'},
        'investimento': {'baixo': 'Baixo (subsistência)', 'medio': 'Médio', 'alto': 'Alto (comercial)'},
        'semente':      {'local': 'Local/Tradicional', 'melhorada': 'Melhorada/Certificada', 'hibrida': 'Híbrida'},
        'pragas':       {'nenhum': 'Nenhum', 'natural': 'Natural/Biológico', 'quimico_basico': 'Químico Básico', 'quimico_avancado': 'Químico Avançado'},
    }

    resultado = {
        'cultura': dados.get('nome', cultura),
        'cultura_id': cultura,
        'hectares': round(hectares, 4),
        'metros_quadrados': round(metros_quadrados, 2),
        'unidade_usada': unidade_area,
        'area_original': area_valor,
        'sementes_necessarias': sementes_ajustadas,
        'fertilizante_npk': fertilizante_ajust,
        'cronograma_irrigacao': dados['irrigacao_dias'],
        'dias_para_colheita': dados['colheita_dias'],
        'rendimento_esperado': rendimento_ajustado,
        'custo_estimado': custo_ajustado,
        'receita_estimada': receita_ajustada,
        'lucro_estimado': lucro_ajustado,
        'preco_venda_kg': preco_venda,
        'categoria': dados.get('categoria', 'geral'),
        'recomenda_solo': dados.get('recomenda_solo', 'Prepare o solo com matéria orgânica e verifique o pH.'),
        'pos_colheita': dados.get('pos_colheita', 'Armazene em local seco e arejado após a secagem.'),
        'npk_recomendado': {
            'N': round(fertilizante_ajust * 0.4, 1),
            'P': round(fertilizante_ajust * 0.3, 1),
            'K': round(fertilizante_ajust * 0.3, 1)
        },
        'alerta_pragas': alertas_pragas_map.get(controle_pragas, alertas_pragas_map['quimico_basico']),
        'contexto': {
            'provincia': provincia.replace('-', ' ').title() if provincia else None,
            'distrito': distrito if distrito else None,
            'tipo_solo': nomes_legiveis['tipo_solo'].get(tipo_solo, tipo_solo),
            'irrigacao': nomes_legiveis['irrigacao'].get(irrigacao, irrigacao),
            'nivel_investimento': nomes_legiveis['investimento'].get(nivel_investimento, nivel_investimento),
            'tipo_semente': nomes_legiveis['semente'].get(tipo_semente, tipo_semente),
            'controle_pragas': nomes_legiveis['pragas'].get(controle_pragas, controle_pragas),
            'clima': info_clima_provincia.get(provincia, None) if provincia else None,
            'ajuste_rendimento_pct': round((r_rend - 1) * 100, 1),
            'ajuste_custo_pct': round((r_custo - 1) * 100, 1),
        }
    }

    resultado['detalhes_basico'] = {
        'densidade_plantio': dados.get('densidade_plantio', 'Consulte um técnico'),
        'epoca_plantio': dados.get('epoca_plantio', 'Consulte um técnico')
    }

    if session.get('is_premium'):
        resultado['detalhes_premium'] = {
            'solo_ideal': dados['solo_ideal'],
            'altitude_ideal': dados['altitude_ideal'],
            'temperatura_ideal': dados['temperatura_ideal'],
            'pragas_comuns': dados['pragas_comuns'],
            'doencas_comuns': dados['doencas_comuns'],
            'epoca_plantio': dados['epoca_plantio'],
            'densidade_plantio': dados.get('densidade_plantio', 'Consulte um técnico'),
            'recomenda_solo': dados.get('recomenda_solo', 'Informação detalhada em breve.'),
            'pos_colheita': dados.get('pos_colheita', 'Informação detalhada em breve.'),
            'calendario_completo': {
                'plantio': dados['epoca_plantio'],
                'irrigacao': f"Irrigar nos dias: {', '.join(map(str, dados['irrigacao_dias']))}",
                'colheita': f"Após {dados['colheita_dias']} dias do plantio"
            }
        }

    return jsonify(resultado)

@app.route('/premium')
@login_required
def premium():
    return render_template('premium.html')

@app.route('/admin/acesso', methods=['GET', 'POST'])
def validar_acesso_admin():
    if request.method == 'GET':
        return render_template('admin_acesso.html')

    codigo = request.form.get('codigo', '').strip()

    config = db.get_admin_config()
    if config and codigo == config[1]:
        session['admin_access_code'] = codigo
        session['admin_level'] = 'superadmin'
        flash('Acesso de super administrador concedido!')
        return redirect(url_for('admin_panel'))

    # Administradores secundários usam o código individual atribuído pelo
    # super administrador. O hash é verificado no banco, sem guardar o
    # código original na sessão ou na base de dados.
    secondary_admin = db.authenticate_secondary_admin(codigo)
    if secondary_admin:
        session.clear()
        session.permanent = True
        session['user_id'] = secondary_admin[1]
        session['user_name'] = secondary_admin[4]
        session['user_type'] = secondary_admin[5]
        session['is_premium'] = secondary_admin[6]
        session['admin_level'] = secondary_admin[2]
        session['admin_auth_method'] = 'secondary_code'
        flash(f'Bem-vindo, {secondary_admin[4]}!')

        workspace_routes = {
            'supervisor': 'admin_supervisor',
            'usuarios': 'admin_usuarios',
            'produtos': 'admin_produtos',
            'financeiro': 'admin_financeiro',
            'equipamentos': 'admin_equipamentos_gestao',
        }
        return redirect(url_for(workspace_routes.get(secondary_admin[2], 'admin_panel')))

    flash('Código de acesso incorreto!')
    return render_template('admin_acesso.html')

@app.route('/controle-agri')
@admin_required
@with_error_handling
@with_performance_monitoring('admin_panel_access')
@with_audit_trail('ADMIN_PANEL_ACCESS')
def admin_panel():
    try:
        stats = db.get_stats()
        usuarios = db.get_users()
        produtos = db.get_filtered_products()
        administradores = db.get_admin_users()
        configs = db.get_configs()
        equipamentos = db.get_equipments()

        admin_level = session.get('admin_level', 'admin')

        # Verificar integridade do sistema
        integrity_ok = db.validate_data_integrity()
        if not integrity_ok:
            flash('Aviso: Problemas de integridade detectados no banco de dados. Backup recomendado.')
            db.audit_log('INTEGRITY_CHECK_FAILED', session.get('user_id'))

        # Criar backup automático se necessário
        if db.backup_scheduler.should_backup():
            backup_path = db.backup_scheduler.create_backup('auto')
            if backup_path:
                db.logger.info(f"Backup automático criado: {backup_path}")

        return render_template('admin.html',
                               stats=stats,
                               usuarios=usuarios,
                               produtos=produtos,
                               administradores=administradores,
                               configuracoes=configs,
                               equipamentos=equipamentos,
                               admin_level=admin_level)
    except Exception as e:
        db.logger.error(f"Erro no painel admin: {str(e)}")
        flash('Erro interno do sistema. Tente novamente.')
        return redirect(url_for('dashboard'))

@app.route('/admin/ativar_premium/<int:user_id>')
@admin_required
def ativar_premium(user_id):
    try:
        db.activate_premium(user_id)
        flash('Premium ativado com sucesso!')
    except Exception as e:
        flash(f'Erro ao ativar premium: {str(e)}')
    return redirect(url_for('admin_panel'))

@app.route('/admin/desativar_premium/<int:user_id>')
@admin_required
def desativar_premium(user_id):
    try:
        db.deactivate_premium(user_id)
        flash('Premium desativado!')
    except Exception as e:
        flash(f'Erro ao desativar premium: {str(e)}')
    return redirect(url_for('admin_panel'))

@app.route('/admin/remover_produto/<int:produto_id>', methods=['GET', 'POST'])
@nivel_admin_required('produtos')
@with_error_handling
@with_performance_monitoring('product_removal')
@with_audit_trail('ADMIN_PRODUCT_REMOVAL')
def remover_produto(produto_id):
    try:
        # Verificar se o produto existe e obter detalhes para auditoria
        conn = db.get_connection()
        c = conn.cursor()
        c.execute("SELECT nome, vendedor_id FROM produtos WHERE id = ? AND ativo = 1", (produto_id,))
        produto = c.fetchone()
        conn.close()

        if not produto:
            if request.method == 'POST':
                return jsonify({'success': False, 'error': 'Produto não encontrado'}), 404
            flash('Produto não encontrado!')
            return redirect(url_for('admin_panel'))

        # Verificar atividade suspeita (remoção em massa)
        # O super administrador pode entrar pelo código global sem uma
        # sessão de usuário comum. Nesse caso, a nomeação continua válida e
        # o campo de auditoria fica sem utilizador associado.
        admin_id = session.get('user_id')
        activity_data = {
            'admin_id': admin_id,
            'action': 'remove_product',
            'product_id': produto_id,
            'product_name': produto[0],
            'owner_id': produto[1]
        }

        if db.security_manager.detect_suspicious_activity(activity_data):
            db.audit_log('SUSPICIOUS_ADMIN_ACTIVITY', admin_id, activity_data)
            flash('Atividade suspeita detectada. Ação registrada para análise.')
            return redirect(url_for('admin_panel'))

        # Remover produto
        db.remove_product(produto_id)

        # Verificar se deve criar backup após remoção administrativa
        if db.backup_scheduler.should_backup(interval_hours=2):  # Backup mais frequente para ações admin
            backup_path = db.backup_scheduler.create_backup('post_admin_action')
            if backup_path:
                db.logger.info(f"Backup automático criado após ação administrativa: {backup_path}")

        flash('Produto removido com sucesso!')
        if request.method == 'POST':
            return jsonify({'success': True, 'produto_id': produto_id})
    except Exception as e:
        db.logger.error(f"Erro ao remover produto {produto_id}: {str(e)}")
        if request.method == 'POST':
            return jsonify({'success': False, 'error': 'Não foi possível remover o produto'}), 500
        flash(f'Erro ao remover produto: {str(e)}')
    return redirect(url_for('admin_panel'))

@app.route('/admin/banir_usuario/<int:user_id>', methods=['GET', 'POST'])
@admin_required
@with_error_handling
@with_performance_monitoring('user_ban')
@with_audit_trail('ADMIN_USER_BAN')
def banir_usuario(user_id):
    conn = db.get_connection()
    c = conn.cursor()
    c.execute("SELECT tipo FROM usuarios WHERE id = ?", (user_id,))
    user = c.fetchone()
    conn.close()

    if user and user[0] == 'admin':
        flash('Não é possível banir administradores!')
        return redirect(url_for('admin_panel'))

    try:
        # Verificar atividade suspeita (banimento em massa)
        admin_id = session.get('user_id')
        activity_data = {
            'admin_id': admin_id,
            'action': 'ban_user',
            'target_user_id': user_id,
            'target_user_type': user[0] if user else 'unknown'
        }

        if db.security_manager.detect_suspicious_activity(activity_data):
            db.audit_log('SUSPICIOUS_ADMIN_ACTIVITY', admin_id, activity_data)
            flash('Atividade suspeita detectada. Ação registrada para análise.')
            return redirect(url_for('admin_panel'))

        db.ban_user(user_id)

        # Verificar se deve criar backup após banimento
        if db.backup_scheduler.should_backup(interval_hours=1):  # Backup imediato para ações críticas
            backup_path = db.backup_scheduler.create_backup('post_user_ban')
            if backup_path:
                db.logger.info(f"Backup automático criado após banimento: {backup_path}")

        flash('Usuário banido e produtos removidos!')
    except Exception as e:
        db.logger.error(f"Erro ao banir usuário {user_id}: {str(e)}")
        flash(f'Erro ao banir usuário: {str(e)}')
    return redirect(url_for('admin_panel'))

@app.route('/admin/reativar_usuario/<int:user_id>')
@admin_required
def reativar_usuario(user_id):
    try:
        db.unban_user(user_id)
        flash('Usuário reativado!')
    except Exception as e:
        flash(f'Erro ao reativar usuário: {str(e)}')
    return redirect(url_for('admin_panel'))

@app.route('/admin/nomear_admin', methods=['POST'])
@superadmin_required
@with_error_handling
@with_performance_monitoring('admin_appointment')
@with_audit_trail('ADMIN_APPOINTMENT')
def nomear_admin():
    user_id_raw = request.form.get('user_id', '').strip()
    nivel = request.form.get('nivel', 'admin')
    codigo_acesso = request.form.get('codigo_acesso', '').strip()

    try:
        user_id = int(user_id_raw)
    except (TypeError, ValueError):
        user_id = None

    # Validações de segurança
    form_data = {
        'user_id': user_id,
        'nivel': nivel,
        'codigo_acesso': codigo_acesso
    }

    validation_rules = {
        'user_id': {
            'required': True,
            'type': 'int',
            'min': 1
        },
        'nivel': {
            'required': True,
            'type': 'string',
            'pattern': r'^(admin|supervisor|usuarios|produtos|financeiro|equipamentos)$'
        },
        'codigo_acesso': {
            'required': True,
            'type': 'string',
            'min_length': 6,
            'max_length': 128,
            'pattern': r'^\S+$'
        }
    }

    try:
        db.security_manager.validate_input(form_data, validation_rules)

        # Verificar atividade suspeita (elevação de privilégios). O
        # superadmin também pode estar autenticado pelo código global, sem
        # um user_id na sessão comum.
        admin_id = session.get('user_id')
        activity_data = {
            'admin_id': admin_id,
            'action': 'appoint_admin',
            'target_user_id': int(user_id),
            'new_level': nivel
        }

        if db.security_manager.detect_suspicious_activity(activity_data):
            db.audit_log('SUSPICIOUS_PRIVILEGE_ESCALATION', admin_id, activity_data)
            flash('Atividade suspeita detectada. Nomeação registrada para análise.')
            return redirect(url_for('admin_panel'))

        if not db.nomear_admin(user_id, nivel, admin_id, codigo_acesso):
            flash('Usuário não encontrado ou já é administrador!')
            return redirect(url_for('admin_panel'))

        # Verificar se deve criar backup após mudança administrativa crítica
        if db.backup_scheduler.should_backup(interval_hours=1):  # Backup imediato para mudanças críticas
            backup_path = db.backup_scheduler.create_backup('post_admin_appointment')
            if backup_path:
                db.logger.info(f"Backup automático criado após nomeação administrativa: {backup_path}")

        flash('Administrador nomeado com sucesso!')
    except ValueError as e:
        flash(f'Dados inválidos: {str(e)}')
    except Exception as e:
        db.logger.error(f"Erro ao nomear admin: {str(e)}")
        flash(f'Erro ao nomear administrador: {str(e)}')

    return redirect(url_for('admin_panel'))

@app.route('/admin/administradores/<int:admin_id>/codigo', methods=['POST'])
@superadmin_required
def configurar_codigo_admin_secundario(admin_id):
    codigo_acesso = request.form.get('codigo_acesso', '').strip()
    try:
        if len(codigo_acesso) < 6 or len(codigo_acesso) > 128 or re.search(r'\s', codigo_acesso):
            raise ValueError('O código deve ter entre 6 e 128 caracteres e não pode conter espaços.')

        # Evitar que um registo de superadmin seja alterado por esta rota,
        # mesmo que alguém tente manipular o formulário.
        conn = db.get_connection()
        c = conn.cursor()
        c.execute("SELECT nivel_acesso FROM administradores WHERE id = ? AND ativo = 1", (admin_id,))
        admin = c.fetchone()
        conn.close()
        if not admin or admin[0] == 'superadmin':
            flash('Só é possível definir código para administradores secundários.')
            return redirect(url_for('admin_panel'))

        if db.set_admin_access_code(admin_id, codigo_acesso):
            flash('Código do administrador secundário guardado com segurança.')
        else:
            flash('Administrador secundário não encontrado.')
    except ValueError as e:
        flash(f'Dados inválidos: {str(e)}')
    except Exception as e:
        db.logger.error(f"Erro ao configurar código do administrador {admin_id}: {str(e)}")
        flash('Erro ao guardar o código do administrador.')
    return redirect(url_for('admin_panel'))

@app.route('/admin/remover_admin/<int:admin_id>')
@superadmin_required
def remover_admin(admin_id):
    if not db.remover_admin(admin_id):
        flash('Não é possível remover o super administrador!')
        return redirect(url_for('admin_panel'))

    flash('Administrador removido!')
    return redirect(url_for('admin_panel'))

@app.route('/admin/atualizar_config', methods=['POST'])
@admin_required
def atualizar_configuracao():
    chave = request.form.get('chave')
    valor = request.form.get('valor')

    # Apenas super admin pode alterar números de pagamento
    if chave in ['numero_emola', 'numero_mpesa'] and session.get('admin_level') != 'superadmin':
        flash('Apenas o super administrador pode alterar números de pagamento!')
        return redirect(url_for('admin_panel'))

    try:
        db.update_config(chave, valor, session.get('user_id', 1))
        flash('Configuração atualizada com sucesso!')
    except Exception as e:
        flash(f'Erro ao atualizar configuração: {str(e)}')
    return redirect(url_for('admin_panel'))

@app.route('/admin/recuperar-codigo', methods=['GET', 'POST'])
def recuperar_codigo_admin():
    if request.method == 'GET':
        return render_template('admin_recuperacao.html')

    tipo_recuperacao = request.form.get('tipo')
    config = db.get_admin_config()

    if not config:
        flash('Configuração não encontrada!')
        return render_template('admin_recuperacao.html')

    if tipo_recuperacao == 'email':
        email = request.form.get('email')
        if email == config[3]:
            flash(f'Código de acesso enviado para seu WhatsApp: {config[4]}')
            return render_template('admin_recuperacao.html', codigo_revelado=config[1])
        else:
            flash('Email não confere!')

    elif tipo_recuperacao == 'telefone':
        telefone = request.form.get('telefone')
        if telefone == config[4]:
            flash(f'Código de acesso: {config[1]}')
            return render_template('admin_recuperacao.html', codigo_revelado=config[1])
        else:
            flash('Telefone não confere!')

    elif tipo_recuperacao == 'seguranca':
        resposta = request.form.get('resposta')
        if resposta.lower() == config[6].lower():
            flash(f'Código de acesso: {config[1]}')
            return render_template('admin_recuperacao.html', codigo_revelado=config[1])
        else:
            flash('Resposta incorreta!')

    return render_template('admin_recuperacao.html')

@app.route('/admin/configurar-codigo', methods=['POST'])
@superadmin_required
def configurar_codigo_admin():
    novo_codigo = request.form.get('novo_codigo')
    nome_completo = request.form.get('nome_completo')
    email_recuperacao = request.form.get('email_recuperacao')
    telefone_recuperacao = request.form.get('telefone_recuperacao')
    pergunta_seguranca = request.form.get('pergunta_seguranca')
    resposta_seguranca = request.form.get('resposta_seguranca')

    try:
        db.update_admin_config(novo_codigo, nome_completo, email_recuperacao, telefone_recuperacao, pergunta_seguranca, resposta_seguranca)
        session['admin_access_code'] = novo_codigo
        flash('Configurações de administrador atualizadas com sucesso!')
    except Exception as e:
        flash(f'Erro ao atualizar configurações: {str(e)}')
    return redirect(url_for('admin_panel'))

@app.route('/api/stats')
@admin_required
def api_stats():
    stats = db.get_stats()
    return jsonify({
        'usuarios': stats['total_usuarios'],
        'produtos': stats['total_produtos'],
        'premium': stats['usuarios_premium'],
        'timestamp': datetime.datetime.now().isoformat()
    })

@app.route('/admin/metrics/update')
@admin_required
def admin_metrics_update():
    """Return the live metric values used by the admin dashboard."""
    stats = db.get_stats()
    return jsonify({
        'usuarios': stats['total_usuarios'],
        'premium': stats['usuarios_premium'],
        'produtos': stats['total_produtos'],
        'administradores': stats.get('total_admins', 0),
        'equipamentos': stats.get('total_equipamentos', 0),
        'timestamp': datetime.datetime.now().isoformat()
    })

@app.route('/admin/supervisor')
@nivel_admin_required('supervisor')
def admin_supervisor():
    conn = db.get_connection()
    c = conn.cursor()

    c.execute("SELECT COUNT(*) FROM usuarios WHERE ativo = 1")
    total_usuarios = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM produtos WHERE ativo = 1")
    total_produtos = c.fetchone()[0]

    conn.close()
    stats = {
        'total_usuarios': total_usuarios,
        'total_produtos': total_produtos
    }
    return render_template('admin_supervisor.html', stats=stats)

@app.route('/admin/relatorios')
@admin_required
def relatorios_admin():
    reports = db.get_reports()
    return render_template('admin_relatorios.html',
                           crescimento=reports['crescimento'],
                           categorias=reports['categorias'],
                           vendedores=reports['vendedores'])

@app.route('/admin/produtos')
@nivel_admin_required('produtos')
def admin_produtos():
    conn = db.get_connection()
    c = conn.cursor()

    c.execute("SELECT COUNT(*) FROM produtos WHERE ativo = 1")
    total_produtos = c.fetchone()[0]

    c.execute('''SELECT p.*, u.nome_completo
                FROM produtos p
                JOIN usuarios u ON p.vendedor_id = u.id
                WHERE p.ativo = 1
                ORDER BY p.data_publicacao DESC''')
    produtos = c.fetchall()

    conn.close()
    stats = {
        'total_produtos': total_produtos,
        'produtos_pendentes': 0,
        'produtos_inativos': 0,
        'produtos_mes': 0
    }
    return render_template('admin_produtos.html', produtos=produtos, stats=stats)

@app.route('/admin/financeiro')
@nivel_admin_required('financeiro')
def admin_financeiro():
    conn = db.get_connection()
    c = conn.cursor()

    c.execute("SELECT COUNT(*) FROM usuarios WHERE premium = 1 AND ativo = 1")
    usuarios_premium = c.fetchone()[0]

    c.execute("SELECT valor FROM configuracoes_sistema WHERE chave = 'numero_emola'")
    numero_emola = c.fetchone()

    c.execute("SELECT valor FROM configuracoes_sistema WHERE chave = 'numero_mpesa'")
    numero_mpesa = c.fetchone()

    conn.close()
    stats = {
        'usuarios_premium': usuarios_premium,
        'receita_total': usuarios_premium * 500,
        'receita_mes': usuarios_premium * 500
    }

    configuracoes_pagamento = {
        'numero_emola': numero_emola[0] if numero_emola else '878312890',
        'numero_mpesa': numero_mpesa[0] if numero_mpesa else '847214191'
    }
    return render_template('admin_financeiro.html', stats=stats, configuracoes_pagamento=configuracoes_pagamento)

@app.route('/admin/equipamentos-gestao')
@nivel_admin_required('equipamentos')
def admin_equipamentos_gestao():
    equipamentos = db.get_equipments()
    return render_template('admin_equipamentos.html', equipamentos=equipamentos)

@app.route('/admin/usuarios')
@nivel_admin_required('usuarios')
def admin_usuarios():
    conn = db.get_connection()
    c = conn.cursor()

    c.execute("SELECT COUNT(*) FROM usuarios WHERE ativo = 1")
    total_usuarios = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM usuarios WHERE premium = 1 AND ativo = 1")
    usuarios_premium = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM usuarios WHERE tipo = 'vendedor' AND ativo = 1")
    vendedores = c.fetchone()[0]

    usuarios = db.get_users()

    conn.close()
    stats = {
        'total_usuarios': total_usuarios,
        'usuarios_premium': usuarios_premium,
        'vendedores': vendedores,
        'usuarios_ativos': total_usuarios
    }
    return render_template('admin_usuarios.html', usuarios=usuarios, stats=stats)

@app.route('/loja')
def loja_equipamentos():
    filtro_categoria = request.args.get('categoria', '')
    filtro_preco_max = request.args.get('preco_max', '')

    equipamentos = db.get_filtered_equipments(categoria=filtro_categoria, preco_max=filtro_preco_max)
    return render_template('loja.html', equipamentos=equipamentos)

@app.route('/produtos')
def listar_produtos():
    filtro_categoria = request.args.get('categoria', '')
    filtro_preco_max = request.args.get('preco_max', '')
    filtro_regiao = request.args.get('regiao', '')

    produtos = db.get_filtered_products(categoria=filtro_categoria, preco_max=filtro_preco_max, regiao=filtro_regiao)
    return render_template('produtos.html', produtos=produtos)

@app.route('/contato/<int:vendedor_id>')
def contato_whatsapp(vendedor_id):
    user = db.get_user_by_id(vendedor_id)
    if not user:
        flash('Vendedor não encontrado')
        return redirect(url_for('index'))

    telefone = user[1]
    # Remover caracteres não numéricos
    telefone_limpo = re.sub(r'\D', '', telefone)

    # Assumir código do país +258 (Moçambique) se não tiver
    if not telefone_limpo.startswith('258'):
        telefone_limpo = '258' + telefone_limpo

    mensagem = f"Olá {user[0]}, vi seu produto no AGRI.vendasMz e tenho interesse!"
    whatsapp_url = f"https://wa.me/{telefone_limpo}?text={mensagem}"

    return redirect(whatsapp_url)

# Rotas de equipamentos (super admin)
@app.route('/admin/equipamentos')
@superadmin_required
def listar_equipamentos():
    equipamentos = db.get_equipments()
    return render_template('admin_equipamentos.html', equipamentos=equipamentos)

@app.route('/admin/equipamentos/novo', methods=['GET', 'POST'])
@superadmin_required
def novo_equipamento():
    if request.method == 'POST':
        nome = request.form['nome'].strip()
        descricao = request.form.get('descricao', '').strip()
        try:
            preco = float(request.form['preco'])
        except ValueError:
            flash('Preço inválido')
            return render_template('admin_equipamento_form.html', equipamento=None, action='novo')

        categoria = request.form.get('categoria', 'Equipamento Agrícola')
        try:
            estoque = int(request.form.get('estoque', 1))
        except ValueError:
            estoque = 1

        localizacao = request.form.get('localizacao', '').strip()
        contato = request.form.get('contato', '').strip()

        foto_url = ''
        if 'foto' in request.files:
            file = request.files['foto']
            foto_url = save_uploaded_file(file, app.config['UPLOAD_FOLDER']) or ''

        try:
            db.create_equipment(nome, descricao, preco, categoria, estoque, foto_url, localizacao, contato, session.get('user_id', 1))
            flash('Equipamento adicionado com sucesso!')
            return redirect(url_for('admin_panel'))
        except Exception as e:
            flash(f'Erro ao adicionar equipamento: {str(e)}')
            return render_template('admin_equipamento_form.html', equipamento=None, action='novo')

    return render_template('admin_equipamento_form.html', equipamento=None, action='novo')

@app.route('/admin/equipamentos/<int:equip_id>/editar', methods=['GET', 'POST'])
@superadmin_required
def editar_equipamento(equip_id):
    equipamento = db.get_equipment_by_id(equip_id)
    if not equipamento:
        flash('Equipamento não encontrado!')
        return redirect(url_for('admin_panel'))

    if request.method == 'POST':
        nome = request.form['nome'].strip()
        descricao = request.form.get('descricao', '').strip()
        try:
            preco = float(request.form['preco'])
        except ValueError:
            flash('Preço inválido')
            return render_template('admin_equipamento_form.html', equipamento=equipamento, action='editar')

        categoria = request.form.get('categoria', 'Equipamento Agrícola')
        try:
            estoque = int(request.form.get('estoque', 1))
        except ValueError:
            estoque = 1

        localizacao = request.form.get('localizacao', '').strip()
        contato = request.form.get('contato', '').strip()
        status = request.form.get('status', 'disponivel')

        foto_url = request.form.get('foto_atual', '')
        if 'foto' in request.files:
            file = request.files['foto']
            foto_url = save_uploaded_file(file, app.config['UPLOAD_FOLDER']) or foto_url

        try:
            db.update_equipment(equip_id, nome, descricao, preco, categoria, estoque, foto_url, localizacao, contato, status)
            flash('Equipamento atualizado com sucesso!')
            return redirect(url_for('admin_panel'))
        except Exception as e:
            flash(f'Erro ao atualizar equipamento: {str(e)}')
            return render_template('admin_equipamento_form.html', equipamento=equipamento, action='editar')

    return render_template('admin_equipamento_form.html', equipamento=equipamento, action='editar')

@app.route('/admin/equipamentos/<int:equip_id>/remover')
@superadmin_required
def remover_equipamento(equip_id):
    try:
        db.delete_equipment(equip_id)
        flash('Equipamento removido com sucesso!')
    except Exception as e:
        flash(f'Erro ao remover equipamento: {str(e)}')
    return redirect(url_for('admin_panel'))

@app.errorhandler(404)
def not_found_error(error):
    return render_template('error.html', title='Página não encontrada', message='A página solicitada não foi encontrada.'), 404


@app.errorhandler(500)
def internal_error(error):
    app.logger.exception('Internal server error: %s', error)
    return render_template('error.html', title='Erro interno', message='Ocorreu um erro inesperado. Tente novamente mais tarde.'), 500


if __name__ == '__main__':
    app.run(host=app.config['HOST'], port=app.config['PORT'], debug=app.config['DEBUG'])