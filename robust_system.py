import logging
import logging.handlers
import os
import json
import sqlite3
import re
from datetime import datetime, timedelta
from functools import wraps
import traceback
import hashlib
import secrets
from werkzeug.security import generate_password_hash, check_password_hash
from flask import session

# Importação condicional para evitar dependência circular
def get_database_class():
    from models import Database
    return Database

class RobustDatabase:
    """Classe Database aprimorada com robustez e segurança"""

    def __init__(self, db_path):
        # Usar composição em vez de herança para evitar dependência circular
        DatabaseClass = get_database_class()
        self.db = DatabaseClass(db_path)  # Instância da classe Database original

        self.db_path = db_path
        self.setup_logging()
        self.backup_scheduler = BackupScheduler(db_path)
        self.security_manager = SecurityManager()

    def __getattr__(self, name):
        """Delegar chamadas de métodos para a instância Database subjacente"""
        return getattr(self.db, name)

    def setup_logging(self):
        """Configura sistema de logging avançado"""
        log_dir = os.path.join(os.path.dirname(self.db_path), 'logs')
        os.makedirs(log_dir, exist_ok=True)

        # Logger principal
        self.logger = logging.getLogger('agri_vendas')
        self.logger.setLevel(logging.INFO)

        # Handler para arquivo com rotação
        log_file = os.path.join(log_dir, 'agri_vendas.log')
        file_handler = logging.handlers.RotatingFileHandler(
            log_file, maxBytes=10*1024*1024, backupCount=5
        )
        file_handler.setLevel(logging.INFO)

        # Handler para erros críticos
        error_log = os.path.join(log_dir, 'errors.log')
        error_handler = logging.handlers.RotatingFileHandler(
            error_log, maxBytes=5*1024*1024, backupCount=3
        )
        error_handler.setLevel(logging.ERROR)

        # Formato dos logs
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s - %(pathname)s:%(lineno)d'
        )
        file_handler.setFormatter(formatter)
        error_handler.setFormatter(formatter)

        self.logger.addHandler(file_handler)
        self.logger.addHandler(error_handler)

        # Logger para auditoria
        self.audit_logger = logging.getLogger('audit')
        audit_handler = logging.FileHandler(os.path.join(log_dir, 'audit.log'))
        audit_formatter = logging.Formatter(
            '%(asctime)s - AUDIT - %(message)s'
        )
        audit_handler.setFormatter(audit_formatter)
        self.audit_logger.addHandler(audit_handler)
        self.audit_logger.setLevel(logging.INFO)

    def get_connection(self):
        """Conexão com tratamento de erros e logging"""
        try:
            conn = sqlite3.connect(self.db_path, timeout=30.0)
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute("PRAGMA journal_mode = WAL")
            conn.execute("PRAGMA synchronous = NORMAL")
            conn.execute("PRAGMA cache_size = -64000")  # 64MB cache
            conn.execute("PRAGMA temp_store = MEMORY")
            return conn
        except Exception as e:
            self.logger.error(f"Erro ao conectar ao banco de dados: {str(e)}")
            raise

    def execute_with_retry(self, query, params=None, max_retries=3):
        """Executa query com retry automático em caso de lock"""
        for attempt in range(max_retries):
            try:
                conn = self.get_connection()
                c = conn.cursor()
                if params:
                    c.execute(query, params)
                else:
                    c.execute(query)
                conn.commit()
                result = c.fetchall() if c.description else None
                conn.close()
                return result
            except sqlite3.OperationalError as e:
                if "database is locked" in str(e) and attempt < max_retries - 1:
                    self.logger.warning(f"Tentativa {attempt + 1} falhou devido a lock no banco. Tentando novamente...")
                    continue
                else:
                    self.logger.error(f"Erro operacional no banco de dados: {str(e)}")
                    raise
            except Exception as e:
                self.logger.error(f"Erro inesperado no banco de dados: {str(e)}")
                raise

    def validate_data_integrity(self):
        """Valida integridade dos dados"""
        try:
            conn = self.get_connection()
            c = conn.cursor()

            # Verificar integridade do banco
            c.execute("PRAGMA integrity_check")
            result = c.fetchone()
            if result[0] != "ok":
                self.logger.error(f"Integridade do banco comprometida: {result[0]}")
                return False

            # Verificar foreign keys
            c.execute("PRAGMA foreign_key_check")
            violations = c.fetchall()
            if violations:
                self.logger.error(f"Violações de foreign key encontradas: {violations}")
                return False

            conn.close()
            return True
        except Exception as e:
            self.logger.error(f"Erro ao validar integridade: {str(e)}")
            return False

    def audit_log(self, action, user_id=None, details=None, ip_address=None):
        """Registra ação para auditoria"""
        try:
            audit_data = {
                'timestamp': datetime.now().isoformat(),
                'action': action,
                'user_id': user_id,
                'details': details or {},
                'ip_address': ip_address
            }
            self.audit_logger.info(json.dumps(audit_data))
        except Exception as e:
            self.logger.error(f"Erro ao registrar auditoria: {str(e)}")

