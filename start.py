from main import app
from models import Database

# Garante que as tabelas do banco existem
db = Database('agri_vendas.db')
db.init_db()

# Inicia o servidor com Gunicorn
import os
os.system("gunicorn main:app --bind 0.0.0.0:10000")



