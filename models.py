import sqlite3
from werkzeug.security import generate_password_hash
import datetime

class Database:
    """Database class com funcionalidades básicas"""

    def __init__(self, db_path):
        self.db_path = db_path

    def get_connection(self):
        return sqlite3.connect(self.db_path)

    def init_db(self):
        conn = self.get_connection()
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

    def _check_user_active(self, user_id):
        """Verifica se usuário está ativo"""
        conn = self.get_connection()
        c = conn.cursor()
        c.execute("SELECT ativo FROM usuarios WHERE id = ?", (user_id,))
        result = c.fetchone()
        conn.close()
        return result and result[0] == 1

    def get_user_by_credentials(self, login_field, senha):
        conn = self.get_connection()
        c = conn.cursor()
        c.execute('''SELECT id, nome_completo, senha_hash, tipo, premium
                    FROM usuarios
                    WHERE (email = ? OR telefone = ?) AND ativo = 1''',
                  (login_field, login_field))
        user = c.fetchone()
        conn.close()
        return user

    def create_user(self, nome, email, telefone, senha, tipo):
        conn = self.get_connection()
        c = conn.cursor()
        senha_hash = generate_password_hash(senha)
        c.execute('''INSERT INTO usuarios
                    (nome_completo, email, telefone, senha_hash, tipo)
                    VALUES (?, ?, ?, ?, ?)''',
                  (nome, email, telefone, senha_hash, tipo))
        conn.commit()
        conn.close()

    def get_products(self, limit=20):
        conn = self.get_connection()
        c = conn.cursor()
        c.execute('''SELECT p.*, u.nome_completo, u.telefone
                    FROM produtos p
                    JOIN usuarios u ON p.vendedor_id = u.id
                    WHERE p.ativo = 1 AND u.ativo = 1
                    ORDER BY p.data_publicacao DESC LIMIT ?''', (limit,))
        produtos = c.fetchall()
        conn.close()
        return produtos

    def create_product(self, vendedor_id, nome, preco, descricao, localizacao, foto_url, categoria):
        conn = self.get_connection()
        c = conn.cursor()
        c.execute('''INSERT INTO produtos
                    (vendedor_id, nome, preco, descricao, localizacao, foto_url, categoria)
                    VALUES (?, ?, ?, ?, ?, ?, ?)''',
                  (vendedor_id, nome, preco, descricao, localizacao, foto_url, categoria))
        conn.commit()
        conn.close()

    def get_user_products(self, user_id):
        conn = self.get_connection()
        c = conn.cursor()
        c.execute('''SELECT * FROM produtos
                    WHERE vendedor_id = ? AND ativo = 1
                    ORDER BY data_publicacao DESC''',
                  (user_id,))
        produtos = c.fetchall()
        conn.close()
        return produtos

    def get_user_count(self, user_id):
        conn = self.get_connection()
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM produtos WHERE vendedor_id = ? AND ativo = 1",
                  (user_id,))
        count = c.fetchone()[0]
        conn.close()
        return count

    def get_admin_config(self):
        conn = self.get_connection()
        c = conn.cursor()
        c.execute("SELECT * FROM configuracoes_admin ORDER BY id DESC LIMIT 1")
        config = c.fetchone()
        conn.close()
        return config

    def update_admin_config(self, codigo_acesso, nome_completo, email_recuperacao, telefone_recuperacao, pergunta_seguranca, resposta_seguranca):
        conn = self.get_connection()
        c = conn.cursor()
        c.execute('''UPDATE configuracoes_admin SET
                    codigo_acesso = ?, nome_completo = ?, email_recuperacao = ?,
                    telefone_recuperacao = ?, pergunta_seguranca = ?, resposta_seguranca = ?,
                    data_alteracao = CURRENT_TIMESTAMP''',
                  (codigo_acesso, nome_completo, email_recuperacao, telefone_recuperacao,
                   pergunta_seguranca, resposta_seguranca))
        conn.commit()
        conn.close()

    def get_equipments(self):
        conn = self.get_connection()
        c = conn.cursor()
        c.execute("SELECT * FROM equipamentos WHERE ativo = 1 ORDER BY data_criacao DESC")
        equipamentos = c.fetchall()
        conn.close()
        return equipamentos

    def create_equipment(self, nome, descricao, preco, categoria, estoque, foto_url, localizacao, contato, criado_por):
        conn = self.get_connection()
        c = conn.cursor()
        c.execute('''INSERT INTO equipamentos
                    (nome, descricao, preco, categoria, estoque, foto_url, localizacao, contato, criado_por)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                  (nome, descricao, preco, categoria, estoque, foto_url, localizacao, contato, criado_por))
        conn.commit()
        conn.close()

    def update_equipment(self, equip_id, nome, descricao, preco, categoria, estoque, foto_url, localizacao, contato, status):
        conn = self.get_connection()
        c = conn.cursor()
        c.execute('''UPDATE equipamentos SET
                    nome=?, descricao=?, preco=?, categoria=?, estoque=?,
                    foto_url=?, localizacao=?, contato=?, status=?
                    WHERE id=?''',
                  (nome, descricao, preco, categoria, estoque, foto_url, localizacao, contato, status, equip_id))
        conn.commit()
        conn.close()

    def delete_equipment(self, equip_id):
        conn = self.get_connection()
        c = conn.cursor()
        c.execute("UPDATE equipamentos SET ativo = 0 WHERE id = ?", (equip_id,))
        conn.commit()
        conn.close()

    def get_equipment_by_id(self, equip_id):
        conn = self.get_connection()
        c = conn.cursor()
        c.execute("SELECT * FROM equipamentos WHERE id = ?", (equip_id,))
        equipamento = c.fetchone()
        conn.close()
        return equipamento

    def get_filtered_equipments(self, categoria=None, preco_max=None):
        conn = self.get_connection()
        c = conn.cursor()

        query = '''SELECT * FROM equipamentos WHERE ativo = 1 AND status = 'disponivel' '''
        params = []

        if categoria:
            query += ' AND categoria = ?'
            params.append(categoria)

        if preco_max:
            query += ' AND preco <= ?'
            params.append(float(preco_max))

        query += ' ORDER BY data_criacao DESC'

        c.execute(query, params)
        equipamentos = c.fetchall()
        conn.close()
        return equipamentos

    def get_filtered_products(self, categoria=None, preco_max=None, regiao=None):
        conn = self.get_connection()
        c = conn.cursor()

        query = '''SELECT p.*, u.nome_completo, u.telefone
                  FROM produtos p
                  JOIN usuarios u ON p.vendedor_id = u.id
                  WHERE p.ativo = 1 AND u.ativo = 1'''
        params = []

        if categoria:
            query += ' AND p.categoria = ?'
            params.append(categoria)

        if preco_max:
            query += ' AND p.preco <= ?'
            params.append(float(preco_max))

        if regiao:
            query += ' AND p.localizacao LIKE ?'
            params.append(f'%{regiao}%')

        query += ' ORDER BY p.data_publicacao DESC'

        c.execute(query, params)
        produtos = c.fetchall()
        conn.close()
        return produtos

    def get_user_by_id(self, user_id):
        conn = self.get_connection()
        c = conn.cursor()
        c.execute("SELECT nome_completo, telefone FROM usuarios WHERE id = ? AND ativo = 1", (user_id,))
        user = c.fetchone()
        conn.close()
        return user

    def get_admin_users(self):
        conn = self.get_connection()
        c = conn.cursor()
        c.execute('''SELECT a.*, u.nome_completo, u.telefone, u2.nome_completo as nomeado_por_nome
                    FROM administradores a
                    JOIN usuarios u ON a.usuario_id = u.id
                    LEFT JOIN usuarios u2 ON a.nomeado_por = u2.id
                    WHERE a.ativo = 1
                    ORDER BY a.data_nomeacao DESC''')
        admins = c.fetchall()
        conn.close()
        return admins

    def get_users(self):
        conn = self.get_connection()
        c = conn.cursor()
        c.execute('''SELECT id, nome_completo, email, telefone, tipo, premium, data_premium_expira, data_cadastro, ativo
                    FROM usuarios
                    ORDER BY data_cadastro DESC''')
        users = c.fetchall()
        conn.close()
        return users

    def activate_premium(self, user_id):
        conn = self.get_connection()
        c = conn.cursor()
        data_expira = datetime.datetime.now() + datetime.timedelta(days=30)
        c.execute("UPDATE usuarios SET premium = 1, data_premium_expira = ? WHERE id = ?",
                  (data_expira.date(), user_id))
        conn.commit()
        conn.close()

    def deactivate_premium(self, user_id):
        conn = self.get_connection()
        c = conn.cursor()
        c.execute("UPDATE usuarios SET premium = 0, data_premium_expira = NULL WHERE id = ?",
                  (user_id,))
        conn.commit()
        conn.close()

    def ban_user(self, user_id):
        conn = self.get_connection()
        c = conn.cursor()
        c.execute("UPDATE usuarios SET ativo = 0 WHERE id = ?", (user_id,))
        c.execute("UPDATE produtos SET ativo = 0 WHERE vendedor_id = ?", (user_id,))
        conn.commit()
        conn.close()

    def unban_user(self, user_id):
        conn = self.get_connection()
        c = conn.cursor()
        c.execute("UPDATE usuarios SET ativo = 1 WHERE id = ?", (user_id,))
        conn.commit()
        conn.close()

    def remove_product(self, produto_id):
        conn = self.get_connection()
        c = conn.cursor()
        c.execute("UPDATE produtos SET ativo = 0 WHERE id = ?", (produto_id,))
        conn.commit()
        conn.close()

    def get_stats(self):
        conn = self.get_connection()
        c = conn.cursor()

        c.execute("SELECT COUNT(*) FROM usuarios WHERE ativo = 1")
        total_usuarios = c.fetchone()[0]

        c.execute("SELECT COUNT(*) FROM usuarios WHERE premium = 1 AND ativo = 1")
        usuarios_premium = c.fetchone()[0]

        c.execute("SELECT COUNT(*) FROM produtos WHERE ativo = 1")
        total_produtos = c.fetchone()[0]

        c.execute("SELECT COUNT(*) FROM administradores WHERE ativo = 1")
        total_admins = c.fetchone()[0]

        c.execute("SELECT COUNT(*) FROM equipamentos WHERE ativo = 1")
        total_equipamentos = c.fetchone()[0]

        conn.close()

        return {
            'total_usuarios': total_usuarios,
            'usuarios_premium': usuarios_premium,
            'total_produtos': total_produtos,
            'total_admins': total_admins,
            'total_equipamentos': total_equipamentos
        }

    def update_config(self, chave, valor, alterado_por):
        conn = self.get_connection()
        c = conn.cursor()
        c.execute('''UPDATE configuracoes_sistema
                    SET valor = ?, data_alteracao = CURRENT_TIMESTAMP, alterado_por = ?
                    WHERE chave = ?''', (valor, alterado_por, chave))
        conn.commit()
        conn.close()

    def get_configs(self):
        conn = self.get_connection()
        c = conn.cursor()
        c.execute("SELECT * FROM configuracoes_sistema ORDER BY chave")
        configs = c.fetchall()
        conn.close()
        return configs

    def nomear_admin(self, user_id, nivel, nomeado_por):
        conn = self.get_connection()
        c = conn.cursor()

        # Verificar se usuário existe
        c.execute("SELECT nome_completo FROM usuarios WHERE id = ? AND ativo = 1", (user_id,))
        user = c.fetchone()

        if not user:
            conn.close()
            return False

        # Verificar se já é admin
        c.execute("SELECT id FROM administradores WHERE usuario_id = ? AND ativo = 1", (user_id,))
        if c.fetchone():
            conn.close()
            return False

        # Atualizar tipo do usuário
        c.execute("UPDATE usuarios SET tipo = 'admin' WHERE id = ?", (user_id,))

        # Inserir na tabela de administradores
        c.execute('''INSERT INTO administradores (usuario_id, nivel_acesso, nomeado_por)
                    VALUES (?, ?, ?)''', (user_id, nivel, nomeado_por))

        conn.commit()
        conn.close()
        return True

    def remover_admin(self, admin_id):
        conn = self.get_connection()
        c = conn.cursor()

        # Verificar se é o super admin
        c.execute('''SELECT a.usuario_id, a.nivel_acesso
                    FROM administradores a
                    WHERE a.id = ?''', (admin_id,))
        result = c.fetchone()

        if result and result[1] == 'superadmin':
            conn.close()
            return False

        # Desativar administrador
        c.execute("UPDATE administradores SET ativo = 0 WHERE id = ?", (admin_id,))

        # Alterar tipo do usuário para vendedor
        if result:
            c.execute("UPDATE usuarios SET tipo = 'vendedor' WHERE id = ?", (result[0],))

        conn.commit()
        conn.close()
        return True

    def get_reports(self):
        conn = self.get_connection()
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

        return {
            'crescimento': crescimento_usuarios,
            'categorias': produtos_categoria,
            'vendedores': vendedores_ativos
        }