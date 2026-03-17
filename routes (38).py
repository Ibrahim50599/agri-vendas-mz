import sqlite3

conn = sqlite3.connect('agri_vendas.db')
c = conn.cursor()
c.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [row[0] for row in c.fetchall()]
print("Tabelas no banco de dados:")
for table in tables:
    print(f"- {table}")
conn.close()