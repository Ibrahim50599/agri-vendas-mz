from flask import Flask, render_template, request, jsonify, redirect, url_for, session, flash
from flask.json.provider import DefaultJSONProvider
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import datetime
import os
import re
import sqlite3
from functools import wraps
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
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Decorador para verificar admin
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Permitir acesso com código especial (apenas super admin)
        if session.get('admin_access_code'):
            config = db.get_admin_config()
            if config and session.get('admin_access_code') == config[1]:
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
            if session.get('admin_access_code'):
                codigo = session.get('admin_access_code')
                if check_admin_access(codigo, nivel_minimo):
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

        # Regras de validação robustas
        validation_rules = {
            'nome_completo': {
                'required': True,
                'type': 'string',
                'min_length': 3,
                'max_length': 100,
                'pattern': r'^[a-zA-ZÀ-ÿ\s\-\.\' ]+$'  # Nomes com acentos e caracteres especiais comuns
            },
            'email': {
                'required': False,  # Email ou telefone obrigatório, mas não ambos
                'type': 'string',
                'max_length': 150,
                'pattern': r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            },
            'telefone': {
                'required': False,  # Email ou telefone obrigatório, mas não ambos
                'type': 'string',
                'min_length': 9,
                'max_length': 15,
                'pattern': r'^(\+258|258|8)?[28][0-9]{7,8}$'  # Padrão Moçambicano
            },
            'senha': {
                'required': True,
                'type': 'string',
                'min_length': 8,  # Aumentado para 8 caracteres
                'max_length': 128,
                'pattern': r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d).+$'  # Pelo menos uma minúscula, maiúscula e número
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
        form_data = {
            'nome': request.form.get('nome', '').strip(),
            'preco': request.form.get('preco', ''),
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
                'pattern': r'^[a-zA-Z0-9\s\-\.\,\(\)]+$'  # Apenas caracteres seguros
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

    return render_template('publicar.html')

@app.route('/consultoria')
@login_required
def consultoria():
    return render_template('consultoria.html')

@app.route('/calcular_plantio', methods=['POST'])
@login_required
def calcular_plantio():
    cultura = request.form.get('cultura', '').strip()
    try:
        area_valor = float(request.form.get('area_valor', request.form.get('hectares', 1)))
    except ValueError:
        return jsonify({'erro': 'Valor de área inválido'})

    unidade_area = request.form.get('unidade_area', 'hectares')

    if cultura not in DADOS_CULTURAS:
        return jsonify({'erro': f'Cultura "{cultura}" não encontrada na base de dados'})

    dados = DADOS_CULTURAS[cultura]
    preco_venda = dados.get('preco_venda', 30)

    # Converter metros quadrados para hectares se necessário
    if unidade_area == 'metros':
        hectares = area_valor / 10000
        metros_quadrados = area_valor
    else:
        hectares = area_valor
        metros_quadrados = area_valor * 10000

    resultado = {
        'cultura': dados.get('nome', cultura),
        'cultura_id': cultura,
        'hectares': round(hectares, 4),
        'metros_quadrados': round(metros_quadrados, 2),
        'unidade_usada': unidade_area,
        'area_original': area_valor,
        'sementes_necessarias': round(dados['sementes_por_ha'] * hectares, 2),
        'fertilizante_npk': round(dados['fertilizante_npk'] * hectares, 2),
        'cronograma_irrigacao': dados['irrigacao_dias'],
        'dias_para_colheita': dados['colheita_dias'],
        'rendimento_esperado': round(dados['rendimento_medio'] * hectares, 2),
        'custo_estimado': round(dados['custo_por_ha'] * hectares, 2),
        'receita_estimada': round(dados['rendimento_medio'] * hectares * preco_venda, 2),
        'lucro_estimado': round((dados['rendimento_medio'] * hectares * preco_venda) - (dados['custo_por_ha'] * hectares), 2),
        'preco_venda_kg': preco_venda,
        'categoria': dados.get('categoria', 'geral'),
        'recomenda_solo': dados.get('recomenda_solo', 'Prepare o solo com matéria orgânica e verifique o pH.'),
        'pos_colheita': dados.get('pos_colheita', 'Armazene em local seco e arejado após a secagem.'),
        'npk_recomendado': {
            'N': round(dados['fertilizante_npk'] * 0.4 * hectares, 1),
            'P': round(dados['fertilizante_npk'] * 0.3 * hectares, 1),
            'K': round(dados['fertilizante_npk'] * 0.3 * hectares, 1)
        },
        'alerta_pragas': [
            {'estagio': 'Germinação', 'risco': 'Lagarta-rosca', 'acao': 'Monitorar solo e umidade'},
            {'estagio': 'Crescimento', 'risco': 'Pulgões', 'acao': 'Aplicação de óleo de neem se necessário'},
            {'estagio': 'Floração', 'risco': 'Percevejos', 'acao': 'Monitoramento rigoroso matinal'}
        ]
    }

    # Informações detalhadas para todos (básico) e premium (completo)
    resultado['detalhes_basico'] = {
        'densidade_plantio': dados.get('densidade_plantio', 'Consulte um técnico'),
        'epoca_plantio': dados.get('epoca_plantio', 'Consulte um técnico')
    }

    # Informações detalhadas completas apenas para premium
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

    codigo = request.form.get('codigo')

    config = db.get_admin_config()
    if config and codigo == config[1]:
        session['admin_access_code'] = codigo
        session['admin_level'] = 'superadmin'
        flash('Acesso de super administrador concedido!')
        return redirect(url_for('admin_panel'))
    else:
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

@app.route('/admin/remover_produto/<int:produto_id>')
@admin_required
@with_error_handling
@with_performance_monitoring('product_removal')
@with_audit_trail('ADMIN_PRODUCT_REMOVAL')
def remover_produto(produto_id):
    try:
        # Verificar se o produto existe e obter detalhes para auditoria
        conn = db.get_connection()
        c = conn.cursor()
        c.execute("SELECT nome, usuario_id FROM produtos WHERE id = ?", (produto_id,))
        produto = c.fetchone()
        conn.close()

        if not produto:
            flash('Produto não encontrado!')
            return redirect(url_for('admin_panel'))

        # Verificar atividade suspeita (remoção em massa)
        admin_id = session['user_id']
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
    except Exception as e:
        db.logger.error(f"Erro ao remover produto {produto_id}: {str(e)}")
        flash(f'Erro ao remover produto: {str(e)}')
    return redirect(url_for('admin_panel'))

@app.route('/admin/banir_usuario/<int:user_id>')
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
        admin_id = session['user_id']
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
    user_id = request.form.get('user_id')
    nivel = request.form.get('nivel', 'admin')

    # Validações de segurança
    form_data = {
        'user_id': user_id,
        'nivel': nivel
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
            'pattern': r'^(admin|moderator|superadmin)$'
        }
    }

    try:
        db.security_manager.validate_input(form_data, validation_rules)

        # Verificar atividade suspeita (elevação de privilégios)
        admin_id = session['user_id']
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

        if not db.nomear_admin(user_id, nivel, session.get('user_id', 1)):
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