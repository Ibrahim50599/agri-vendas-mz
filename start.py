from main import app, init_db
import os

# Garante que as tabelas do banco existem
init_db()

# Inicia o servidor com Gunicorn
os.system("gunicorn main:app --bind 0.0.0.0:10000")



