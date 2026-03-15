from flask import Flask
from routes import register_routes
from config import Config
from models import Database
import os

app = Flask(__name__)
app.config.from_object(Config)

# Criar pasta de uploads se não existir
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Inicializar banco de dados
db = Database(app.config['DATABASE'])
db.init_db()

# Registrar todas as rotas
register_routes(app, db)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))