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

    # Tabela de administradores
    c.execute('''CREATE TABLE IF NOT EXISTS administradores (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario_id INTEGER,
        nivel_acesso TEXT DEFAULT 'admin',
        FOREIGN KEY (usuario_id) REFERENCES usuarios (id)
    )''')

    # Inserir admin padrão se não existir
    c.execute("SELECT * FROM usuarios WHERE telefone = '868312890'")
    if not c.fetchone():
        admin_hash = generate_password_hash('12345,Ibrahim')
        c.execute('''INSERT INTO usuarios 
                    (nome_completo, telefone, senha_hash, tipo, premium) 
                    VALUES (?, ?, ?, ?, ?)''',
                  ('Ibrahim Hagi Amane', '868312890', admin_hash, 'admin', 1))

        admin_id = c.lastrowid
        c.execute("INSERT INTO administradores (usuario_id, nivel_acesso) VALUES (?, ?)",
                  (admin_id, 'superadmin'))

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
        if 'user_id' not in session:
            return redirect(url_for('login'))

        conn = sqlite3.connect('agri_vendas.db')
        c = conn.cursor()
        c.execute("SELECT tipo FROM usuarios WHERE id = ?", (session['user_id'],))
        user = c.fetchone()
        conn.close()

        if not user or user[0] != 'admin':
            flash('Acesso negado. Apenas administradores.')
            return redirect(url_for('index'))
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
                WHERE p.ativo = 1 
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

    # Dados básicos de plantio
    dados_culturas = {
        'milho': {
            'sementes_por_ha': 20,  # kg
            'fertilizante_npk': 150,  # kg
            'irrigacao_dias': [7, 14, 21, 35, 50],
            'colheita_dias': 120
        },
        'feijao': {
            'sementes_por_ha': 50,
            'fertilizante_npk': 200,
            'irrigacao_dias': [5, 10, 20, 30, 45],
            'colheita_dias': 90
        },
        'tomate': {
            'sementes_por_ha': 1,  # kg
            'fertilizante_npk': 300,
            'irrigacao_dias': [3, 6, 9, 12, 18, 25],
            'colheita_dias': 75
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
        'dias_para_colheita': dados['colheita_dias']
    }

    # Informações detalhadas apenas para premium
    if session.get('is_premium'):
        resultado['detalhes_premium'] = {
            'densidade_plantio': f"{20000 * hectares:.0f} plantas",
            'cronograma_fertilizacao': [15, 30, 45],
            'pragas_comuns': ['Lagarta', 'Pulgão', 'Ferrugem'],
            'dicas_extras': 'Solo bem drenado, pH entre 6.0-7.0'
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

    # Estatísticas gerais
    c.execute("SELECT COUNT(*) FROM usuarios WHERE ativo = 1")
    total_usuarios = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM usuarios WHERE premium = 1 AND ativo = 1")
    usuarios_premium = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM produtos WHERE ativo = 1")
    total_produtos = c.fetchone()[0]

    # Lista de usuários
    c.execute('''SELECT id, nome_completo, email, telefone, tipo, premium, data_cadastro
                FROM usuarios WHERE ativo = 1 ORDER BY data_cadastro DESC''')
    usuarios = c.fetchall()

    # Lista de produtos
    c.execute('''SELECT p.*, u.nome_completo 
                FROM produtos p 
                JOIN usuarios u ON p.vendedor_id = u.id 
                WHERE p.ativo = 1 
                ORDER BY p.data_publicacao DESC''')
    produtos = c.fetchall()

    conn.close()

    stats = {
        'total_usuarios': total_usuarios,
        'usuarios_premium': usuarios_premium,
        'total_produtos': total_produtos
    }

    return render_template('admin.html', stats=stats, usuarios=usuarios, produtos=produtos)


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
              WHERE p.ativo = 1'''
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


@app.route('/contato/<int:vendedor_id>')
def contato_whatsapp(vendedor_id):
    conn = sqlite3.connect('agri_vendas.db')
    c = conn.cursor()
    c.execute("SELECT nome_completo, telefone FROM usuarios WHERE id = ?", (vendedor_id,))
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