from flask import Flask, render_template, request, jsonify, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import sqlite3
import jwt
import datetime
import os
import re
from functools import wraps

app = Flask(__name__)
app.secret_key = 'agri_vendas_mz_secret_key_2024'
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Criar pasta de uploads se não existir
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)


# Inicializar banco de dados
def init_db():
    conn = sqlite3.connect('agri_vendas.db')
    c = conn.cursor()

    # Tabela de usuários
    c.execute('''CREATE TABLE IF NOT EXISTS usuarios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome_completo TEXT NOT NULL,
        email TEXT UNIQUE,
        telefone TEXT UNIQUE,
        senha_hash TEXT NOT NULL,
        tipo TEXT DEFAULT 'comprador',
        premium INTEGER DEFAULT 0,
        data_premium_expira DATE,
        data_cadastro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        ativo INTEGER DEFAULT 1
    )''')

    # Tabela de produtos
    c.execute('''CREATE TABLE IF NOT EXISTS produtos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        vendedor_id INTEGER,
        nome TEXT NOT NULL,
        preco REAL NOT NULL,
        descricao TEXT,
        localizacao TEXT,
        foto_url TEXT,
        categoria TEXT,
        data_publicacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        ativo INTEGER DEFAULT 1,
        FOREIGN KEY (vendedor_id) REFERENCES usuarios (id)
    )''')

    # Tabela de administradores (recriar com estrutura correta)
    c.execute('DROP TABLE IF EXISTS administradores')
    c.execute('''CREATE TABLE administradores (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario_id INTEGER,
        nivel_acesso TEXT DEFAULT 'admin',
        data_nomeacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        nomeado_por INTEGER,
        ativo INTEGER DEFAULT 1,
        FOREIGN KEY (usuario_id) REFERENCES usuarios (id),
        FOREIGN KEY (nomeado_por) REFERENCES usuarios (id)
    )''')

    # Tabela de configurações do sistema
    c.execute('''CREATE TABLE IF NOT EXISTS configuracoes_sistema (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        chave TEXT UNIQUE,
        valor TEXT,
        descricao TEXT,
        data_alteracao TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        alterado_por INTEGER,
        FOREIGN KEY (alterado_por) REFERENCES usuarios (id)
    )''')

    # Tabela de configurações admin
    c.execute('''CREATE TABLE IF NOT EXISTS configuracoes_admin (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        codigo_acesso TEXT NOT NULL,
        nome_completo TEXT,
        email_recuperacao TEXT,
        telefone_recuperacao TEXT,
        pergunta_seguranca TEXT,
        resposta_seguranca TEXT,
        data_criacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        data_alteracao TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    # Tabela de equipamentos (gerenciada pelo super admin)
    c.execute('''CREATE TABLE IF NOT EXISTS equipamentos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT NOT NULL,
        descricao TEXT,
        preco REAL NOT NULL,
        categoria TEXT,
        estoque INTEGER DEFAULT 1,
        foto_url TEXT,
        localizacao TEXT,
        contato TEXT,
        status TEXT DEFAULT 'disponivel',
        criado_por INTEGER,
        data_criacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        ativo INTEGER DEFAULT 1,
        FOREIGN KEY (criado_por) REFERENCES usuarios (id)
    )''')

    # Inserir configurações padrão
    c.execute("INSERT OR IGNORE INTO configuracoes_sistema (chave, valor, descricao) VALUES (?, ?, ?)",
              ('numero_emola', '878312890', 'Número E-MOLA para pagamentos'))
    c.execute("INSERT OR IGNORE INTO configuracoes_sistema (chave, valor, descricao) VALUES (?, ?, ?)",
              ('numero_mpesa', '847214191', 'Número M-PESA para pagamentos'))


# Códigos de acesso para diferentes níveis administrativos
CODIGOS_ADMIN = {
    'AGRI2024ADMIN': 'superadmin',  # Super Administrador (Ibrahim)
    'VIGIA001': 'supervisor',  # Administrador Supervisor (2 pessoas)
    'VIGIA002': 'supervisor',
    'USUARIOS001': 'usuarios',  # Gestor de Usuários
    'PRODUTOS001': 'produtos',  # Gestor de Produtos
    'FINANCEIRO001': 'financeiro',  # Gestor Financeiro
    'EQUIPAMENTOS001': 'equipamentos'  # Gestor de Equipamentos
}

# Decorador para diferentes níveis de admin
def nivel_admin_required(nivel_minimo):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if session.get('admin_access_code'):
                codigo = session.get('admin_access_code')
                if codigo in CODIGOS_ADMIN:
                    nivel_usuario = CODIGOS_ADMIN[codigo]
                    niveis_hierarquia = ['equipamentos', 'financeiro', 'produtos', 'usuarios', 'supervisor', 'superadmin']
                    if niveis_hierarquia.index(nivel_usuario) >= niveis_hierarquia.index(nivel_minimo):
                        return f(*args, **kwargs)
            
            if 'user_id' not in session:
                flash('Acesso negado.')
                return redirect(url_for('login'))
            
            conn = sqlite3.connect('agri_vendas.db')
            c = conn.cursor()
            c.execute("SELECT nivel_acesso FROM administradores WHERE usuario_id = ? AND ativo = 1", (session['user_id'],))
            admin = c.fetchone()
            conn.close()
            
            if not admin:
                flash('Acesso negado.')
                return redirect(url_for('index'))
            
            niveis_hierarquia = ['equipamentos', 'financeiro', 'produtos', 'usuarios', 'supervisor', 'superadmin']
            if niveis_hierarquia.index(admin[0]) >= niveis_hierarquia.index(nivel_minimo):
                return f(*args, **kwargs)
            
            flash('Você não tem permissão para acessar esta área.')
            return redirect(url_for('admin_panel'))
        return decorated_function
    return decorator


    c.execute("INSERT OR IGNORE INTO configuracoes_sistema (chave, valor, descricao) VALUES (?, ?, ?)",
              ('numero_suporte', '878312890', 'Número de suporte técnico'))

    # Inserir configuração admin padrão
    c.execute("SELECT COUNT(*) FROM configuracoes_admin")
    if c.fetchone()[0] == 0:
        c.execute('''INSERT INTO configuracoes_admin 
                    (codigo_acesso, nome_completo, email_recuperacao, telefone_recuperacao, 
                     pergunta_seguranca, resposta_seguranca) 
                    VALUES (?, ?, ?, ?, ?, ?)''',
                  ('AGRI2024ADMIN', 'Ibrahim Hagi Amane', 'ibrahim@agrivendas.mz', '878312890',
                   'Qual é o nome da sua primeira empresa?', 'AGRI.vendasMz'))

    # Inserir admin padrão se não existir
    c.execute("SELECT * FROM usuarios WHERE telefone = '878312890'")
    if not c.fetchone():
        admin_hash = generate_password_hash('12345,Ibrahim')
        c.execute('''INSERT INTO usuarios 
                    (nome_completo, telefone, senha_hash, tipo, premium) 
                    VALUES (?, ?, ?, ?, ?)''',
                  ('Ibrahim Hagi Amane', '878312890', admin_hash, 'admin', 1))

        admin_id = c.lastrowid
        c.execute("INSERT INTO administradores (usuario_id, nivel_acesso, nomeado_por) VALUES (?, ?, ?)",
                  (admin_id, 'superadmin', admin_id))
    else:
        # Verificar se o admin existe na tabela administradores
        c.execute("SELECT id FROM usuarios WHERE telefone = '878312890'")
        admin_id = c.fetchone()[0]
        c.execute("SELECT * FROM administradores WHERE usuario_id = ?", (admin_id,))
        if not c.fetchone():
            c.execute("INSERT INTO administradores (usuario_id, nivel_acesso, nomeado_por) VALUES (?, ?, ?)",
                      (admin_id, 'superadmin', admin_id))
    
    # Inserir equipamentos de exemplo
    c.execute("SELECT COUNT(*) FROM equipamentos")
    if c.fetchone()[0] == 0:
        equipamentos_exemplo = [
            ('Trator Agrícola 75HP', 'Trator robusto ideal para preparação de solo, aração e cultivo. Motor diesel de 75HP, tração 4x4.', 
             450000, 'Tratores', 2, '', 'Maputo', '878312890', 'disponivel', admin_id),
            ('Sistema de Irrigação por Aspersão', 'Sistema completo para irrigação de até 5 hectares. Inclui bomba, tubos e aspersores.', 
             85000, 'Irrigação', 5, '', 'Matola', '878312890', 'disponivel', admin_id),
            ('Pulverizador Costal 20L', 'Pulverizador manual de alta pressão, ideal para aplicação de defensivos agrícolas.', 
             3500, 'Pulverizadores', 15, '', 'Beira', '878312890', 'disponivel', admin_id)
        ]
        
        for equip in equipamentos_exemplo:
            c.execute('''INSERT INTO equipamentos 
                        (nome, descricao, preco, categoria, estoque, foto_url, localizacao, contato, status, criado_por)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', equip)

    conn.commit()
    conn.close()


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
            conn = sqlite3.connect('agri_vendas.db')
            c = conn.cursor()
            c.execute("SELECT codigo_acesso FROM configuracoes_admin ORDER BY id DESC LIMIT 1")
            codigo_atual = c.fetchone()
            conn.close()

            if codigo_atual and session.get('admin_access_code') == codigo_atual[0]:
                session['admin_level'] = 'superadmin'
                return f(*args, **kwargs)

        if 'user_id' not in session:
            flash('Acesso negado. Faça login ou use o código de acesso.')
            return redirect(url_for('login'))

        conn = sqlite3.connect('agri_vendas.db')
        c = conn.cursor()
        # Verificar se é admin e qual o nível
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
            conn = sqlite3.connect('agri_vendas.db')
            c = conn.cursor()
            c.execute("SELECT codigo_acesso FROM configuracoes_admin ORDER BY id DESC LIMIT 1")
            codigo_atual = c.fetchone()
            conn.close()

            if codigo_atual and session.get('admin_access_code') == codigo_atual[0]:
                return f(*args, **kwargs)

        if 'user_id' not in session:
            flash('Acesso negado.')
            return redirect(url_for('login'))

        # Verificar se é super admin
        conn = sqlite3.connect('agri_vendas.db')
        c = conn.cursor()
        c.execute("SELECT nivel_acesso FROM administradores WHERE usuario_id = ? AND ativo = 1", (session['user_id'],))
        admin = c.fetchone()
        conn.close()

        if not admin or admin[0] != 'superadmin':
            flash('Apenas o super administrador pode acessar esta função.')
            return redirect(url_for('admin_panel'))

        return f(*args, **kwargs)

    return decorated_function


