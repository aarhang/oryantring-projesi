import os
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_socketio import SocketIO, emit
from sqlalchemy import create_engine, text

app = Flask(__name__)
app.config['SECRET_KEY'] = 'bu-cok-gizli-bir-anahtar-olmalı'
socketio = SocketIO(app)

# --- YENİ: VERİTABANI BAĞLANTISI ---
# Render'daki veritabanı adresini bir "Ortam Değişkeni" olarak alacağız.
DATABASE_URL = os.environ.get('DATABASE_URL')
engine = create_engine(DATABASE_URL)

ADMIN_PASSWORD = '1234'
VALID_CHECKPOINTS = {
    'kod1', 'kod2', 'kod3', 'kod4', 'kod5', 'kod6', 'kod7', 'kod8', 'kod9', 'kod10', 'kod11', 'kod12'}
def init_db():
    # PostgreSQL'e uygun CREATE TABLE komutu
    create_table_query = text("""
    CREATE TABLE IF NOT EXISTS users (
        name VARCHAR(255) PRIMARY KEY,
        score INTEGER NOT NULL DEFAULT 0,
        scanned_codes TEXT NOT NULL DEFAULT ''
    )
    """)
    with engine.connect() as conn:
        conn.execute(create_table_query)
        conn.commit()

# --- GÜNCELLENMİŞ ROTALAR ---
@app.route('/start_race', methods=['POST'])
def start_race():
    user_name = request.form['username']
    with engine.connect() as conn:
        user = conn.execute(text("SELECT * FROM users WHERE name = :name"), {'name': user_name}).fetchone()
        if user is None:
            conn.execute(text("INSERT INTO users (name) VALUES (:name)"), {'name': user_name})
            conn.commit()
    
    session['role'] = 'racer'
    session['user_name'] = user_name
    update_leaderboard()
    return render_template('race.html', user_name=user_name)

@app.route('/checkpoint', methods=['GET','POST'])
def checkpoint():
    data = request.get_json()
    user_name = data['userName']
    scanned_code = data['decodedText']

    if scanned_code not in VALID_CHECKPOINTS:
        return jsonify({'success': False, 'message': 'Bu QR kod yarışmaya ait değil!'})
    
    with engine.connect() as conn:
        user = conn.execute(text("SELECT * FROM users WHERE name = :name"), {'name': user_name}).fetchone()
        scanned_list = user.scanned_codes.split(',')
        if scanned_code in scanned_list:
            return jsonify({'success': False, 'message': 'Bu noktayı daha önce geçtiniz!'})
        
        new_score = user.score + 1
        new_scanned_codes = user.scanned_codes + ',' + scanned_code
        
        conn.execute(text("UPDATE users SET score = :score, scanned_codes = :codes WHERE name = :name"),
                     {'score': new_score, 'codes': new_scanned_codes, 'name': user_name})
        conn.commit()

    update_leaderboard()
    return jsonify({'success': True, 'newScore': new_score, 'message': 'Tebrikler! Puan kazandınız.'})

def update_leaderboard():
    with engine.connect() as conn:
        users = conn.execute(text("SELECT name, score FROM users ORDER BY score DESC")).fetchall()
        leaderboard_data = [dict(row._mapping) for row in users]
        socketio.emit('leaderboard_update', leaderboard_data)

# Diğer rotalar ve SocketIO olayları aynı kalabilir.
@app.route('/')
def anasayfa(): return render_template('login.html')
@app.route('/admin', methods=['GET', 'POST'])
def admin_panel():
    if request.method == 'POST':
        if request.form.get('password') == ADMIN_PASSWORD: session['role'] = 'admin'
        return redirect(url_for('admin_panel'))
    return render_template('admin.html')

race_started_flag = False
@socketio.on('start_race_event')
def handle_start_race_event():
    global race_started_flag
    if not race_started_flag: race_started_flag = True; emit('race_started', broadcast=True)
@socketio.on('connect')
def handle_connect(): update_leaderboard()

if __name__ == '__main__':
    # init_db() fonksiyonunu sadece ilk kurulumda veya gerektiğinde yerel olarak çalıştırırız.
    # Sunucuda bu otomatik olarak yönetilecek.
    # init_db() 
    socketio.run(app, debug=True)