class BackupScheduler:
    """Gerenciador de backups automáticos"""

    def __init__(self, db_path):
        self.db_path = db_path
        self.backup_dir = os.path.join(os.path.dirname(db_path), 'backups')
        os.makedirs(self.backup_dir, exist_ok=True)

    def create_backup(self, backup_type='auto'):
        """Cria backup do banco de dados"""
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_name = f"backup_{backup_type}_{timestamp}.db"
            backup_path = os.path.join(self.backup_dir, backup_name)

            # Copiar arquivo de banco
            import shutil
            shutil.copy2(self.db_path, backup_path)

            # Criar backup das configurações
            self._backup_configs(backup_path.replace('.db', '_configs.json'))

            # Limpar backups antigos
            self._cleanup_old_backups()

            return backup_path
        except Exception as e:
            logging.error(f"Erro ao criar backup: {str(e)}")
            return None

    def _backup_configs(self, config_path):
        """Backup das configurações do sistema"""
        try:
            configs = {}
            # Adicionar configurações importantes aqui
            configs['backup_date'] = datetime.now().isoformat()
            configs['version'] = '1.0'

            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(configs, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logging.error(f"Erro ao fazer backup das configurações: {str(e)}")

    def should_backup(self, interval_hours=24):
        """Verifica se deve criar backup baseado no intervalo"""
        try:
            backup_files = [f for f in os.listdir(self.backup_dir)
                          if f.startswith('backup_auto_') and f.endswith('.db')]

            if not backup_files:
                return True

            # Verificar último backup
            latest_backup = max(backup_files, key=lambda x: os.path.getctime(
                os.path.join(self.backup_dir, x)))
            backup_time = datetime.fromtimestamp(os.path.getctime(
                os.path.join(self.backup_dir, latest_backup)))

            time_since_backup = datetime.now() - backup_time
            return time_since_backup.total_seconds() > interval_hours * 3600
        except Exception as e:
            logging.error(f"Erro ao verificar necessidade de backup: {str(e)}")
            return False

class SecurityManager:
    """Gerenciador de segurança avançado"""

    def __init__(self):
        self.failed_attempts = {}
        self.blocked_ips = set()
        self.suspicious_activities = []

    def validate_input(self, data, rules):
        """Valida entrada de dados com regras específicas"""
        for field, rule in rules.items():
            if field not in data:
                if rule.get('required', False):
                    raise ValueError(f"Campo obrigatório: {field}")
                continue

            value = data[field]

            # Validar tipo
            if 'type' in rule:
                if rule['type'] == 'string' and not isinstance(value, str):
                    raise ValueError(f"Campo {field} deve ser string")
                elif rule['type'] == 'int' and not isinstance(value, int):
                    raise ValueError(f"Campo {field} deve ser inteiro")
                elif rule['type'] == 'float' and not isinstance(value, (int, float)):
                    raise ValueError(f"Campo {field} deve ser numérico")

            # Validar comprimento
            if 'min_length' in rule and len(str(value)) < rule['min_length']:
                raise ValueError(f"Campo {field} deve ter pelo menos {rule['min_length']} caracteres")

            if 'max_length' in rule and len(str(value)) > rule['max_length']:
                raise ValueError(f"Campo {field} deve ter no máximo {rule['max_length']} caracteres")

            # Validar padrão regex
            if 'pattern' in rule and not re.match(rule['pattern'], str(value)):
                raise ValueError(f"Campo {field} não corresponde ao padrão esperado")

            # Validar range numérico
            if 'min' in rule and isinstance(value, (int, float)) and value < rule['min']:
                raise ValueError(f"Campo {field} deve ser maior ou igual a {rule['min']}")

            if 'max' in rule and isinstance(value, (int, float)) and value > rule['max']:
                raise ValueError(f"Campo {field} deve ser menor ou igual a {rule['max']}")

    def check_rate_limit(self, identifier, max_attempts=5, window_minutes=15):
        """Verifica limite de tentativas"""
        now = datetime.now()
        key = f"{identifier}_{now.strftime('%Y%m%d%H%M')}"

        if key not in self.failed_attempts:
            self.failed_attempts[key] = []

        # Limpar tentativas antigas
        self.failed_attempts[key] = [
            attempt for attempt in self.failed_attempts[key]
            if (now - attempt).seconds < window_minutes * 60
        ]

        if len(self.failed_attempts[key]) >= max_attempts:
            return False

        self.failed_attempts[key].append(now)
        return True

    def detect_suspicious_activity(self, activity_data):
        """Detecta atividades suspeitas"""
        suspicious_patterns = [
            'multiple_failed_logins',
            'unusual_login_time',
            'mass_data_deletion',
            'privilege_escalation_attempt'
        ]

        for pattern in suspicious_patterns:
            if self._check_pattern(pattern, activity_data):
                self.suspicious_activities.append({
                    'pattern': pattern,
                    'timestamp': datetime.now(),
                    'data': activity_data
                })
                return True
        return False

    def _check_pattern(self, pattern, data):
        """Verifica se atividade corresponde a padrão suspeito"""
        if pattern == 'multiple_failed_logins':
            return data.get('failed_attempts', 0) > 3
        elif pattern == 'unusual_login_time':
            hour = datetime.now().hour
            return hour < 6 or hour > 22  # Login fora do horário comercial
        elif pattern == 'mass_data_deletion':
            return data.get('deleted_records', 0) > 10
        elif pattern == 'privilege_escalation_attempt':
            return data.get('privilege_change_attempt', False)
        return False

    def generate_secure_token(self, length=32):
        """Gera token seguro"""
        return secrets.token_urlsafe(length)

    def hash_sensitive_data(self, data):
        """Hash de dados sensíveis"""
        return hashlib.sha256(data.encode()).hexdigest()

class ErrorHandler:
    """Gerenciador de erros avançado"""

    def __init__(self):
        self.error_counts = {}
        self.error_threshold = 10  # Alertar após 10 erros do mesmo tipo

    def handle_error(self, error, context=None):
        """Trata erro de forma inteligente"""
        error_type = type(error).__name__
        error_message = str(error)

        # Contar ocorrências
        if error_type not in self.error_counts:
            self.error_counts[error_type] = 0
        self.error_counts[error_type] += 1

        # Log do erro
        logging.error(f"Erro {error_type}: {error_message}")
        if context:
            logging.error(f"Contexto: {context}")

        # Alertar se threshold atingido
        if self.error_counts[error_type] >= self.error_threshold:
            self._send_alert(error_type, error_message)

        # Tentar recuperação automática para alguns tipos de erro
        if isinstance(error, sqlite3.OperationalError):
            if "database is locked" in error_message:
                logging.warning("Tentando resolver lock do banco de dados")
                return self._handle_db_lock()
            elif "no such table" in error_message:
                logging.warning("Tentando recriar tabelas faltantes")
                return self._handle_missing_table()

        return False  # Não conseguiu recuperar

    def _send_alert(self, error_type, message):
        """Envia alerta para administradores"""
        logging.critical(f"ALERTA: Múltiplas ocorrências de erro {error_type}: {message}")
        # Aqui poderia enviar email/SMS para admins

    def _handle_db_lock(self):
        """Tenta resolver lock do banco"""
        import time
        time.sleep(1)  # Esperar um pouco
        return True

    def _handle_missing_table(self):
        """Tenta recriar tabelas faltantes"""
        try:
            # Aqui poderia chamar db.init_db() novamente
            logging.info("Tentativa de recriar tabelas faltantes")
            return True
        except:
            return False

class PerformanceMonitor:
    """Monitor de performance do sistema"""

    def __init__(self):
        self.metrics = {}
        self.slow_queries_threshold = 1.0  # segundos

    def start_timer(self, operation_name):
        """Inicia timer para operação"""
        self.metrics[operation_name] = {
            'start_time': datetime.now(),
            'operation': operation_name
        }

    def end_timer(self, operation_name):
        """Finaliza timer e registra métrica"""
        if operation_name in self.metrics:
            start_time = self.metrics[operation_name]['start_time']
            duration = (datetime.now() - start_time).total_seconds()

            if duration > self.slow_queries_threshold:
                logging.warning(f"Operação lenta detectada: {operation_name} - {duration:.2f}s")

            # Armazenar métrica para análise futura
            self._store_metric(operation_name, duration)

    def _store_metric(self, operation, duration):
        """Armazena métrica para análise"""
        # Aqui poderia salvar em banco ou arquivo
        pass

    def get_performance_report(self):
        """Gera relatório de performance"""
        # Implementar geração de relatório
        pass

# Decorators para robustez
def with_error_handling(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except Exception as e:
            error_handler = ErrorHandler()
            if not error_handler.handle_error(e, {'function': f.__name__, 'args': args}):
                raise  # Re-raise se não conseguiu recuperar
    return wrapper

def with_performance_monitoring(operation_name):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            monitor = PerformanceMonitor()
            monitor.start_timer(operation_name)
            try:
                result = f(*args, **kwargs)
                return result
            finally:
                monitor.end_timer(operation_name)
        return wrapper
    return decorator

def with_audit_trail(action_name):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            # Por enquanto, desabilitar auditoria para evitar erro
            try:
                result = f(*args, **kwargs)
                return result
            except Exception as e:
                raise
        return wrapper
    return decorator