# Rotas principais
@app.route('/')
def index():
    conn = sqlite3.connect('agri_vendas.db')
    c = conn.cursor()
    c.execute('''SELECT p.*, u.nome_completo, u.telefone 
                FROM produtos p 
                JOIN usuarios u ON p.vendedor_id = u.id 
                WHERE p.ativo = 1 AND u.ativo = 1
                ORDER BY p.data_publicacao DESC LIMIT 20''')
    produtos = c.fetchall()
    conn.close()

    return render_template('index.html', produtos=produtos)


@app.route('/cadastro', methods=['GET', 'POST'])
def cadastro():
    if request.method == 'POST':
        nome = request.form['nome_completo']
        email = request.form.get('email', '')
        telefone = request.form.get('telefone', '')
        senha = request.form['senha']
        tipo = request.form.get('tipo', 'comprador')

        if not (email or telefone):
            flash('Email ou telefone é obrigatório')
            return render_template('cadastro.html')

        conn = sqlite3.connect('agri_vendas.db')
        c = conn.cursor()

        # Verificar se já existe
        if email:
            c.execute("SELECT id FROM usuarios WHERE email = ?", (email,))
            if c.fetchone():
                flash('Email já cadastrado')
                conn.close()
                return render_template('cadastro.html')

        if telefone:
            c.execute("SELECT id FROM usuarios WHERE telefone = ?", (telefone,))
            if c.fetchone():
                flash('Telefone já cadastrado')
                conn.close()
                return render_template('cadastro.html')

        senha_hash = generate_password_hash(senha)
        c.execute('''INSERT INTO usuarios 
                    (nome_completo, email, telefone, senha_hash, tipo) 
                    VALUES (?, ?, ?, ?, ?)''',
                  (nome, email, telefone, senha_hash, tipo))

        conn.commit()
        conn.close()

        flash('Cadastro realizado com sucesso!')
        return redirect(url_for('login'))

    return render_template('cadastro.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        login_field = request.form['login']  # email ou telefone
        senha = request.form['senha']

        conn = sqlite3.connect('agri_vendas.db')
        c = conn.cursor()
        c.execute('''SELECT id, nome_completo, senha_hash, tipo, premium 
                    FROM usuarios 
                    WHERE (email = ? OR telefone = ?) AND ativo = 1''',
                  (login_field, login_field))
        user = c.fetchone()
        conn.close()

        if user and check_password_hash(user[2], senha):
            session['user_id'] = user[0]
            session['user_name'] = user[1]
            session['user_type'] = user[3]
            session['is_premium'] = user[4]

            flash(f'Bem-vindo, {user[1]}!')
            return redirect(url_for('dashboard'))
        else:
            flash('Login ou senha incorretos')

    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    flash('Logout realizado com sucesso')
    return redirect(url_for('index'))


@app.route('/dashboard')
@login_required
def dashboard():
    conn = sqlite3.connect('agri_vendas.db')
    c = conn.cursor()

    # Buscar produtos do usuário se for vendedor
    if session.get('user_type') in ['vendedor', 'admin']:
        c.execute('''SELECT * FROM produtos 
                    WHERE vendedor_id = ? AND ativo = 1 
                    ORDER BY data_publicacao DESC''',
                  (session['user_id'],))
        meus_produtos = c.fetchall()
    else:
        meus_produtos = []

    conn.close()
    return render_template('dashboard.html', meus_produtos=meus_produtos)


@app.route('/publicar', methods=['GET', 'POST'])
@login_required
def publicar_produto():
    if session.get('user_type') not in ['vendedor', 'admin']:
        flash('Apenas vendedores podem publicar produtos')
        return redirect(url_for('dashboard'))

    # Verificar limite para usuários não premium
    if not session.get('is_premium'):
        conn = sqlite3.connect('agri_vendas.db')
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM produtos WHERE vendedor_id = ? AND ativo = 1",
                  (session['user_id'],))
        count = c.fetchone()[0]
        conn.close()

        if count >= 5:
            flash('Limite de 5 anúncios atingido. Assine o Premium para anúncios ilimitados!')
            return redirect(url_for('premium'))

    if request.method == 'POST':
        nome = request.form['nome']
        preco = float(request.form['preco'])
        descricao = request.form['descricao']
        localizacao = request.form['localizacao']
        categoria = request.form['categoria']

        foto_url = ''
        if 'foto' in request.files:
            file = request.files['foto']
            if file.filename != '':
                filename = secure_filename(file.filename)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                foto_url = f'uploads/{filename}'

        conn = sqlite3.connect('agri_vendas.db')
        c = conn.cursor()
        c.execute('''INSERT INTO produtos 
                    (vendedor_id, nome, preco, descricao, localizacao, foto_url, categoria)
                    VALUES (?, ?, ?, ?, ?, ?, ?)''',
                  (session['user_id'], nome, preco, descricao, localizacao, foto_url, categoria))
        conn.commit()
        conn.close()

        flash('Produto publicado com sucesso!')
        return redirect(url_for('dashboard'))

    return render_template('publicar.html')


@app.route('/consultoria')
@login_required
def consultoria():
    return render_template('consultoria.html')


