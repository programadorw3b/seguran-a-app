import os
import re
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, session, flash, g
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
load_dotenv()
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv("SECRET_KEY")
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024 
EXTENSOES = {'png', 'jpg', 'jpeg', 'webp'}
DATABASE = 'mindconnect.db'
def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def fechar_conexao(exception):
    db = g.pop('db', None)
    if db is not None:
        db.close()

def inicializar_banco():
    with app.app_context():
        db = get_db()
        db.execute('''
            CREATE TABLE IF NOT EXISTS usuarios(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL,
                imagem TEXT,
                celular INTEGER,
                email TEXT UNIQUE NOT NULL,
                senha TEXT NOT NULL,
                admin INTEGER DEFAULT 0
            );
        ''')
        db.execute('''
            CREATE TABLE IF NOT EXISTS psicologos(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL,
                cro INTEGER UNIQUE NOT NULL,
                imagem TEXT,
                celular INTEGER,
                email TEXT UNIQUE NOT NULL,
                senha TEXT NOT NULL
            );
        ''')
        db.execute('''
            CREATE TABLE IF NOT EXISTS consultas(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                titulo TEXT NOT NULL,
                data TEXT NOT NULL,
                
                paciente_id INTEGER NOT NULL,
                psicologo_id INTEGER NOT NULL,
                FOREIGN KEY (paciente_id) REFERENCES usuarios (id),
                FOREIGN KEY (psicologo_id) REFERENCES psicologos (id)
            );
        ''')
        db.execute('''
            CREATE TABLE IF NOT EXISTS feedbacks(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL,
                tipo TEXT NOT NULL,
                mensagem TEXT NOT NULL
            );
        ''')
        db.commit()

@app.route('/')
def index():
    return render_template('index.html')


'''
Funções puro html:
@app.route('/norms')
def norms():
    return render_template('norms.html')
@app.route('/userterms')
def termos():
    return render_template('userterms.html')
@app.route('/relax')
def relax():
    return render_template('relax.html')
@app.route('/recomendations')
def relax():
    return render_template('recomendations.html')
'''



if __name__ == '__main__':
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    inicializar_banco()
    app.run(debug=True)