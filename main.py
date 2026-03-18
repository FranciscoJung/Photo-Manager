import sys
import os
import database as db
import utils
from ui import PhotoManagerApp

# Define o diretório base como a pasta onde o .exe (ou main.py) está
if getattr(sys, 'frozen', False):
    # Quando rodando como .exe gerado pelo PyInstaller
    BASE_DIR = os.path.dirname(sys.executable)
else:
    # Quando rodando diretamente com python main.py
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Passa o diretório base para os módulos
utils.BASE_DIR = BASE_DIR
db.BASE_DIR = BASE_DIR

if __name__ == "__main__":
    utils.ensure_dirs()
    db.initialize_db()
    app = PhotoManagerApp()
    app.mainloop()