@app.route('/calcular_plantio', methods=['POST'])
@login_required
def calcular_plantio():
    cultura = request.form['cultura']
    area_valor = float(request.form.get('area_valor', request.form.get('hectares', 1)))
    unidade_area = request.form.get('unidade_area', 'hectares')
    
    # Converter metros quadrados para hectares se necessário
    if unidade_area == 'metros':
        hectares = area_valor / 10000  # 1 hectare = 10000 m²
        metros_quadrados = area_valor
    else:
        hectares = area_valor
        metros_quadrados = area_valor * 10000

    # Base de dados COMPLETA de todas as culturas
    dados_culturas = {
        # ===================== CEREAIS =====================
        'milho': {
            'nome': 'Milho', 'sementes_por_ha': 20, 'fertilizante_npk': 150, 
            'irrigacao_dias': [7, 14, 21, 35, 50], 'colheita_dias': 120, 
            'rendimento_medio': 3500, 'custo_por_ha': 15000, 'preco_venda': 30,
            'solo_ideal': 'Solo bem drenado, pH 6.0-7.0', 'altitude_ideal': '0-1800m',
            'temperatura_ideal': '18-32°C', 'epoca_plantio': 'Out-Dez (época chuvosa)',
            'pragas_comuns': ['Lagarta-do-cartucho', 'Broca-do-colmo', 'Curuquerê', 'Pulgão'],
            'doencas_comuns': ['Ferrugem', 'Mancha-branca', 'Podridão-do-colmo', 'Cercosporiose'],
            'densidade_plantio': '60.000-80.000 plantas/ha', 'categoria': 'cereais'
        },
        'arroz': {
            'nome': 'Arroz', 'sementes_por_ha': 120, 'fertilizante_npk': 180, 
            'irrigacao_dias': [7, 14, 21, 35, 50, 70], 'colheita_dias': 110, 
            'rendimento_medio': 4000, 'custo_por_ha': 18000, 'preco_venda': 45,
            'solo_ideal': 'Solo argiloso, com boa retenção de água, pH 5.5-6.5',
            'altitude_ideal': '0-1000m', 'temperatura_ideal': '22-32°C',
            'epoca_plantio': 'Nov-Jan (irrigado), Mar-Mai (sequeiro)',
            'pragas_comuns': ['Broca-do-colmo', 'Percevejo-do-grão', 'Lagarta-das-folhas'],
            'doencas_comuns': ['Brusone', 'Queima-das-bainhas', 'Mancha-parda'],
            'densidade_plantio': '100-150 kg sementes/ha', 'categoria': 'cereais'
        },
        'trigo': {
            'nome': 'Trigo', 'sementes_por_ha': 150, 'fertilizante_npk': 200, 
            'irrigacao_dias': [10, 20, 35, 50, 70], 'colheita_dias': 130, 
            'rendimento_medio': 3000, 'custo_por_ha': 16000, 'preco_venda': 40,
            'solo_ideal': 'Solo franco-argiloso, pH 6.0-7.5', 'altitude_ideal': '500-2500m',
            'temperatura_ideal': '15-25°C', 'epoca_plantio': 'Mai-Jul (inverno)',
            'pragas_comuns': ['Pulgão', 'Lagarta-militar', 'Percevejo-barriga-verde'],
            'doencas_comuns': ['Ferrugem', 'Oídio', 'Giberela', 'Brusone'],
            'densidade_plantio': '250-350 plantas/m²', 'categoria': 'cereais'
        },
        'sorgo': {
            'nome': 'Sorgo', 'sementes_por_ha': 10, 'fertilizante_npk': 120, 
            'irrigacao_dias': [10, 25, 40, 60], 'colheita_dias': 100, 
            'rendimento_medio': 3000, 'custo_por_ha': 10000, 'preco_venda': 25,
            'solo_ideal': 'Solo bem drenado, tolerante a seca, pH 5.5-7.5', 'altitude_ideal': '0-1500m',
            'temperatura_ideal': '20-35°C', 'epoca_plantio': 'Set-Nov (principal)',
            'pragas_comuns': ['Pulgão-verde', 'Lagarta-do-cartucho', 'Mosca-do-sorgo'],
            'doencas_comuns': ['Antracnose', 'Helmintosporiose', 'Ferrugem'],
            'densidade_plantio': '120.000-180.000 plantas/ha', 'categoria': 'cereais'
        },
        'aveia': {
            'nome': 'Aveia', 'sementes_por_ha': 80, 'fertilizante_npk': 100, 
            'irrigacao_dias': [15, 30, 45, 60], 'colheita_dias': 120, 
            'rendimento_medio': 2500, 'custo_por_ha': 8000, 'preco_venda': 35,
            'solo_ideal': 'Solo fértil, bem drenado, pH 5.5-7.0', 'altitude_ideal': '500-2000m',
            'temperatura_ideal': '10-22°C', 'epoca_plantio': 'Mar-Jun (inverno)',
            'pragas_comuns': ['Pulgão', 'Lagarta-militar', 'Percevejo'],
            'doencas_comuns': ['Ferrugem', 'Helmintosporiose', 'Oídio'],
            'densidade_plantio': '200-300 plantas/m²', 'categoria': 'cereais'
        },
        'cevada': {
            'nome': 'Cevada', 'sementes_por_ha': 100, 'fertilizante_npk': 120, 
            'irrigacao_dias': [10, 25, 40, 55], 'colheita_dias': 110, 
            'rendimento_medio': 2800, 'custo_por_ha': 12000, 'preco_venda': 38,
            'solo_ideal': 'Solo bem drenado, pH 6.0-7.5', 'altitude_ideal': '800-2500m',
            'temperatura_ideal': '12-25°C', 'epoca_plantio': 'Abr-Jun (inverno)',
            'pragas_comuns': ['Pulgão', 'Lagarta-militar', 'Trips'],
            'doencas_comuns': ['Oídio', 'Ferrugem', 'Manchas foliares'],
            'densidade_plantio': '250-350 plantas/m²', 'categoria': 'cereais'
        },
        
        # ===================== HORTÍCOLAS =====================
        'tomate': {
            'nome': 'Tomate', 'sementes_por_ha': 1, 'fertilizante_npk': 300, 
            'irrigacao_dias': [3, 6, 9, 12, 18, 25, 35, 45], 'colheita_dias': 75, 
            'rendimento_medio': 40000, 'custo_por_ha': 25000, 'preco_venda': 60,
            'solo_ideal': 'Solo orgânico, bem drenado, pH 6.0-6.8', 'altitude_ideal': '0-1500m',
            'temperatura_ideal': '18-26°C', 'epoca_plantio': 'Ano todo (com irrigação)',
            'pragas_comuns': ['Broca-pequena', 'Mosca-branca', 'Trips', 'Ácaro-rajado'],
            'doencas_comuns': ['Requeima', 'Murcha-bacteriana', 'Vírus-do-mosaico', 'Alternária'],
            'densidade_plantio': '15.000-25.000 plantas/ha', 'categoria': 'horticolas'
        },
        'alface': {
            'nome': 'Alface', 'sementes_por_ha': 0.5, 'fertilizante_npk': 100, 
            'irrigacao_dias': [2, 4, 6, 8, 10, 12, 14], 'colheita_dias': 45, 
            'rendimento_medio': 25000, 'custo_por_ha': 12000, 'preco_venda': 20,
            'solo_ideal': 'Solo rico em matéria orgânica, pH 6.0-6.8', 'altitude_ideal': '0-1200m',
            'temperatura_ideal': '15-24°C', 'epoca_plantio': 'Ano todo (evitar calor extremo)',
            'pragas_comuns': ['Pulgão', 'Trips', 'Lesmas', 'Lagarta-rosca'],
            'doencas_comuns': ['Míldio', 'Queima-das-bordas', 'Podridão-mole'],
            'densidade_plantio': '80.000-120.000 plantas/ha', 'categoria': 'horticolas'
        },
        'cenoura': {
            'nome': 'Cenoura', 'sementes_por_ha': 4, 'fertilizante_npk': 150, 
            'irrigacao_dias': [5, 10, 15, 20, 30, 45, 60], 'colheita_dias': 90, 
            'rendimento_medio': 35000, 'custo_por_ha': 15000, 'preco_venda': 25,
            'solo_ideal': 'Solo arenoso, profundo, pH 6.0-6.8', 'altitude_ideal': '0-1500m',
            'temperatura_ideal': '15-22°C', 'epoca_plantio': 'Mar-Jul (época seca)',
            'pragas_comuns': ['Nematoides', 'Pulgão', 'Mosca-da-cenoura'],
            'doencas_comuns': ['Alternária', 'Cercosporiose', 'Podridão-mole'],
            'densidade_plantio': '500.000-800.000 plantas/ha', 'categoria': 'horticolas'
        },
        'couve': {
            'nome': 'Couve', 'sementes_por_ha': 0.3, 'fertilizante_npk': 180, 
            'irrigacao_dias': [3, 6, 10, 15, 20, 30], 'colheita_dias': 60, 
            'rendimento_medio': 30000, 'custo_por_ha': 14000, 'preco_venda': 18,
            'solo_ideal': 'Solo rico, bem drenado, pH 6.0-7.0', 'altitude_ideal': '0-1800m',
            'temperatura_ideal': '18-25°C', 'epoca_plantio': 'Ano todo',
            'pragas_comuns': ['Pulgão', 'Lagarta-da-couve', 'Traça-das-crucíferas'],
            'doencas_comuns': ['Podridão-negra', 'Míldio', 'Hérnia-das-crucíferas'],
            'densidade_plantio': '25.000-40.000 plantas/ha', 'categoria': 'horticolas'
        },
        'cebola': {
            'nome': 'Cebola', 'sementes_por_ha': 3, 'fertilizante_npk': 200, 
            'irrigacao_dias': [5, 10, 20, 35, 50, 70], 'colheita_dias': 120, 
            'rendimento_medio': 25000, 'custo_por_ha': 18000, 'preco_venda': 35,
            'solo_ideal': 'Solo areno-argiloso, pH 5.8-6.5', 'altitude_ideal': '0-1500m',
            'temperatura_ideal': '15-25°C', 'epoca_plantio': 'Mar-Jun (principal)',
            'pragas_comuns': ['Trips', 'Mosca-da-cebola', 'Ácaro-rajado'],
            'doencas_comuns': ['Míldio', 'Podridão-basal', 'Mancha-púrpura'],
            'densidade_plantio': '250.000-400.000 plantas/ha', 'categoria': 'horticolas'
        },
        'pimento': {
            'nome': 'Pimento', 'sementes_por_ha': 0.8, 'fertilizante_npk': 250, 
            'irrigacao_dias': [3, 7, 14, 21, 35, 50], 'colheita_dias': 90, 
            'rendimento_medio': 25000, 'custo_por_ha': 22000, 'preco_venda': 50,
            'solo_ideal': 'Solo fértil, bem drenado, pH 6.0-6.8', 'altitude_ideal': '0-1200m',
            'temperatura_ideal': '20-30°C', 'epoca_plantio': 'Set-Nov (verão)',
            'pragas_comuns': ['Pulgão', 'Ácaro-rajado', 'Mosca-branca', 'Trips'],
            'doencas_comuns': ['Antracnose', 'Murcha-bacteriana', 'Oídio', 'Vírus'],
            'densidade_plantio': '20.000-30.000 plantas/ha', 'categoria': 'horticolas'
        },
        'repolho': {
            'nome': 'Repolho', 'sementes_por_ha': 0.4, 'fertilizante_npk': 200, 
            'irrigacao_dias': [4, 8, 15, 25, 40, 55], 'colheita_dias': 80, 
            'rendimento_medio': 45000, 'custo_por_ha': 16000, 'preco_venda': 15,
            'solo_ideal': 'Solo argiloso, rico em matéria orgânica, pH 6.0-7.0', 'altitude_ideal': '0-1800m',
            'temperatura_ideal': '15-22°C', 'epoca_plantio': 'Mar-Ago (frio)',
            'pragas_comuns': ['Lagarta-da-couve', 'Pulgão', 'Traça-das-crucíferas'],
            'doencas_comuns': ['Podridão-negra', 'Míldio', 'Hérnia'],
            'densidade_plantio': '25.000-35.000 plantas/ha', 'categoria': 'horticolas'
        },
        'pepino': {
            'nome': 'Pepino', 'sementes_por_ha': 2, 'fertilizante_npk': 180, 
            'irrigacao_dias': [3, 6, 10, 15, 20, 30], 'colheita_dias': 50, 
            'rendimento_medio': 30000, 'custo_por_ha': 15000, 'preco_venda': 25,
            'solo_ideal': 'Solo fértil, bem drenado, pH 5.5-6.8', 'altitude_ideal': '0-1200m',
            'temperatura_ideal': '20-30°C', 'epoca_plantio': 'Set-Fev (quente)',
            'pragas_comuns': ['Pulgão', 'Ácaro-rajado', 'Mosca-branca', 'Broca'],
            'doencas_comuns': ['Oídio', 'Míldio', 'Antracnose', 'Vírus-do-mosaico'],
            'densidade_plantio': '15.000-25.000 plantas/ha', 'categoria': 'horticolas'
        },
        'abobora': {
            'nome': 'Abóbora', 'sementes_por_ha': 3, 'fertilizante_npk': 150, 
            'irrigacao_dias': [7, 14, 25, 40, 60], 'colheita_dias': 100, 
            'rendimento_medio': 20000, 'custo_por_ha': 10000, 'preco_venda': 20,
            'solo_ideal': 'Solo rico, bem drenado, pH 6.0-6.8', 'altitude_ideal': '0-1500m',
            'temperatura_ideal': '20-30°C', 'epoca_plantio': 'Set-Dez (quente)',
            'pragas_comuns': ['Broca', 'Mosca-das-frutas', 'Pulgão'],
            'doencas_comuns': ['Oídio', 'Míldio', 'Antracnose'],
            'densidade_plantio': '2.000-5.000 plantas/ha', 'categoria': 'horticolas'
        },
        
        # ===================== FRUTÍCOLAS =====================
        'manga': {
            'nome': 'Manga', 'sementes_por_ha': 0.1, 'fertilizante_npk': 200, 
            'irrigacao_dias': [15, 30, 60, 90], 'colheita_dias': 1095, 
            'rendimento_medio': 15000, 'custo_por_ha': 35000, 'preco_venda': 40,
            'solo_ideal': 'Solo profundo, bem drenado, pH 5.5-7.5', 'altitude_ideal': '0-1000m',
            'temperatura_ideal': '24-30°C', 'epoca_plantio': 'Nov-Jan (estação chuvosa)',
            'pragas_comuns': ['Mosca-das-frutas', 'Cochonilha', 'Tripes', 'Broca'],
            'doencas_comuns': ['Antracnose', 'Oídio', 'Seca-de-ponteiros', 'Malformação'],
            'densidade_plantio': '70-200 plantas/ha', 'categoria': 'fruticolas'
        },
        'banana': {
            'nome': 'Banana', 'sementes_por_ha': 0.01, 'fertilizante_npk': 350, 
            'irrigacao_dias': [7, 14, 21, 30, 45, 60], 'colheita_dias': 365, 
            'rendimento_medio': 25000, 'custo_por_ha': 30000, 'preco_venda': 25,
            'solo_ideal': 'Solo profundo, fértil, bem drenado, pH 6.0-6.5', 'altitude_ideal': '0-1200m',
            'temperatura_ideal': '22-30°C', 'epoca_plantio': 'Set-Dez (início das chuvas)',
            'pragas_comuns': ['Broca-do-rizoma', 'Tripes', 'Nematoides', 'Moleque'],
            'doencas_comuns': ['Mal-do-Panamá', 'Sigatoka', 'Moko', 'Podridão-mole'],
            'densidade_plantio': '1.600-2.500 plantas/ha', 'categoria': 'fruticolas'
        },
        'citrinos': {
            'nome': 'Citrinos (Laranja/Limão)', 'sementes_por_ha': 0.05, 'fertilizante_npk': 280, 
            'irrigacao_dias': [14, 28, 45, 70], 'colheita_dias': 1460, 
            'rendimento_medio': 30000, 'custo_por_ha': 40000, 'preco_venda': 30,
            'solo_ideal': 'Solo areno-argiloso, profundo, pH 6.0-7.0', 'altitude_ideal': '0-1500m',
            'temperatura_ideal': '23-32°C', 'epoca_plantio': 'Out-Dez (estação chuvosa)',
            'pragas_comuns': ['Pulgão', 'Cochonilha', 'Ácaro-da-leprose', 'Minador'],
            'doencas_comuns': ['Greening', 'CVC', 'Gomose', 'Cancro-cítrico'],
            'densidade_plantio': '250-500 plantas/ha', 'categoria': 'fruticolas'
        },
        'maca': {
            'nome': 'Maçã', 'sementes_por_ha': 0.02, 'fertilizante_npk': 250, 
            'irrigacao_dias': [14, 28, 45, 70, 100], 'colheita_dias': 1825, 
            'rendimento_medio': 35000, 'custo_por_ha': 50000, 'preco_venda': 55,
            'solo_ideal': 'Solo profundo, bem drenado, pH 6.0-7.0', 'altitude_ideal': '900-2000m',
            'temperatura_ideal': '10-22°C', 'epoca_plantio': 'Jun-Ago (inverno)',
            'pragas_comuns': ['Mosca-das-frutas', 'Grafolita', 'Pulgão', 'Ácaro'],
            'doencas_comuns': ['Sarna', 'Oídio', 'Podridão-amarga', 'Cancro'],
            'densidade_plantio': '800-3.000 plantas/ha', 'categoria': 'fruticolas'
        },
        'uva': {
            'nome': 'Uva', 'sementes_por_ha': 0.03, 'fertilizante_npk': 300, 
            'irrigacao_dias': [7, 14, 25, 40, 60, 90], 'colheita_dias': 730, 
            'rendimento_medio': 20000, 'custo_por_ha': 45000, 'preco_venda': 80,
            'solo_ideal': 'Solo areno-argiloso, bem drenado, pH 6.0-7.0', 'altitude_ideal': '0-1500m',
            'temperatura_ideal': '18-28°C', 'epoca_plantio': 'Jun-Ago (inverno)',
            'pragas_comuns': ['Cochonilha', 'Ácaro-rajado', 'Pérola-da-terra', 'Filoxera'],
            'doencas_comuns': ['Míldio', 'Oídio', 'Antracnose', 'Ferrugem'],
            'densidade_plantio': '1.500-3.000 plantas/ha', 'categoria': 'fruticolas'
        },
        'abacate': {
            'nome': 'Abacate', 'sementes_por_ha': 0.08, 'fertilizante_npk': 200, 
            'irrigacao_dias': [14, 30, 60, 90], 'colheita_dias': 1460, 
            'rendimento_medio': 15000, 'custo_por_ha': 35000, 'preco_venda': 45,
            'solo_ideal': 'Solo profundo, bem drenado, pH 5.5-7.0', 'altitude_ideal': '0-2000m',
            'temperatura_ideal': '20-28°C', 'epoca_plantio': 'Out-Dez (estação chuvosa)',
            'pragas_comuns': ['Broca-do-fruto', 'Ácaro', 'Tripes', 'Cochonilha'],
            'doencas_comuns': ['Podridão-radicular', 'Antracnose', 'Cercospora', 'Cancro'],
            'densidade_plantio': '100-400 plantas/ha', 'categoria': 'fruticolas'
        },
        'papaia': {
            'nome': 'Papaia', 'sementes_por_ha': 0.5, 'fertilizante_npk': 350, 
            'irrigacao_dias': [5, 10, 20, 35, 50], 'colheita_dias': 270, 
            'rendimento_medio': 60000, 'custo_por_ha': 25000, 'preco_venda': 20,
            'solo_ideal': 'Solo fértil, bem drenado, pH 6.0-6.5', 'altitude_ideal': '0-800m',
            'temperatura_ideal': '22-30°C', 'epoca_plantio': 'Set-Nov (quente)',
            'pragas_comuns': ['Ácaro-rajado', 'Mosca-das-frutas', 'Pulgão'],
            'doencas_comuns': ['Vírus-do-mosaico', 'Antracnose', 'Oídio', 'Podridão'],
            'densidade_plantio': '1.600-2.500 plantas/ha', 'categoria': 'fruticolas'
        },
        'ananás': {
            'nome': 'Ananás (Abacaxi)', 'sementes_por_ha': 0.1, 'fertilizante_npk': 300, 
            'irrigacao_dias': [10, 25, 45, 70, 100], 'colheita_dias': 540, 
            'rendimento_medio': 40000, 'custo_por_ha': 20000, 'preco_venda': 25,
            'solo_ideal': 'Solo arenoso, bem drenado, pH 4.5-5.5', 'altitude_ideal': '0-1000m',
            'temperatura_ideal': '22-32°C', 'epoca_plantio': 'Out-Fev (quente)',
            'pragas_comuns': ['Cochonilha', 'Broca-do-fruto', 'Ácaro'],
            'doencas_comuns': ['Fusariose', 'Podridão-negra', 'Murcha'],
            'densidade_plantio': '40.000-70.000 plantas/ha', 'categoria': 'fruticolas'
        },
        
        # ===================== TUBÉRCULOS =====================
        'mandioca': {
            'nome': 'Mandioca', 'sementes_por_ha': 1, 'fertilizante_npk': 100, 
            'irrigacao_dias': [20, 45, 90], 'colheita_dias': 360, 
            'rendimento_medio': 25000, 'custo_por_ha': 8000, 'preco_venda': 15,
            'solo_ideal': 'Solo arenoso, bem drenado, pH 5.5-6.5', 'altitude_ideal': '0-1800m',
            'temperatura_ideal': '20-30°C', 'epoca_plantio': 'Set-Nov (início das chuvas)',
            'pragas_comuns': ['Ácaros', 'Cochonilha', 'Mosca-branca', 'Trips'],
            'doencas_comuns': ['Bacteriose', 'Antracnose', 'Podridão-radicular', 'Mosaico'],
            'densidade_plantio': '10.000-15.000 plantas/ha', 'categoria': 'tuberculos'
        },
        'batata': {
            'nome': 'Batata', 'sementes_por_ha': 2500, 'fertilizante_npk': 250, 
            'irrigacao_dias': [5, 10, 20, 35, 50, 70], 'colheita_dias': 100, 
            'rendimento_medio': 30000, 'custo_por_ha': 35000, 'preco_venda': 25,
            'solo_ideal': 'Solo solto, bem drenado, pH 5.0-6.0', 'altitude_ideal': '500-3000m',
            'temperatura_ideal': '15-22°C', 'epoca_plantio': 'Abr-Jun e Set-Nov',
            'pragas_comuns': ['Traça', 'Larva-alfinete', 'Pulgão', 'Vaquinha'],
            'doencas_comuns': ['Requeima', 'Pinta-preta', 'Murcha-bacteriana', 'Sarna'],
            'densidade_plantio': '40.000-50.000 plantas/ha', 'categoria': 'tuberculos'
        },
        'batata-doce': {
            'nome': 'Batata-doce', 'sementes_por_ha': 0.5, 'fertilizante_npk': 120, 
            'irrigacao_dias': [10, 25, 50, 80], 'colheita_dias': 150, 
            'rendimento_medio': 20000, 'custo_por_ha': 10000, 'preco_venda': 18,
            'solo_ideal': 'Solo arenoso, bem drenado, pH 5.5-6.5', 'altitude_ideal': '0-2000m',
            'temperatura_ideal': '20-30°C', 'epoca_plantio': 'Set-Dez (quente)',
            'pragas_comuns': ['Broca-da-raiz', 'Elateríneo', 'Vaquinha'],
            'doencas_comuns': ['Mal-do-pé', 'Nematoide', 'Podridão-negra'],
            'densidade_plantio': '25.000-40.000 plantas/ha', 'categoria': 'tuberculos'
        },
        'inhame': {
            'nome': 'Inhame', 'sementes_por_ha': 3000, 'fertilizante_npk': 150, 
            'irrigacao_dias': [14, 30, 60, 100], 'colheita_dias': 240, 
            'rendimento_medio': 15000, 'custo_por_ha': 15000, 'preco_venda': 30,
            'solo_ideal': 'Solo franco, profundo, pH 5.5-6.5', 'altitude_ideal': '0-1500m',
            'temperatura_ideal': '22-30°C', 'epoca_plantio': 'Set-Nov (quente)',
            'pragas_comuns': ['Nematoides', 'Cochonilha', 'Besouro'],
            'doencas_comuns': ['Antracnose', 'Podridão-seca', 'Mosaico'],
            'densidade_plantio': '10.000-20.000 plantas/ha', 'categoria': 'tuberculos'
        },
        
        # ===================== LEGUMINOSAS =====================
        'feijao': {
            'nome': 'Feijão', 'sementes_por_ha': 50, 'fertilizante_npk': 200, 
            'irrigacao_dias': [5, 10, 20, 30, 45], 'colheita_dias': 90, 
            'rendimento_medio': 1200, 'custo_por_ha': 12000, 'preco_venda': 80,
            'solo_ideal': 'Solo franco, bem drenado, pH 6.0-6.5', 'altitude_ideal': '0-2000m',
            'temperatura_ideal': '16-28°C', 'epoca_plantio': 'Set-Nov (época das águas)',
            'pragas_comuns': ['Vaquinha', 'Mosca-branca', 'Ácaro-rajado', 'Cigarrinha'],
            'doencas_comuns': ['Antracnose', 'Ferrugem', 'Murcha-de-fusário', 'Mancha-angular'],
            'densidade_plantio': '200.000-300.000 plantas/ha', 'categoria': 'leguminosas'
        },
        'soja': {
            'nome': 'Soja', 'sementes_por_ha': 60, 'fertilizante_npk': 100, 
            'irrigacao_dias': [10, 25, 45, 70], 'colheita_dias': 120, 
            'rendimento_medio': 3000, 'custo_por_ha': 15000, 'preco_venda': 45,
            'solo_ideal': 'Solo fértil, bem drenado, pH 6.0-6.5', 'altitude_ideal': '0-1200m',
            'temperatura_ideal': '20-30°C', 'epoca_plantio': 'Out-Dez (principal)',
            'pragas_comuns': ['Lagarta-da-soja', 'Percevejo', 'Mosca-branca', 'Ácaro'],
            'doencas_comuns': ['Ferrugem-asiática', 'Antracnose', 'Cancro-da-haste', 'Oídio'],
            'densidade_plantio': '250.000-400.000 plantas/ha', 'categoria': 'leguminosas'
        },
        'grao-de-bico': {
            'nome': 'Grão-de-bico', 'sementes_por_ha': 80, 'fertilizante_npk': 80, 
            'irrigacao_dias': [15, 35, 60], 'colheita_dias': 110, 
            'rendimento_medio': 1500, 'custo_por_ha': 10000, 'preco_venda': 70,
            'solo_ideal': 'Solo franco-arenoso, pH 6.0-7.0', 'altitude_ideal': '0-2000m',
            'temperatura_ideal': '15-25°C', 'epoca_plantio': 'Mar-Jun (seco)',
            'pragas_comuns': ['Lagarta-rosca', 'Pulgão', 'Trips'],
            'doencas_comuns': ['Murcha-de-fusário', 'Podridão-radicular', 'Ferrugem'],
            'densidade_plantio': '200.000-330.000 plantas/ha', 'categoria': 'leguminosas'
        },
        'amendoim': {
            'nome': 'Amendoim', 'sementes_por_ha': 100, 'fertilizante_npk': 100, 
            'irrigacao_dias': [10, 25, 50, 80], 'colheita_dias': 120, 
            'rendimento_medio': 2500, 'custo_por_ha': 12000, 'preco_venda': 50,
            'solo_ideal': 'Solo arenoso, bem drenado, pH 6.0-6.5', 'altitude_ideal': '0-1500m',
            'temperatura_ideal': '22-30°C', 'epoca_plantio': 'Set-Nov (quente)',
            'pragas_comuns': ['Lagarta-rosca', 'Trips', 'Percevejo', 'Cigarrinha'],
            'doencas_comuns': ['Cercosporiose', 'Ferrugem', 'Verrugose', 'Mancha-preta'],
            'densidade_plantio': '100.000-200.000 plantas/ha', 'categoria': 'leguminosas'
        },
        'ervilha': {
            'nome': 'Ervilha', 'sementes_por_ha': 120, 'fertilizante_npk': 80, 
            'irrigacao_dias': [7, 15, 30, 50], 'colheita_dias': 75, 
            'rendimento_medio': 2000, 'custo_por_ha': 10000, 'preco_venda': 60,
            'solo_ideal': 'Solo franco, bem drenado, pH 6.0-7.0', 'altitude_ideal': '500-2500m',
            'temperatura_ideal': '12-22°C', 'epoca_plantio': 'Mar-Jun (frio)',
            'pragas_comuns': ['Pulgão', 'Trips', 'Lagarta-rosca'],
            'doencas_comuns': ['Oídio', 'Ferrugem', 'Antracnose', 'Murcha'],
            'densidade_plantio': '400.000-600.000 plantas/ha', 'categoria': 'leguminosas'
        },
        'feijao-nhemba': {
            'nome': 'Feijão Nhemba (Caupi)', 'sementes_por_ha': 30, 'fertilizante_npk': 80, 
            'irrigacao_dias': [10, 25, 45], 'colheita_dias': 70, 
            'rendimento_medio': 1000, 'custo_por_ha': 8000, 'preco_venda': 65,
            'solo_ideal': 'Solo arenoso, tolerante a seca, pH 5.5-6.5', 'altitude_ideal': '0-1500m',
            'temperatura_ideal': '25-35°C', 'epoca_plantio': 'Nov-Jan (quente)',
            'pragas_comuns': ['Vaquinha', 'Pulgão', 'Broca-da-vagem'],
            'doencas_comuns': ['Mosaico', 'Cercosporiose', 'Antracnose'],
            'densidade_plantio': '100.000-200.000 plantas/ha', 'categoria': 'leguminosas'
        },
        
        # ===================== OLEAGINOSAS =====================
        'girassol': {
            'nome': 'Girassol', 'sementes_por_ha': 5, 'fertilizante_npk': 100, 
            'irrigacao_dias': [15, 35, 55, 75], 'colheita_dias': 110, 
            'rendimento_medio': 2000, 'custo_por_ha': 10000, 'preco_venda': 55,
            'solo_ideal': 'Solo profundo, bem drenado, pH 6.0-7.5', 'altitude_ideal': '0-1500m',
            'temperatura_ideal': '20-28°C', 'epoca_plantio': 'Set-Nov (principal)',
            'pragas_comuns': ['Lagarta-do-girassol', 'Percevejo', 'Pulgão'],
            'doencas_comuns': ['Ferrugem', 'Oídio', 'Mancha-de-alternária', 'Podridão'],
            'densidade_plantio': '40.000-50.000 plantas/ha', 'categoria': 'oleaginosas'
        },
        'gergelim': {
            'nome': 'Gergelim', 'sementes_por_ha': 3, 'fertilizante_npk': 80, 
            'irrigacao_dias': [12, 28, 50], 'colheita_dias': 100, 
            'rendimento_medio': 800, 'custo_por_ha': 8000, 'preco_venda': 120,
            'solo_ideal': 'Solo arenoso, bem drenado, pH 5.5-8.0', 'altitude_ideal': '0-1500m',
            'temperatura_ideal': '25-35°C', 'epoca_plantio': 'Out-Dez (quente)',
            'pragas_comuns': ['Lagarta-rosca', 'Pulgão', 'Trips'],
            'doencas_comuns': ['Cercosporiose', 'Murcha-de-fusário', 'Podridão'],
            'densidade_plantio': '200.000-400.000 plantas/ha', 'categoria': 'oleaginosas'
        },
        'coco': {
            'nome': 'Coco', 'sementes_por_ha': 0.01, 'fertilizante_npk': 200, 
            'irrigacao_dias': [30, 60, 90], 'colheita_dias': 1825, 
            'rendimento_medio': 15000, 'custo_por_ha': 25000, 'preco_venda': 8,
            'solo_ideal': 'Solo arenoso costeiro, pH 5.0-8.0', 'altitude_ideal': '0-600m',
            'temperatura_ideal': '25-32°C', 'epoca_plantio': 'Nov-Jan (chuvoso)',
            'pragas_comuns': ['Ácaro-do-coqueiro', 'Broca-do-estipe', 'Cochonilha'],
            'doencas_comuns': ['Queima-das-folhas', 'Anel-vermelho', 'Podridão-seca'],
            'densidade_plantio': '120-200 plantas/ha', 'categoria': 'oleaginosas'
        },
        
        # ===================== MEDICINAIS =====================
        'aloe-vera': {
            'nome': 'Aloe Vera', 'sementes_por_ha': 0.1, 'fertilizante_npk': 60, 
            'irrigacao_dias': [20, 45, 75], 'colheita_dias': 365, 
            'rendimento_medio': 50000, 'custo_por_ha': 15000, 'preco_venda': 15,
            'solo_ideal': 'Solo arenoso, bem drenado, pH 6.0-8.0', 'altitude_ideal': '0-1500m',
            'temperatura_ideal': '18-30°C', 'epoca_plantio': 'Ano todo',
            'pragas_comuns': ['Cochonilha', 'Ácaro', 'Trips'],
            'doencas_comuns': ['Podridão-radicular', 'Antracnose', 'Ferrugem'],
            'densidade_plantio': '25.000-50.000 plantas/ha', 'categoria': 'medicinais'
        },
        'manjericao': {
            'nome': 'Manjericão', 'sementes_por_ha': 0.5, 'fertilizante_npk': 120, 
            'irrigacao_dias': [3, 7, 12, 18, 25], 'colheita_dias': 60, 
            'rendimento_medio': 8000, 'custo_por_ha': 10000, 'preco_venda': 80,
            'solo_ideal': 'Solo rico em matéria orgânica, pH 5.5-6.5', 'altitude_ideal': '0-1500m',
            'temperatura_ideal': '20-30°C', 'epoca_plantio': 'Set-Mar (quente)',
            'pragas_comuns': ['Pulgão', 'Ácaro', 'Lesmas'],
            'doencas_comuns': ['Fusário', 'Míldio', 'Mancha-bacteriana'],
            'densidade_plantio': '100.000-150.000 plantas/ha', 'categoria': 'medicinais'
        },
        'hortela': {
            'nome': 'Hortelã', 'sementes_por_ha': 0.2, 'fertilizante_npk': 100, 
            'irrigacao_dias': [3, 6, 10, 15, 22], 'colheita_dias': 90, 
            'rendimento_medio': 10000, 'custo_por_ha': 8000, 'preco_venda': 70,
            'solo_ideal': 'Solo rico, úmido, pH 6.0-7.0', 'altitude_ideal': '0-2000m',
            'temperatura_ideal': '15-25°C', 'epoca_plantio': 'Ano todo',
            'pragas_comuns': ['Lagarta', 'Pulgão', 'Ácaro'],
            'doencas_comuns': ['Ferrugem', 'Oídio', 'Mancha-foliar'],
            'densidade_plantio': '80.000-120.000 plantas/ha', 'categoria': 'medicinais'
        },
        'moringa': {
            'nome': 'Moringa', 'sementes_por_ha': 5, 'fertilizante_npk': 100, 
            'irrigacao_dias': [20, 45, 75], 'colheita_dias': 180, 
            'rendimento_medio': 20000, 'custo_por_ha': 10000, 'preco_venda': 50,
            'solo_ideal': 'Solo arenoso, bem drenado, tolerante a seca', 'altitude_ideal': '0-1500m',
            'temperatura_ideal': '25-35°C', 'epoca_plantio': 'Set-Dez (quente)',
            'pragas_comuns': ['Lagarta', 'Pulgão', 'Cochonilha'],
            'doencas_comuns': ['Podridão-radicular', 'Antracnose'],
            'densidade_plantio': '10.000-20.000 plantas/ha', 'categoria': 'medicinais'
        },
        
        # ===================== REGIONAIS (MOÇAMBIQUE) =====================
        'mapira': {
            'nome': 'Mapira (Sorgo local)', 'sementes_por_ha': 8, 'fertilizante_npk': 80, 
            'irrigacao_dias': [15, 35, 60], 'colheita_dias': 110, 
            'rendimento_medio': 2500, 'custo_por_ha': 7000, 'preco_venda': 28,
            'solo_ideal': 'Solo tolerante a seca, pH 5.5-7.5', 'altitude_ideal': '0-1500m',
            'temperatura_ideal': '22-35°C', 'epoca_plantio': 'Nov-Jan (quente)',
            'pragas_comuns': ['Pássaros', 'Lagarta-do-cartucho', 'Pulgão'],
            'doencas_comuns': ['Antracnose', 'Ferrugem', 'Carvão'],
            'densidade_plantio': '100.000-150.000 plantas/ha', 'categoria': 'regionais'
        },
        'mexoeira': {
            'nome': 'Mexoeira (Milheto)', 'sementes_por_ha': 5, 'fertilizante_npk': 60, 
            'irrigacao_dias': [15, 40, 70], 'colheita_dias': 90, 
            'rendimento_medio': 1500, 'custo_por_ha': 5000, 'preco_venda': 32,
            'solo_ideal': 'Solo arenoso, tolerante a seca', 'altitude_ideal': '0-1200m',
            'temperatura_ideal': '25-35°C', 'epoca_plantio': 'Nov-Jan (quente)',
            'pragas_comuns': ['Pássaros', 'Lagarta', 'Broca-do-colmo'],
            'doencas_comuns': ['Ferrugem', 'Míldio', 'Ergot'],
            'densidade_plantio': '150.000-250.000 plantas/ha', 'categoria': 'regionais'
        },
        'mucuna': {
            'nome': 'Mucuna', 'sementes_por_ha': 40, 'fertilizante_npk': 40, 
            'irrigacao_dias': [20, 50], 'colheita_dias': 150, 
            'rendimento_medio': 2000, 'custo_por_ha': 5000, 'preco_venda': 25,
            'solo_ideal': 'Solo diverso, fixadora de nitrogênio', 'altitude_ideal': '0-1500m',
            'temperatura_ideal': '22-32°C', 'epoca_plantio': 'Nov-Jan (chuvoso)',
            'pragas_comuns': ['Vaquinha', 'Lagarta-das-folhas'],
            'doencas_comuns': ['Cercosporiose', 'Podridão-radicular'],
            'densidade_plantio': '50.000-100.000 plantas/ha', 'categoria': 'regionais'
        },
        'cajueiro': {
            'nome': 'Cajueiro', 'sementes_por_ha': 0.05, 'fertilizante_npk': 150, 
            'irrigacao_dias': [30, 60, 90], 'colheita_dias': 1095, 
            'rendimento_medio': 1200, 'custo_por_ha': 20000, 'preco_venda': 150,
            'solo_ideal': 'Solo arenoso costeiro, pH 5.5-6.5', 'altitude_ideal': '0-600m',
            'temperatura_ideal': '25-32°C', 'epoca_plantio': 'Nov-Jan (chuvoso)',
            'pragas_comuns': ['Broca-das-pontas', 'Tripes', 'Helopeltis'],
            'doencas_comuns': ['Antracnose', 'Oídio', 'Gomose'],
            'densidade_plantio': '100-200 plantas/ha', 'categoria': 'regionais'
        },
        'algodao': {
            'nome': 'Algodão', 'sementes_por_ha': 15, 'fertilizante_npk': 180, 
            'irrigacao_dias': [10, 25, 45, 70, 100], 'colheita_dias': 150, 
            'rendimento_medio': 2500, 'custo_por_ha': 18000, 'preco_venda': 60,
            'solo_ideal': 'Solo argiloso, bem drenado, pH 5.8-8.0', 'altitude_ideal': '0-1200m',
            'temperatura_ideal': '25-35°C', 'epoca_plantio': 'Out-Dez (quente)',
            'pragas_comuns': ['Lagarta-rosada', 'Bicudo', 'Pulgão', 'Mosca-branca'],
            'doencas_comuns': ['Ramulose', 'Murcha-de-fusário', 'Mancha-angular'],
            'densidade_plantio': '80.000-120.000 plantas/ha', 'categoria': 'regionais'
        }
    }

    if cultura not in dados_culturas:
        return jsonify({'erro': f'Cultura "{cultura}" não encontrada na base de dados'})

    dados = dados_culturas[cultura]
    preco_venda = dados.get('preco_venda', 30)
    
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
        'categoria': dados.get('categoria', 'geral')
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


