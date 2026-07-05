import re
from werkzeug.utils import secure_filename
import os

def validate_email(email):
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def validate_phone(phone):
    # Normalize and validate Mozambique phone numbers.
    # Accepted prefixes: +258, 258, 0 (optional)
    # Accepted networks: Movitel (82/83), Vodacom/Emcel (84-87)
    # Format examples: 828123456, 0828123456, +258828123456
    if not phone:
        return False

    # Remove whitespace and non-digit characters (e.g., spaces, dashes)
    cleaned = re.sub(r'\D', '', phone)

    # Allow optional leading 0, 258, or +258 (handled via digits only)
    if cleaned.startswith('258'):
        cleaned = cleaned[3:]
    elif cleaned.startswith('0'):
        cleaned = cleaned[1:]

    # Now should be 9 digits starting with 8[2-7]
    pattern = r'^8[2-7][0-9]{7}$'
    return re.match(pattern, cleaned) is not None

# MIME types permitidos para upload
ALLOWED_MIME_TYPES = {
    'png': 'image/png',
    'jpg': 'image/jpeg',
    'jpeg': 'image/jpeg',
    'gif': 'image/gif',
    'webp': 'image/webp'
}

def allowed_file(filename, allowed_extensions={'png', 'jpg', 'jpeg', 'gif', 'webp'}):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions

def validate_file_mime(file, allowed_extensions={'png', 'jpg', 'jpeg', 'gif', 'webp'}):
    """Valida o tipo MIME real do arquivo, não apenas a extensão"""
    if not file or not file.filename:
        return False

    ext = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else ''
    if ext not in allowed_extensions:
        return False

    # Ler primeiros bytes para verificar magic number
    file.seek(0)
    header = file.read(32)
    file.seek(0)

    # Verificar assinaturas de arquivo conhecidas
    signatures = {
        b'\x89PNG\r\n\x1a\n': 'png',
        b'\xff\xd8\xff': 'jpg',
        b'GIF87a': 'gif',
        b'GIF89a': 'gif',
        b'RIFF': 'webp',  # WebP começa com RIFF
    }

    for sig, file_type in signatures.items():
        if header.startswith(sig):
            return ext == file_type or (ext == 'jpeg' and file_type == 'jpg')

    return False

def save_uploaded_file(file, upload_folder):
    if file and allowed_file(file.filename) and validate_file_mime(file):
        filename = secure_filename(file.filename)
        filepath = os.path.join(upload_folder, filename)
        file.save(filepath)
        return f'uploads/{filename}'
    return None

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

# Hierarquia de níveis administrativos
NIVEIS_HIERARQUIA = ['equipamentos', 'financeiro', 'produtos', 'usuarios', 'supervisor', 'superadmin']

def get_nivel_hierarquia(nivel):
    return NIVEIS_HIERARQUIA.index(nivel) if nivel in NIVEIS_HIERARQUIA else -1

def check_admin_access(codigo, nivel_minimo):
    if codigo in CODIGOS_ADMIN:
        nivel_usuario = CODIGOS_ADMIN[codigo]
        return get_nivel_hierarquia(nivel_usuario) >= get_nivel_hierarquia(nivel_minimo)
    return False

# Base de dados COMPLETA de todas as culturas
DADOS_CULTURAS = {
    # ===================== CEREAIS =====================
    'milho': {
        'nome': 'Milho', 'sementes_por_ha': 20, 'fertilizante_npk': 150,
        'irrigacao_dias': [7, 14, 21, 35, 50], 'colheita_dias': 120,
        'rendimento_medio': 3500, 'custo_por_ha': 15000, 'preco_venda': 30,
        'solo_ideal': 'Solo bem drenado, pH 6.0-7.0', 'altitude_ideal': '0-1800m',
        'temperatura_ideal': '18-32°C', 'epoca_plantio': 'Out-Dez (época chuvosa)',
        'pragas_comuns': ['Lagarta-do-cartucho', 'Broca-do-colmo', 'Curuquerê', 'Pulgão'],
        'doencas_comuns': ['Ferrugem', 'Mancha-branca', 'Podridão-do-colmo', 'Cercosporiose'],
        'densidade_plantio': '60.000-80.000 plantas/ha', 'categoria': 'cereais',
        'recomenda_solo': 'Realizar calagem se pH < 5.5. Adicionar matéria orgânica.',
        'pos_colheita': 'Secagem até 13% de umidade. Armazenar em silos arejados ou sacos tratados contra caruncho.'
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
        'densidade_plantio': '100-150 kg sementes/ha', 'categoria': 'cereais',
        'recomenda_solo': 'Manter lâmina de água constante. NPK rico em Nitrogênio.',
        'pos_colheita': 'Secagem imediata após colheita para evitar fungos. Limpeza de impurezas antes do armazenamento.'
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
        'nome': 'Mapira (Sorgo local)', 'sementes_por_ha': 8, 'fertilizante_npk': 120,
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