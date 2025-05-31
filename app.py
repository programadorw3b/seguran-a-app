import os
import re
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, session, flash, g
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
load_dotenv()

# inicio do app

app = Flask(__name__)

app.config['SECRET_KEY'] = os.getenv("SECRET_KEY")
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024 

EXTENSOES = {'png', 'jpg', 'jpeg', 'webp'}

# inicio do banco de dados

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
                admin INTEGER DEFAULT 0,
                rec_code DATETIME
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
                tipo TEXT NOT NULL,
                data TEXT NOT NULL,
                prontuario TEXT,
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


# Rotas

#Rota index
@app.route('/')
def index():
    return render_template('index.html')

#Rota para cadastro
@app.route('/cadastro', methods=['GET','POST'])
def cadastro():
    if request.method == 'POST':
        nome = request.form['nome']
        email = request.form['email'].lower()
        senha = request.form['senha']
        senha_segura = generate_password_hash(senha)
        db = get_db()
        try:
            db.execute('INSERT INTO usuarios (nome, email, senha) VALUES (?, ?, ?)', (nome, email, senha_segura))
            db.commit()
            flash('Usuário cadastrado com sucesso!!!')
            return redirect(url_for('index'))
        except sqlite3.IntegrityError:
            flash('E-mail já cadastrado!')
            return render_template('register.html')
    return render_template('register.html')

#Rota para login
@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        login = request.form['login'].lower()
        senha = request.form['senha']
        db = get_db()
        usuario = db.execute('SELECT * FROM usuarios WHERE email=?', (login, )).fetchone()
        if usuario and check_password_hash(usuario['senha'], senha):
            session['usuario_id'] = usuario['id']
            session['user_admin'] = usuario['admin']
            return redirect(url_for('index'))
        else:
            flash('Usuário ou senha inválidos.')
            return render_template('login.html')
    return render_template('login.html')


#Rota questionary
@app.route('/questionario',methods=['GET','POST'])
def questionary():
    if request.method == 'POST':
        opcao_1 = int(request.form.get('hoje'))
        opcao_2 = int(request.form.get('sentido'))
        opcao_3 = int(request.form.get('causa'))
        opcao_4 = int(request.form.get('conversar'))
        opcao_5 = int(request.form.get('relaxar'))
        total = opcao_1+opcao_2+opcao_3+opcao_4+opcao_5+6
        if total <= 2:
            resultado = ["🔴 Alerta emocional", "Consulta com psicólogo online", "Áudio de primeiros socorros emocionais", "Registro de sentimentos", "Acesso a apoio confidencial e imediato"]
            # aqui vai retornar uma mensagem de alerta de risco emocional
            return render_template('questionary_result.html', resultado=resultado)
        elif total <= 4:
            resultado = ["🟡 Atenção moderada", "Técnicas de relaxamento", "Meditação guiada", "Diário emocional", "Ative lembretes para pausas e autocuidado"]
            #aqui vai retornar uma mensagem de atenção moderada
            return render_template('questionary_result.html', resultado=resultado)
        else:
            resultado = ["🟢 Bem-estar alto" "Continue com suas práticas de autocuidado", "Explore novos conteúdos preventivos", "Mantenha hábito saudáveis", "Experimente metas semanais"]
            #aqui vai retornar uma mensagem de bem-estar alto
            return render_template('questionary_result.html', resultado=resultado)
    return render_template('questionary.html')

# rota para norms

@app.route('/norms')
def norms():
    return render_template('norms.html') 

# rota para feedback

@app.route('/feedback',methods=['GET','POST'])
def feedback():
    if request.method == 'POST':
        tipo = request.form.get('tipo')
        nome = request.form.get('nome')
        mensagem = request.form.get('mensagem')
        db = get_db()
        if not nome:
            nome = 'anônimo'
        db.execute('INSERT INTO feedbacks (nome,tipo,mensagem) VALUES (?,?,?)',(nome,tipo,mensagem))
        db.commit()
        return redirect(url_for('index'))
    return render_template('feedback.html')

#Rota de relaxamento
@app.route('/relax')
def relax():
    return render_template('relax.html')

@app.route('/userterms')
def termos():
    return render_template('userterms.html')

'''
Funções puro html:


@app.route('/recomendations')
def recomendation():
    return render_template('recomendations.html')
'''

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))
# execução do app

if __name__ == '__main__':
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    inicializar_banco()
    with app.app_context():
        db = get_db()
        admin =  db.execute('SELECT * FROM usuarios where admin=1').fetchall()
        if not admin:
                adm_nome = os.getenv("ADM_NOME")
                adm_email = os.getenv("ADM_EMAIL")
                adm_senha = os.getenv("ADM_SENHA")
                senha_adm = generate_password_hash(adm_senha)
                db.execute('INSERT INTO usuarios (nome, email, senha, admin) VALUES (?, ?, ?, 1)', (adm_nome, adm_email, senha_adm))
                db.commit()
    app.run(debug=True)