@app.route('/controle-agri')
@admin_required
def admin_panel():
    conn = sqlite3.connect('agri_vendas.db')
    c = conn.cursor()

    try:
        # Estatísticas gerais
        c.execute("SELECT COUNT(*) FROM usuarios WHERE ativo = 1")
        total_usuarios = c.fetchone()[0]

        c.execute("SELECT COUNT(*) FROM usuarios WHERE premium = 1 AND ativo = 1")
        usuarios_premium = c.fetchone()[0]

        c.execute("SELECT COUNT(*) FROM produtos WHERE ativo = 1")
        total_produtos = c.fetchone()[0]

        c.execute("SELECT COUNT(*) FROM administradores WHERE ativo = 1")
        total_admins = c.fetchone()[0]

        # Lista de usuários
        c.execute('''SELECT id, nome_completo, email, telefone, tipo, premium, data_cadastro
                    FROM usuarios WHERE ativo = 1 ORDER BY data_cadastro DESC LIMIT 50''')
        usuarios = c.fetchall()

        # Lista de produtos
        c.execute('''SELECT p.*, u.nome_completo 
                    FROM produtos p 
                    JOIN usuarios u ON p.vendedor_id = u.id 
                    WHERE p.ativo = 1 AND u.ativo = 1
                    ORDER BY p.data_publicacao DESC LIMIT 50''')
        produtos = c.fetchall()

        # Lista de administradores (apenas para super admin)
        administradores = []
        if session.get('admin_level') == 'superadmin' or session.get('admin_access_code'):
            c.execute('''SELECT a.*, u.nome_completo, u.telefone, u2.nome_completo as nomeado_por_nome
                        FROM administradores a 
                        JOIN usuarios u ON a.usuario_id = u.id 
                        LEFT JOIN usuarios u2 ON a.nomeado_por = u2.id
                        WHERE a.ativo = 1 
                        ORDER BY a.data_nomeacao DESC''')
            administradores = c.fetchall()

        # Configurações do sistema
        c.execute("SELECT * FROM configuracoes_sistema ORDER BY chave")
        configuracoes = c.fetchall()

        # Equipamentos (apenas para super admin)
        equipamentos = []
        total_equipamentos = 0
        if session.get('admin_level') == 'superadmin' or session.get('admin_access_code'):
            c.execute("SELECT COUNT(*) FROM equipamentos WHERE ativo = 1")
            total_equipamentos = c.fetchone()[0]
            c.execute('''SELECT * FROM equipamentos WHERE ativo = 1 ORDER BY data_criacao DESC LIMIT 50''')
            equipamentos = c.fetchall()

        stats = {
            'total_usuarios': total_usuarios,
            'usuarios_premium': usuarios_premium,
            'total_produtos': total_produtos,
            'total_admins': total_admins,
            'total_equipamentos': total_equipamentos
        }

        admin_level = session.get('admin_level', 'admin')

    except Exception as e:
        flash(f'Erro ao carregar painel: {str(e)}')
        stats = {'total_usuarios': 0, 'usuarios_premium': 0, 'total_produtos': 0, 'total_admins': 0, 'total_equipamentos': 0}
        usuarios = []
        produtos = []
        administradores = []
        configuracoes = []
        equipamentos = []
        admin_level = 'admin'

    finally:
        conn.close()

    return render_template('admin.html',
                           stats=stats,
                           usuarios=usuarios,
                           produtos=produtos,
                           administradores=administradores,
                           configuracoes=configuracoes,
                           equipamentos=equipamentos,
                           admin_level=admin_level)


