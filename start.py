from main import init_db, app
import os

if __name__ == '__main__':
    init_db()
    os.system("gunicorn main:app")


