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

    # Inserir configurações padrão
    c.execute("INSERT OR IGNORE INTO configuracoes_sistema (chave, valor, descricao) VALUES (?, ?, ?)",
              ('numero_emola', '878312890', 'Número E-MOLA para pagamentos'))
    c.execute("INSERT OR IGNORE INTO configuracoes_sistema (chave, valor, descricao) VALUES (?, ?, ?)",
              ('numero_mpesa', '847214191', 'Número M-PESA para pagamentos'))
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
    hectares = float(request.form['hectares'])

    # Base de dados completa e expandida de culturas
    dados_culturas = {
        # CEREAIS
        'milho': {
            'sementes_por_ha': 20, 'fertilizante_npk': 150, 'irrigacao_dias': [7, 14, 21, 35, 50],
            'colheita_dias': 120, 'rendimento_medio': 3500, 'custo_por_ha': 15000,
            'solo_ideal': 'Solo bem drenado, pH 6.0-7.0', 'altitude_ideal': '0-1800m',
            'temperatura_ideal': '18-32°C', 'epoca_plantio': 'Out-Dez (época chuvosa)',
            'pragas_comuns': ['Lagarta-do-cartucho', 'Broca-do-colmo', 'Curuquerê', 'Pulgão'],
            'doencas_comuns': ['Ferrugem', 'Mancha-branca', 'Podridão-do-colmo', 'Cercosporiose'],
            'categoria': 'cereais'
        },
        'arroz': {
            'sementes_por_ha': 120, 'fertilizante_npk': 180, 'irrigacao_dias': [7, 14, 21, 35, 50, 70],
            'colheita_dias': 110, 'rendimento_medio': 4000, 'custo_por_ha': 18000,
            'solo_ideal': 'Solo argiloso, com boa retenção de água, pH 5.5-6.5',
            'altitude_ideal': '0-1000m', 'temperatura_ideal': '22-32°C',
            'epoca_plantio': 'Nov-Jan (irrigado), Mar-Mai (sequeiro)',
            'pragas_comuns': ['Broca-do-colmo', 'Percevejo-do-grão', 'Lagarta-das-folhas'],
            'doencas_comuns': ['Brusone', 'Queima-das-bainhas', 'Mancha-parda'],
            'categoria': 'cereais'
        },
        # Adicionar mais culturas conforme necessário
        'feijao': {
            'sementes_por_ha': 50, 'fertilizante_npk': 200, 'irrigacao_dias': [5, 10, 20, 30, 45],
            'colheita_dias': 90, 'rendimento_medio': 1200, 'custo_por_ha': 12000,
            'solo_ideal': 'Solo franco, bem drenado, pH 6.0-6.5',
            'altitude_ideal': '0-2000m', 'temperatura_ideal': '16-28°C',
            'epoca_plantio': 'Set-Nov (época das águas)',
            'pragas_comuns': ['Vaquinha', 'Mosca-branca', 'Ácaro-rajado', 'Cigarrinha'],
            'doencas_comuns': ['Antracnose', 'Ferrugem', 'Murcha-de-fusário', 'Mancha-angular'],
            'categoria': 'leguminosas'
        },
        'tomate': {
            'sementes_por_ha': 1, 'fertilizante_npk': 300, 'irrigacao_dias': [3, 6, 9, 12, 18, 25],
            'colheita_dias': 75, 'rendimento_medio': 40000, 'custo_por_ha': 25000,
            'solo_ideal': 'Solo orgânico, bem drenado, pH 6.0-6.8',
            'altitude_ideal': '0-1500m', 'temperatura_ideal': '18-26°C',
            'epoca_plantio': 'Ano todo (com irrigação)',
            'pragas_comuns': ['Broca-pequena', 'Mosca-branca', 'Trips', 'Ácaro-rajado'],
            'doencas_comuns': ['Requeima', 'Murcha-bacteriana', 'Vírus-do-mosaico', 'Alternária'],
            'categoria': 'horticolas'
        }
    }

    if cultura not in dados_culturas:
        return jsonify({'erro': 'Cultura não encontrada'})

    dados = dados_culturas[cultura]
    resultado = {
        'cultura': cultura,
        'hectares': hectares,
        'sementes_necessarias': dados['sementes_por_ha'] * hectares,
        'fertilizante_npk': dados['fertilizante_npk'] * hectares,
        'cronograma_irrigacao': dados['irrigacao_dias'],
        'dias_para_colheita': dados['colheita_dias'],
        'rendimento_esperado': dados['rendimento_medio'] * hectares,
        'custo_estimado': dados['custo_por_ha'] * hectares,
        'receita_estimada': (dados['rendimento_medio'] * hectares * 30),  # 30 MT/kg estimado
        'lucro_estimado': (dados['rendimento_medio'] * hectares * 30) - (dados['custo_por_ha'] * hectares)
    }

    # Informações detalhadas apenas para premium
    if session.get('is_premium'):
        resultado['detalhes_premium'] = {
            'solo_ideal': dados['solo_ideal'],
            'altitude_ideal': dados['altitude_ideal'],
            'temperatura_ideal': dados['temperatura_ideal'],
            'pragas_comuns': dados['pragas_comuns'],
            'doencas_comuns': dados['doencas_comuns'],
            'epoca_plantio': dados['epoca_plantio']
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

        stats = {
            'total_usuarios': total_usuarios,
            'usuarios_premium': usuarios_premium,
            'total_produtos': total_produtos,
            'total_admins': total_admins
        }

        admin_level = session.get('admin_level', 'admin')

    except Exception as e:
        flash(f'Erro ao carregar painel: {str(e)}')
        stats = {'total_usuarios': 0, 'usuarios_premium': 0, 'total_produtos': 0, 'total_admins': 0}
        usuarios = []
        produtos = []
        administradores = []
        configuracoes = []
        admin_level = 'admin'

    finally:
        conn.close()

    return render_template('admin.html',
                           stats=stats,
                           usuarios=usuarios,
                           produtos=produtos,
                           administradores=administradores,
                           configuracoes=configuracoes,
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