@app.route('/admin/ativar_premium/<int:user_id>')
@admin_required
def ativar_premium(user_id):
    conn = sqlite3.connect('agri_vendas.db')
    c = conn.cursor()

    # Ativar premium por 30 dias
    data_expira = datetime.datetime.now() + datetime.timedelta(days=30)
    c.execute("UPDATE usuarios SET premium = 1, data_premium_expira = ? WHERE id = ?",
              (data_expira.date(), user_id))

    conn.commit()
    conn.close()

    flash('Premium ativado com sucesso!')
    return redirect(url_for('admin_panel'))


@app.route('/admin/desativar_premium/<int:user_id>')
@admin_required
def desativar_premium(user_id):
    conn = sqlite3.connect('agri_vendas.db')
    c = conn.cursor()
    c.execute("UPDATE usuarios SET premium = 0, data_premium_expira = NULL WHERE id = ?",
              (user_id,))
    conn.commit()
    conn.close()

    flash('Premium desativado!')
    return redirect(url_for('admin_panel'))


@app.route('/admin/remover_produto/<int:produto_id>')
@admin_required
def remover_produto(produto_id):
    conn = sqlite3.connect('agri_vendas.db')
    c = conn.cursor()
    c.execute("UPDATE produtos SET ativo = 0 WHERE id = ?", (produto_id,))
    conn.commit()
    conn.close()

    flash('Produto removido!')
    return redirect(url_for('admin_panel'))


