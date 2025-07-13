from main import init_db, app

# Inicializa o banco de dados com as tabelas necessárias
init_db()

# Inicia o servidor Flask no ambiente do Render
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)

