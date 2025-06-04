import os
import re
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, session, flash, g, jsonify
import json
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
import random
import smtplib # enviar email
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from contextlib import contextmanager
from datetime import datetime,timedelta
load_dotenv()

# inicio do app

app = Flask(__name__)

app.config['SECRET_KEY'] = os.getenv("SECRET_KEY")
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024 

EXTENSOES = {'png', 'jpg', 'jpeg', 'webp'}

# chechar extensão

def check_extension(nome_foto):
    return '.' in nome_foto and nome_foto.lower().rsplit('.',1)[1] in EXTENSOES

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
                rec_code INTEGER,
                created DATETIME,
                expired DATETIME
            );
        ''')
        db.execute('''
            CREATE TABLE IF NOT EXISTS psicologos(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL,
                crp TEXT UNIQUE NOT NULL,
                imagem TEXT,
                celular INTEGER,
                email TEXT UNIQUE NOT NULL,
                senha TEXT NOT NULL,
                horarios TEXT NOT NULL
            );
        ''')
        db.execute('''
            CREATE TABLE IF NOT EXISTS consultas(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                data TEXT NOT NULL,
                horario TEXT NOT NULL,
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
        db.execute('''
            CREATE TABLE IF NOT EXISTS ocupado(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nome TEXT NOT NULL,
                    data DATA NOT NULL,
                    horario TEXT NOT NULL,
                    FOREIGN KEY (nome) REFERENCES psicologos (nome)
                    );
                ''')
        db.commit()

# Recuperação de senha

#Gerar código

def codigo(email):
    codigo = random.randint(1000,9999)
    db = get_db()
    email_exists = db.execute('SELECT nome FROM usuarios WHERE email=?',(email,)).fetchone()
    print(email_exists)
    agora = datetime.now()
    expirou = agora + timedelta(minutes=5)
    db.execute('UPDATE usuarios SET rec_code=?,created=?,expired=? WHERE email=?',(codigo,agora,expirou,email))
    db.commit()

#Apagar código

@app.before_request
def apagar_codigo():
    db = get_db()
    agora = datetime.now()
    db.execute('UPDATE usuarios SET rec_code=NULL, created=NULL, expired=NULL WHERE expired < ?',(agora,))
    db.commit()

#Enviar email

def senha_cod(email,codigo):
    remetente = os.getenv("REMETENTE") #adicionar remetente de email
    remetente_senha = os.getenv("SENHA_REMETENTE") #adicionar senha do email do remetente
    if email and codigo:
        mensagem = MIMEMultipart()
        mensagem['From'] = remetente
        mensagem['To'] = email
        mensagem['Subject'] = 'Código de recuperação de senha - MindConnect'
        # corpo do email
        db = get_db()
        data = db.execute('SELECT * FROM usuarios WHERE email=?',(email,)).fetchone()
        corpo = f"Olá {data[1]}, seu código de recuperação é o seguinte: {data[7]}, use-o logo pois ele irá expirar em 5 minutos."
        mensagem.attach(MIMEText(corpo,'plain'))
        try:
            servidor_email = smtplib.SMTP('smtp.gmail.com',587)
            servidor_email.starttls()
            servidor_email.login(remetente,remetente_senha)
            servidor_email.sendmail(remetente,email,mensagem.as_string())
        except Exception as e:
            print(f"Erro: {e}")
        finally:
            servidor_email.quit()

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
        foto = request.files['foto']
        senha = request.form['senha']
        celular = request.form['celular']
        senha_segura = generate_password_hash(senha)
        nome_foto = None
        db = get_db()
        try:
            if foto and check_extension(foto.filename):
                nome_foto = secure_filename(foto.filename)
                foto.save(os.path.join(app.config['UPLOAD_FOLDER'],nome_foto))
                db.execute('INSERT INTO usuarios (nome,email,senha,imagem,celular) VALUES (?,?,?,?,?)',(nome,email,senha_segura,nome_foto,celular))
            else:
                db.execute('INSERT INTO usuarios (nome, email, senha, celular) VALUES (?, ?, ?, ?)', (nome, email, senha_segura,celular))
            db.commit()
            flash('Usuário cadastrado com sucesso!!!')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('E-mail já cadastrado!')
            return render_template('register.html')
    return render_template('register.html')


#Rota para login de usuario

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        login = request.form['login']
        senha = request.form['senha']
        db = get_db()
        usuario = db.execute('SELECT * FROM usuarios WHERE email=?', (login, )).fetchone()
        if usuario and check_password_hash(usuario['senha'], senha):
            session['usuario_id'] = usuario['id']
            session['user_admin'] = usuario['admin']
            session['usuario_tipo'] = 'user'
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
            resultado = ["🔴 Alerta emocional 🔴"]
            resultado_classe = "alerta"
            recomendacoes = ["Consulta com psicólogo online", "Áudio de primeiros socorros emocionais", "Registro de sentimentos", "Acesso a apoio confidencial e imediato"]
            # aqui vai retornar uma mensagem de alerta de risco emocional
            return render_template('questionary_result.html', resultado=resultado, recomendacoes=recomendacoes, resultado_classe=resultado_classe)
        elif total <= 4:
            resultado = ["🟡 Atenção moderada 🟡"]
            resultado_classe = "moderado"
            recomendacoes = ["Técnicas de relaxamento", "Meditação guiada", "Diário emocional", "Ative lembretes para pausas e autocuidado"]
            #aqui vai retornar uma mensagem de atenção moderada
            return render_template('questionary_result.html', resultado=resultado, recomendacoes=recomendacoes, resultado_classe=resultado_classe)
        else:
            resultado = ["🟢 Bem-estar alto 🟢"]
            resultado_classe = "alto"
            recomendacoes = ["Continue com suas práticas de autocuidado", "Explore novos conteúdos preventivos", "Mantenha hábito saudáveis", "Experimente metas semanais"]
    
            #aqui vai retornar uma mensagem de bem-estar alto
            return render_template('questionary_result.html', resultado=resultado, recomendacoes=recomendacoes, resultado_classe=resultado_classe)
    return render_template('questionary.html')

# rota para norms

@app.route('/norms')
def norms():
    return render_template('norms.html') 

# rota para feedback

@app.route('/feedback',methods=['GET','POST'])
def feedback():
    if not session:
        return redirect(url_for('login'))
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

#Rota dos termos

@app.route('/userterms')
def termos():
    return render_template('userterms.html')

#Rota recomendações

@app.route('/recomendations')
def recomendation():
    return render_template('recomendations.html')

#Rota esqueci senha

@app.route('/password',methods=['GET','POST'])
def password():
    if request.method == 'POST':
        email = request.form['email']
        session['email'] = email
        codigo(email)
        db = get_db()
        cod = db.execute('SELECT rec_code FROM usuarios WHERE email=?',(email,))
        if not cod:
            flash("Código não gerado ou email inexistente")
            return redirect(url_for('password'))
        senha_cod(email,cod)
        return redirect(url_for('password_recovery'))
    return render_template('password.html')

#Rota para nova senha

@app.route('/password_recovery',methods=['GET','POST'])
def password_recovery():
    if request.method == "POST":
        codigo = int(request.form.get('codigo'))
        senha = request.form.get('password')
        email = session.get('email')
        print(email)
        db = get_db()
        cod = db.execute('SELECT * FROM usuarios WHERE email=?',(email,)).fetchone()
        print(codigo,cod)
        if codigo == cod[7]:
            senha_segura = generate_password_hash(senha)
            db.execute('UPDATE usuarios SET senha=? WHERE email=?',(senha_segura,email))
            session.clear()
            flash("Senha alterada com sucesso")
            return redirect(url_for('login'))
        else:
            flash("Código inválido ou inexistente")
    return render_template('password_recovery.html')

# rota para agendar consulta

@app.route('/agendar',methods=['GET','POST'])
def agendar():
    if not session:
        return redirect(url_for('login'))
    db = get_db()
    psicologos = db.execute('SELECT * FROM psicologos').fetchall()
    if request.method == 'POST':
        nome = request.form.get('psicologo')
        data_str = request.form.get('select_date')
        horario_str = request.form.get('horario')
        if nome and data_str and horario_str:
            hora_inicio = horario_str.split(' - ')[0]

            data_horario_str = f"{data_str} {hora_inicio}"
            data_horario_dt = datetime.strptime(data_horario_str,'%Y-%m-%d %H:%M')

            if data_horario_dt > datetime.now():
                db.execute('INSERT INTO ocupado (nome,data,horario) VALUES (?,?,?)',(nome,data_str,horario_str))
                db.execute('INSERT INTO consultas (data,horario,paciente_id,psicologo_id) VALUES (?,?,?,?)',(data_str,horario_str,session['usuario_id'],nome))
                db.commit()
                return redirect(url_for('index'))
    return render_template('gestao.html',psicologos=psicologos)

@app.route('/buscar_por_data')
def buscar_por_data():
    data = request.args.get('data')
    psicologo = request.args.get('psicologo')
    if not data or not psicologo:
        return jsonify([])
    # horarios disponiveis do psicologo
    db = get_db()
    resultado = db.execute('SELECT horarios FROM psicologos WHERE nome=?',(psicologo,)).fetchone()
    if not resultado:
        return jsonify([])
    try:
        horarios = json.loads(resultado['horarios'])
    except json.JSONDecodeError:
        return jsonify([])
    # horarios que o psicologo tá ocupado
    ocupado = db.execute('SELECT horario FROM ocupado WHERE nome=? AND data=?',(psicologo,data)).fetchall()
    horarios_ocupado = [row['horario'] for row in ocupado]
    # horarios disponiveis
    horarios_disponiveis = [h for h in horarios if h not in horarios_ocupado]
    return jsonify(horarios_disponiveis)


# rota para registrar psicologo

@app.route('/register_psi',methods=['GET','POST'])
def register_psi():
    if request.method == 'POST':
        nome = request.form.get('nome')
        crp = request.form.get('crp')
        email = request.form.get('email')
        foto = request.files.get('foto')
        senha = request.form.get('senha')
        senha_segura = generate_password_hash(senha)
        inicio_str = request.form.get('inicio')
        final_str = request.form.get('final')
        intervalo_m = int(request.form.get('intervalo'))
        inicio = datetime.strptime(inicio_str,'%H:%M')
        final = datetime.strptime(final_str,'%H:%M')
        intervalo = timedelta(minutes=intervalo_m)
        horarios = []
        while inicio + intervalo <= final:
            proximo = inicio + intervalo
            horarios.append(f"{inicio.strftime('%H:%M')} - {proximo.strftime('%H:%M')}")
            inicio = proximo
        horarios_json = json.dumps(horarios)
        db = get_db()
        if foto and check_extension(foto.filename):
            nome_foto = secure_filename(foto.filename)
            foto.save(os.path.join(app.config['UPLOAD_FOLDER'],nome_foto))
            db.execute('INSERT INTO psicologos (nome,crp,email,imagem,senha,horarios) VALUES (?,?,?,?,?,?)',(nome,crp,email,nome_foto,senha_segura,horarios_json))
        elif not foto:
            db.execute('INSERT INTO psicologos (nome,crp,email,senha,horarios) VALUES (?,?,?,?,?)',(nome,crp,email,senha_segura,horarios_json))
        db.commit()
        return redirect(url_for('index'))
    return render_template('register_psi.html')

#Rota para login de psicologo

@app.route('/login_psi', methods=['GET','POST'])
def login_psi():
    if request.method == 'POST':
        login = request.form['login'].lower()
        senha = request.form['senha']
        db = get_db()
        psicologo = db.execute('SELECT * FROM psicologos WHERE email=?', (login, )).fetchone()
        if psicologo and check_password_hash(psicologo['senha'], senha):
            session['psicologo_id'] = psicologo['id']
            return redirect(url_for('index'))
        else:
            flash('Usuário ou senha inválidos.')
            return render_template('login_psi.html')
    return render_template('login_psi.html')


#rota para edit user

@app.route('/edit_user',methods=['GET','POST'])
def edit_user():
    db = get_db()
    usuario = db.execute('SELECT * FROM usuarios WHERE id=?',(session['usuario_id'],)).fetchone()
    if request.method == 'POST':
        if session['usuario_tipo'] == 'user':
            nome = request.form['nome']
            celular = request.form['celular']
            email = request.form['email']
            foto = request.files['foto']
            if nome:
                db.execute('UPDATE usuarios SET nome=? WHERE id=?',(nome,session['usuario_id']))
            if celular:
                db.execute('UPDATE usuarios SET celular=? WHERE id=?',(celular,session['usuario_id']))
            if email:
                db.execute('UPDATE usuarios SET email=? WHERE id=?',(email,session['usuario_id']))
            if foto and check_extension(foto.filename):
                if usuario['imagem']:
                    diretorio_imagem = os.path.join('static','uploads',usuario['imagem'])
                    foto.save(diretorio_imagem)
                elif not usuario['imagem']:
                    nome_foto = None
                    nome_foto = secure_filename(foto.filename)
                    foto.save(os.path.join('static','uploads/'+nome_foto))
                    db.execute('UPDATE usuarios SET imagem VALUES ? WHERE id=?',(nome_foto,session['usuario_id']))
            db.commit()
            return render_template('edit_user.html',usuario=usuario)
        else:
            nome = request.form['nome']
            celular = request.form['celular']
            email = request.form['email']
            foto = request.files['foto']
            inicio_str = request.form.get('inicio')
            final_str = request.form.get('final')
            intervalo_m = int(request.form.get('intervalo'))
            if nome:
                db.execute('UPDATE psicologos SET nome=? WHERE id=?',(nome,session['psicologo_id']))
            if celular:
                db.execute('UPDATE psicologos SET celular=? WHERE id=?',(celular,session['psicologo_id']))
            if email:
                db.execute('UPDATE psicologos SET email=? WHERE id=?',(email,session['psicologo_id']))
            if foto and check_extension(foto.filename):
                if db.execute('SELECT imagem FROM psicologos WHERE id=?',(session['psicologo_id'])).fetchone():
                    diretorio_imagem = os.path.join('static','uploads',usuario['imagem'])
                    foto.save(diretorio_imagem)
                elif not db.execute('SELECT imagem FROM psicologos WHERE id=?',(session['psicologo_id'])).fetchone():
                    nome_foto = None
                    nome_foto = secure_filename(foto.filename)
                    foto.save(os.path.join('static','uploads/'+nome_foto))
                    db.execute('UPDATE psicologos SET imagem VALUES ? WHERE id=?',(nome_foto,session['psicologo_id']))
            if inicio_str and final_str and intervalo_m:
                inicio = datetime.strptime(inicio_str,'%H:%M')
                final = datetime.strptime(final_str,'%H:%M')
                intervalo = timedelta(minutes=intervalo_m)
                horarios = []
                while inicio + intervalo <= final:
                    proximo = inicio + intervalo
                    horarios.append(f"{inicio.strftime('%H:%M')} - {proximo.strftime('%H:%M')}")
                    inicio = proximo
                horarios_json = json.dumps(horarios)
                db.execute('UPDATE psicologos SET horarios=? WHERE id=?',(horarios_json,session['psicologo_id']))
    return render_template('edit_user.html',usuario=usuario)


#rota para mostrar consultas usuario

@app.route('/consultas')
def consultas():
    if not session:
        return redirect(url_for('login'))
    if session['usuario_id']:
        db = get_db()
        consultas_marcadas = db.execute('SELECT * FROM consultas WHERE paciente_id=?',(session['usuario_id'],)).fetchall()
        psicologos = []
        for consulta in consultas_marcadas:
            psicologo = db.execute('SELECT * FROM psicologos WHERE nome=?',(consulta['psicologo_id'],)).fetchone()
            psicologos.append(psicologo)
        return render_template('check_up.html',consultas_marcadas=consultas_marcadas,psicologos=psicologos)
    return render_template('check_up.html')

'''
.env:
SECRET_KEY=bc120d0cf5ab14672c2ed52367b1f6c089dd7b5f5a84d4664f355d1dbe5e7b4f
ADM_NOME=adm
ADM_EMAIL=adm@gmail.com
ADM_SENHA=adm123
REMETENTE=adm@gmail.com
SENHA_REMETENTE=adm123

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