# ===================== EQUIPAMENTOS (SUPER ADMIN) =====================

@app.route('/admin/equipamentos')
@superadmin_required
def listar_equipamentos():
    conn = sqlite3.connect('agri_vendas.db')
    c = conn.cursor()
    c.execute('''SELECT * FROM equipamentos WHERE ativo = 1 ORDER BY data_criacao DESC''')
    equipamentos = c.fetchall()
    conn.close()
    return render_template('admin_equipamentos.html', equipamentos=equipamentos)


@app.route('/admin/equipamentos/novo', methods=['GET', 'POST'])
@superadmin_required
def novo_equipamento():
    if request.method == 'POST':
        nome = request.form['nome']
        descricao = request.form.get('descricao', '')
        preco = float(request.form['preco'])
        categoria = request.form.get('categoria', 'Equipamento Agrícola')
        estoque = int(request.form.get('estoque', 1))
        localizacao = request.form.get('localizacao', '')
        contato = request.form.get('contato', '')
        
        foto_url = ''
        if 'foto' in request.files:
            file = request.files['foto']
            if file.filename != '':
                filename = secure_filename(file.filename)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                foto_url = f'uploads/{filename}'
        
        conn = sqlite3.connect('agri_vendas.db')
        c = conn.cursor()
        c.execute('''INSERT INTO equipamentos 
                    (nome, descricao, preco, categoria, estoque, foto_url, localizacao, contato, criado_por)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                  (nome, descricao, preco, categoria, estoque, foto_url, localizacao, contato, 
                   session.get('user_id', 1)))
        conn.commit()
        conn.close()
        
        flash('Equipamento adicionado com sucesso!')
        return redirect(url_for('admin_panel'))
    
    return render_template('admin_equipamento_form.html', equipamento=None, action='novo')


@app.route('/admin/equipamentos/<int:equip_id>/editar', methods=['GET', 'POST'])
@superadmin_required
def editar_equipamento(equip_id):
    conn = sqlite3.connect('agri_vendas.db')
    c = conn.cursor()
    
    if request.method == 'POST':
        nome = request.form['nome']
        descricao = request.form.get('descricao', '')
        preco = float(request.form['preco'])
        categoria = request.form.get('categoria', 'Equipamento Agrícola')
        estoque = int(request.form.get('estoque', 1))
        localizacao = request.form.get('localizacao', '')
        contato = request.form.get('contato', '')
        status = request.form.get('status', 'disponivel')
        
        # Verificar se há nova foto
        foto_url = request.form.get('foto_atual', '')
        if 'foto' in request.files:
            file = request.files['foto']
            if file.filename != '':
                filename = secure_filename(file.filename)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                foto_url = f'uploads/{filename}'
        
        c.execute('''UPDATE equipamentos SET 
                    nome=?, descricao=?, preco=?, categoria=?, estoque=?, 
                    foto_url=?, localizacao=?, contato=?, status=?
                    WHERE id=?''',
                  (nome, descricao, preco, categoria, estoque, foto_url, localizacao, contato, status, equip_id))
        conn.commit()
        conn.close()
        
        flash('Equipamento atualizado com sucesso!')
        return redirect(url_for('admin_panel'))
    
    c.execute("SELECT * FROM equipamentos WHERE id = ?", (equip_id,))
    equipamento = c.fetchone()
    conn.close()
    
    if not equipamento:
        flash('Equipamento não encontrado!')
        return redirect(url_for('admin_panel'))
    
    return render_template('admin_equipamento_form.html', equipamento=equipamento, action='editar')


@app.route('/admin/equipamentos/<int:equip_id>/remover')
@superadmin_required
def remover_equipamento(equip_id):
    conn = sqlite3.connect('agri_vendas.db')
    c = conn.cursor()
    c.execute("UPDATE equipamentos SET ativo = 0 WHERE id = ?", (equip_id,))
    conn.commit()
    conn.close()
    
    flash('Equipamento removido com sucesso!')
    return redirect(url_for('admin_panel'))


# ===================== LOJA DE EQUIPAMENTOS =====================

@app.route('/loja')
def loja_equipamentos():
    filtro_categoria = request.args.get('categoria', '')
    filtro_preco_max = request.args.get('preco_max', '')
    
    conn = sqlite3.connect('agri_vendas.db')
    c = conn.cursor()
    
    query = '''SELECT * FROM equipamentos WHERE ativo = 1 AND status = 'disponivel' '''
    params = []
    
    if filtro_categoria:
        query += ' AND categoria = ?'
        params.append(filtro_categoria)
    
    if filtro_preco_max:
        query += ' AND preco <= ?'
        params.append(float(filtro_preco_max))
    
    query += ' ORDER BY data_criacao DESC'
    
    c.execute(query, params)
    equipamentos = c.fetchall()
    conn.close()
    
    return render_template('loja.html', equipamentos=equipamentos)


@app.route('/produtos')
def listar_produtos():
    filtro_categoria = request.args.get('categoria', '')
    filtro_preco_max = request.args.get('preco_max', '')
    filtro_regiao = request.args.get('regiao', '')

    conn = sqlite3.connect('agri_vendas.db')
    c = conn.cursor()

    query = '''SELECT p.*, u.nome_completo, u.telefone 
              FROM produtos p 
              JOIN usuarios u ON p.vendedor_id = u.id 
              WHERE p.ativo = 1 AND u.ativo = 1'''
    params = []

    if filtro_categoria:
        query += ' AND p.categoria = ?'
        params.append(filtro_categoria)

    if filtro_preco_max:
        query += ' AND p.preco <= ?'
        params.append(float(filtro_preco_max))

    if filtro_regiao:
        query += ' AND p.localizacao LIKE ?'
        params.append(f'%{filtro_regiao}%')

    query += ' ORDER BY p.data_publicacao DESC'

    c.execute(query, params)
    produtos = c.fetchall()
    conn.close()

    return render_template('produtos.html', produtos=produtos)


@app.route('/admin/acesso', methods=['GET', 'POST'])
def validar_acesso_admin():
    if request.method == 'GET':
        return render_template('admin_acesso.html')

    codigo = request.form.get('codigo')

    conn = sqlite3.connect('agri_vendas.db')
    c = conn.cursor()
    c.execute("SELECT codigo_acesso FROM configuracoes_admin ORDER BY id DESC LIMIT 1")
    codigo_atual = c.fetchone()
    conn.close()

    if codigo_atual and codigo == codigo_atual[0]:
        session['admin_access_code'] = codigo
        session['admin_level'] = 'superadmin'
        flash('Acesso de super administrador concedido!')
        return redirect(url_for('admin_panel'))
    else:
        flash('Código de acesso incorreto!')
        return render_template('admin_acesso.html')


@app.route('/admin/nomear_admin', methods=['POST'])
@superadmin_required
def nomear_admin():
    user_id = request.form.get('user_id')
    nivel = request.form.get('nivel', 'admin')

    conn = sqlite3.connect('agri_vendas.db')
    c = conn.cursor()

    # Verificar se usuário existe
    c.execute("SELECT nome_completo FROM usuarios WHERE id = ? AND ativo = 1", (user_id,))
    user = c.fetchone()

    if not user:
        flash('Usuário não encontrado!')
        conn.close()
        return redirect(url_for('admin_panel'))

    # Verificar se já é admin
    c.execute("SELECT id FROM administradores WHERE usuario_id = ? AND ativo = 1", (user_id,))
    if c.fetchone():
        flash('Usuário já é administrador!')
        conn.close()
        return redirect(url_for('admin_panel'))

    # Atualizar tipo do usuário
    c.execute("UPDATE usuarios SET tipo = 'admin' WHERE id = ?", (user_id,))

    # Inserir na tabela de administradores
    nomeado_por = session.get('user_id', 1)  # 1 é o ID do Ibrahim
    c.execute('''INSERT INTO administradores (usuario_id, nivel_acesso, nomeado_por) 
                VALUES (?, ?, ?)''', (user_id, nivel, nomeado_por))

    conn.commit()
    conn.close()

    flash(f'{user[0]} foi nomeado como administrador!')
    return redirect(url_for('admin_panel'))


@app.route('/admin/remover_admin/<int:admin_id>')
@superadmin_required
def remover_admin(admin_id):
    conn = sqlite3.connect('agri_vendas.db')
    c = conn.cursor()

    # Verificar se é o super admin
    c.execute('''SELECT a.usuario_id, a.nivel_acesso 
                FROM administradores a 
                WHERE a.id = ?''', (admin_id,))
    result = c.fetchone()

    if result and result[1] == 'superadmin':
        flash('Não é possível remover o super administrador!')
        conn.close()
        return redirect(url_for('admin_panel'))

    # Desativar administrador
    c.execute("UPDATE administradores SET ativo = 0 WHERE id = ?", (admin_id,))

    # Alterar tipo do usuário para vendedor
    if result:
        c.execute("UPDATE usuarios SET tipo = 'vendedor' WHERE id = ?", (result[0],))

    conn.commit()
    conn.close()

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

    conn = sqlite3.connect('agri_vendas.db')
    c = conn.cursor()

    alterado_por = session.get('user_id', 1)
    c.execute('''UPDATE configuracoes_sistema 
                SET valor = ?, data_alteracao = CURRENT_TIMESTAMP, alterado_por = ? 
                WHERE chave = ?''', (valor, alterado_por, chave))

    conn.commit()
    conn.close()

    flash('Configuração atualizada com sucesso!')
    return redirect(url_for('admin_panel'))


@app.route('/admin/banir_usuario/<int:user_id>')
@admin_required
def banir_usuario(user_id):
    # Não permitir banir administradores
    conn = sqlite3.connect('agri_vendas.db')
    c = conn.cursor()

    c.execute("SELECT tipo FROM usuarios WHERE id = ?", (user_id,))
    user = c.fetchone()

    if user and user[0] == 'admin':
        flash('Não é possível banir administradores!')
        conn.close()
        return redirect(url_for('admin_panel'))

    c.execute("UPDATE usuarios SET ativo = 0 WHERE id = ?", (user_id,))
    c.execute("UPDATE produtos SET ativo = 0 WHERE vendedor_id = ?", (user_id,))

    conn.commit()
    conn.close()

    flash('Usuário banido e produtos removidos!')
    return redirect(url_for('admin_panel'))


@app.route('/admin/reativar_usuario/<int:user_id>')
@admin_required
def reativar_usuario(user_id):
    conn = sqlite3.connect('agri_vendas.db')
    c = conn.cursor()
    c.execute("UPDATE usuarios SET ativo = 1 WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()

    flash('Usuário reativado!')
    return redirect(url_for('admin_panel'))


@app.route('/admin/recuperar-codigo', methods=['GET', 'POST'])
def recuperar_codigo_admin():
    if request.method == 'GET':
        return render_template('admin_recuperacao.html')

    tipo_recuperacao = request.form.get('tipo')

    conn = sqlite3.connect('agri_vendas.db')
    c = conn.cursor()
    c.execute("SELECT * FROM configuracoes_admin ORDER BY id DESC LIMIT 1")
    config = c.fetchone()
    conn.close()

    if not config:
        flash('Configuração não encontrada!')
        return render_template('admin_recuperacao.html')

    if tipo_recuperacao == 'email':
        email = request.form.get('email')
        if email == config[3]:  # email_recuperacao
            flash(f'Código de acesso enviado para seu WhatsApp: {config[4]}')
            return render_template('admin_recuperacao.html', codigo_revelado=config[1])
        else:
            flash('Email não confere!')

    elif tipo_recuperacao == 'telefone':
        telefone = request.form.get('telefone')
        if telefone == config[4]:  # telefone_recuperacao
            flash(f'Código de acesso: {config[1]}')
            return render_template('admin_recuperacao.html', codigo_revelado=config[1])
        else:
            flash('Telefone não confere!')

    elif tipo_recuperacao == 'seguranca':
        resposta = request.form.get('resposta')
        if resposta.lower() == config[6].lower():  # resposta_seguranca
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

    conn = sqlite3.connect('agri_vendas.db')
    c = conn.cursor()

    # Atualizar configuração existente
    c.execute('''UPDATE configuracoes_admin SET 
                codigo_acesso = ?, nome_completo = ?, email_recuperacao = ?, 
                telefone_recuperacao = ?, pergunta_seguranca = ?, resposta_seguranca = ?,
                data_alteracao = CURRENT_TIMESTAMP''',
              (novo_codigo, nome_completo, email_recuperacao, telefone_recuperacao,
               pergunta_seguranca, resposta_seguranca))

    conn.commit()
    conn.close()

    # Atualizar sessão com novo código
    session['admin_access_code'] = novo_codigo

    flash('Configurações de administrador atualizadas com sucesso!')
    return redirect(url_for('admin_panel'))


@app.route('/api/stats')
@admin_required
def api_stats():
    """API endpoint para estatísticas em tempo real"""
    conn = sqlite3.connect('agri_vendas.db')
    c = conn.cursor()
    
    c.execute("SELECT COUNT(*) FROM usuarios WHERE ativo = 1")
    usuarios = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM produtos WHERE ativo = 1")
    produtos = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM usuarios WHERE premium = 1 AND ativo = 1")
    premium = c.fetchone()[0]
    
    conn.close()
    
    return jsonify({
        'usuarios': usuarios,
        'produtos': produtos,
        'premium': premium,
        'timestamp': datetime.datetime.now().isoformat()
    })


@app.route('/admin/supervisor')
@nivel_admin_required('supervisor')
def admin_supervisor():
    """Painel para administradores supervisores"""
    conn = sqlite3.connect('agri_vendas.db')
    c = conn.cursor()
    
    c.execute("SELECT COUNT(*) FROM usuarios WHERE ativo = 1")
    total_usuarios = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM produtos WHERE ativo = 1")
    total_produtos = c.fetchone()[0]
    
    stats = {
        'total_usuarios': total_usuarios,
        'total_produtos': total_produtos
    }
    
    conn.close()
    return render_template('admin_supervisor.html', stats=stats)


@app.route('/admin/relatorios')
@admin_required
def relatorios_admin():
    conn = sqlite3.connect('agri_vendas.db')
    c = conn.cursor()

    # Relatório de crescimento mensal
    c.execute('''SELECT strftime('%Y-%m', data_cadastro) as mes, COUNT(*) as novos_usuarios
                FROM usuarios WHERE ativo = 1 
                GROUP BY mes ORDER BY mes DESC LIMIT 12''')
    crescimento_usuarios = c.fetchall()

    # Produtos mais populares por categoria
    c.execute('''SELECT categoria, COUNT(*) as total 
                FROM produtos WHERE ativo = 1 
                GROUP BY categoria ORDER BY total DESC''')
    produtos_categoria = c.fetchall()

    # Vendedores mais ativos
    c.execute('''SELECT u.nome_completo, u.telefone, COUNT(p.id) as total_produtos
                FROM usuarios u 
                JOIN produtos p ON u.id = p.vendedor_id 
                WHERE p.ativo = 1 AND u.ativo = 1
                GROUP BY u.id ORDER BY total_produtos DESC LIMIT 10''')
    vendedores_ativos = c.fetchall()

    conn.close()

    return render_template('admin_relatorios.html',
                           crescimento=crescimento_usuarios,
                           categorias=produtos_categoria,
                           vendedores=vendedores_ativos)


# ===================== ROTAS ADMINISTRADORES ESPECIALIZADOS =====================

@app.route('/admin/produtos')
@nivel_admin_required('produtos')
def admin_produtos():
    conn = sqlite3.connect('agri_vendas.db')
    c = conn.cursor()
    
    c.execute("SELECT COUNT(*) FROM produtos WHERE ativo = 1")
    total_produtos = c.fetchone()[0]
    
    c.execute('''SELECT p.*, u.nome_completo 
                FROM produtos p 
                JOIN usuarios u ON p.vendedor_id = u.id 
                WHERE p.ativo = 1
                ORDER BY p.data_publicacao DESC''')
    produtos = c.fetchall()
    
    stats = {
        'total_produtos': total_produtos,
        'produtos_pendentes': 0,
        'produtos_inativos': 0,
        'produtos_mes': 0
    }
    
    conn.close()
    return render_template('admin_produtos.html', produtos=produtos, stats=stats)


@app.route('/admin/financeiro')
@nivel_admin_required('financeiro')
def admin_financeiro():
    conn = sqlite3.connect('agri_vendas.db')
    c = conn.cursor()
    
    c.execute("SELECT COUNT(*) FROM usuarios WHERE premium = 1 AND ativo = 1")
    usuarios_premium = c.fetchone()[0]
    
    c.execute("SELECT valor FROM configuracoes_sistema WHERE chave = 'numero_emola'")
    numero_emola = c.fetchone()
    
    c.execute("SELECT valor FROM configuracoes_sistema WHERE chave = 'numero_mpesa'")
    numero_mpesa = c.fetchone()
    
    stats = {
        'usuarios_premium': usuarios_premium,
        'receita_total': usuarios_premium * 500,
        'receita_mes': usuarios_premium * 500
    }
    
    configuracoes_pagamento = {
        'numero_emola': numero_emola[0] if numero_emola else '878312890',
        'numero_mpesa': numero_mpesa[0] if numero_mpesa else '847214191'
    }
    
    conn.close()
    return render_template('admin_financeiro.html', stats=stats, configuracoes_pagamento=configuracoes_pagamento)


@app.route('/admin/equipamentos-gestao')
@nivel_admin_required('equipamentos')
def admin_equipamentos_gestao():
    conn = sqlite3.connect('agri_vendas.db')
    c = conn.cursor()
    c.execute("SELECT * FROM equipamentos WHERE ativo = 1 ORDER BY data_criacao DESC")
    equipamentos = c.fetchall()
    conn.close()
    return render_template('admin_equipamentos.html', equipamentos=equipamentos)


@app.route('/admin/usuarios')
@nivel_admin_required('usuarios')
def admin_usuarios():
    conn = sqlite3.connect('agri_vendas.db')
    c = conn.cursor()
    
    c.execute("SELECT COUNT(*) FROM usuarios WHERE ativo = 1")
    total_usuarios = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM usuarios WHERE premium = 1 AND ativo = 1")
    usuarios_premium = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM usuarios WHERE tipo = 'vendedor' AND ativo = 1")
    vendedores = c.fetchone()[0]
    
    c.execute('''SELECT id, nome_completo, email, telefone, tipo, premium, data_premium_expira, data_cadastro, ativo
                FROM usuarios 
                ORDER BY data_cadastro DESC''')
    usuarios = c.fetchall()
    
    stats = {
        'total_usuarios': total_usuarios,
        'usuarios_premium': usuarios_premium,
        'vendedores': vendedores,
        'usuarios_ativos': total_usuarios
    }
    
    conn.close()
    return render_template('admin_usuarios.html', usuarios=usuarios, stats=stats)


@app.route('/contato/<int:vendedor_id>')
def contato_whatsapp(vendedor_id):
    conn = sqlite3.connect('agri_vendas.db')
    c = conn.cursor()
    c.execute("SELECT nome_completo, telefone FROM usuarios WHERE id = ? AND ativo = 1", (vendedor_id,))
    vendedor = c.fetchone()
    conn.close()

    if vendedor:
        telefone = vendedor[1]
        # Remover caracteres não numéricos
        telefone_limpo = re.sub(r'\D', '', telefone)

        # Assumir código do país +258 (Moçambique) se não tiver
        if not telefone_limpo.startswith('258'):
            telefone_limpo = '258' + telefone_limpo

        mensagem = f"Olá {vendedor[0]}, vi seu produto no AGRI.vendasMz e tenho interesse!"
        whatsapp_url = f"https://wa.me/{telefone_limpo}?text={mensagem}"

        return redirect(whatsapp_url)

    flash('Vendedor não encontrado')
    return redirect(url_for('index'))



if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000, debug=True)