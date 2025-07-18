import sqlite3
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_socketio import SocketIO, emit

app = Flask(__name__)
app.config['SECRET_KEY'] = 'bu-cok-gizli-bir-anahtar-olmalı'
socketio = SocketIO(app)

ADMIN_PASSWORD = '1234'
VALID_CHECKPOINTS = {'checkpoint_1', 'checkpoint_2', 'checkpoint_3', 'checkpoint_4', 'finish'}

# ... (get_db_connection ve init_db fonksiyonları aynı kalıyor) ...
def get_db_connection():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    conn.execute('CREATE TABLE IF NOT EXISTS users (name TEXT PRIMARY KEY, score INTEGER NOT NULL DEFAULT 0, scanned_codes TEXT NOT NULL DEFAULT "")')
    conn.commit()
    conn.close()

# --- ROTALAR ---

@app.route('/')
def anasayfa():
    return render_template('login.html')

@app.route('/start_race', methods=['POST'])
def start_race():
    user_name = request.form['username']
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE name = ?', (user_name,)).fetchone()
    if user is None:
        conn.execute('INSERT INTO users (name) VALUES (?)', (user_name,))
        conn.commit()
        print(f"Yeni kullanıcı veritabanına eklendi: {user_name}")
    conn.close()
    
    session['role'] = 'racer'
    session['user_name'] = user_name

    # YENİ: Yeni kullanıcı giriş yaptığında da liderlik tablosunu güncelle.
    update_leaderboard()

    return render_template('race.html', user_name=user_name)

@app.route('/checkpoint', methods=['POST'])
def checkpoint():
    # ... (Bu fonksiyon aynı kalıyor) ...
    data = request.get_json()
    user_name = data['userName']
    scanned_code = data['decodedText']
    if scanned_code not in VALID_CHECKPOINTS:
        return jsonify({'success': False, 'message': 'Bu QR kod yarışmaya ait değil!'})
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE name = ?', (user_name,)).fetchone()
    scanned_list = user['scanned_codes'].split(',')
    if scanned_code in scanned_list:
        conn.close()
        return jsonify({'success': False, 'message': 'Bu noktayı daha önce geçtiniz!'})
    new_score = user['score'] + 1
    new_scanned_codes = user['scanned_codes'] + ',' + scanned_code
    conn.execute('UPDATE users SET score = ?, scanned_codes = ? WHERE name = ?', (new_score, new_scanned_codes, user_name))
    conn.commit()
    conn.close()
    update_leaderboard()
    return jsonify({'success': True, 'newScore': new_score, 'message': 'Tebrikler! Puan kazandınız.'})

@app.route('/admin', methods=['GET', 'POST'])
def admin_panel():
    # ... (Bu fonksiyon aynı kalıyor) ...
    if request.method == 'POST':
        if request.form.get('password') == ADMIN_PASSWORD:
            session['role'] = 'admin'
            return redirect(url_for('admin_panel'))
        else:
            return "<h1>Yanlış Şifre!</h1>"
    return render_template('admin.html')

# SİLİNDİ: Artık bu rota ve sayfaya ihtiyacımız yok.
# @app.route('/leaderboard')
# def leaderboard():
#     if session.get('role') != 'admin':
#         return "<h1>Bu sayfaya erişim yetkiniz yok!</h1>", 403
#     return render_template('leaderboard.html')

# --- SOCKET.IO ve YARDIMCI FONKSİYONLAR (Değişiklik yok) ---
race_started_flag = False
@socketio.on('start_race_event')
def handle_start_race_event():
    global race_started_flag
    if not race_started_flag:
        race_started_flag = True
        emit('race_started', broadcast=True)

@socketio.on('connect')
def handle_connect():
    update_leaderboard()

def update_leaderboard():
    conn = get_db_connection()
    users = conn.execute('SELECT name, score FROM users ORDER BY score DESC').fetchall()
    conn.close()
    leaderboard_data = [dict(row) for row in users]
    socketio.emit('leaderboard_update', leaderboard_data)

if __name__ == '__main__':
    init_db()
    socketio.run(app, debug=True)