from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import sqlite3
import os
import uuid
import random
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = 'titan_key_system_2024'
CORS(app)

# ============ CONFIG ============
PLATFORM_PASSWORD = 'NVTITAN'
ADMIN_PASSWORD = '2009'
DEFAULT_TOKENS = 5
ADMIN_ID = 'BZ-ADMIN'
TELEGRAM_USERNAME = '@vikranthxx0'

# ============ PACKAGES ============
PACKAGES = {
    '20': {'tokens': 20, 'price': '500₹'},
    '30': {'tokens': 30, 'price': '1000₹'},
    '60': {'tokens': 60, 'price': '1500₹'},
    'unlimited': {'tokens': 9999, 'price': '5000₹', 'duration_days': 30}
}

DB_PATH = 'titan_database.db'

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id TEXT PRIMARY KEY,
        access_key TEXT UNIQUE,
        tokens INTEGER DEFAULT 5,
        analyses INTEGER DEFAULT 0,
        online INTEGER DEFAULT 0,
        kicked INTEGER DEFAULT 0,
        is_admin INTEGER DEFAULT 0,
        rejoin_code TEXT,
        joined_at TEXT,
        unlimited_until TEXT,
        total_purchased INTEGER DEFAULT 0,
        ip_address TEXT
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS keys (
        key TEXT PRIMARY KEY,
        user_id TEXT,
        created_at TEXT,
        used INTEGER DEFAULT 0,
        ip_address TEXT
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS signals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT,
        direction TEXT,
        price REAL,
        trade_time TEXT,
        trade_end_time TEXT,
        result_type TEXT,
        screenshot_name TEXT,
        created_at TEXT
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS purchases (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT,
        package TEXT,
        amount TEXT,
        tokens INTEGER,
        status TEXT DEFAULT 'pending',
        created_at TEXT
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS revenue (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT,
        package TEXT,
        amount TEXT,
        tokens INTEGER,
        created_at TEXT
    )''')
    
    # Create admin
    c.execute("SELECT id FROM users WHERE id = ?", (ADMIN_ID,))
    if not c.fetchone():
        admin_key = 'TITAN-ADMIN-' + uuid.uuid4().hex[:4].upper()
        c.execute('''INSERT INTO users (id, access_key, tokens, analyses, online, kicked, is_admin, joined_at)
                     VALUES (?, ?, 9999, 0, 0, 0, 1, ?)''',
                  (ADMIN_ID, admin_key, get_ist_now().isoformat()))
        c.execute('''INSERT INTO keys (key, user_id, created_at, used)
                     VALUES (?, ?, ?, 0)''',
                  (admin_key, ADMIN_ID, get_ist_now().isoformat()))
    
    conn.commit()
    conn.close()

init_db()

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def get_user(user_id):
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    return user

def get_user_by_key(key):
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE access_key = ?", (key,)).fetchone()
    conn.close()
    return user

def update_user(user_id, **kwargs):
    conn = get_db()
    for key, value in kwargs.items():
        conn.execute(f"UPDATE users SET {key} = ? WHERE id = ?", (value, user_id))
    conn.commit()
    conn.close()

def get_ist_now():
    return datetime.utcnow() + timedelta(hours=5, minutes=30)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/login', methods=['POST'])
def api_login():
    data = request.json
    access_key = data.get('key', '').strip().upper()
    ip = request.remote_addr
    
    if not access_key:
        return jsonify({'success': False, 'message': 'Enter access key'})
    
    # Check if key exists
    conn = get_db()
    key_data = conn.execute("SELECT * FROM keys WHERE key = ?", (access_key,)).fetchone()
    
    if not key_data:
        conn.close()
        return jsonify({'success': False, 'message': 'Invalid key'})
    
    user = get_user(key_data['user_id'])
    
    if not user:
        conn.close()
        return jsonify({'success': False, 'message': 'User not found'})
    
    if user['kicked']:
        conn.close()
        return jsonify({'success': False, 'kicked': True, 'message': 'Account restricted'})
    
    # Key already used by different IP
    if key_data['used'] == 1 and key_data['ip_address'] and key_data['ip_address'] != ip:
        conn.close()
        return jsonify({'success': False, 'message': 'Key already in use on another device'})
    
    # Mark key as used
    conn.execute("UPDATE keys SET used = 1, ip_address = ? WHERE key = ?", (ip, access_key))
    conn.commit()
    conn.close()
    
    update_user(user['id'], online=1, ip_address=ip)
    
    return jsonify({
        'success': True,
        'user_id': user['id'],
        'tokens': user['tokens'],
        'analyses': user['analyses'],
        'is_admin': user['is_admin']
    })

@app.route('/api/admin/generate-key', methods=['POST'])
def admin_generate_key():
    data = request.json
    admin_password = data.get('password', '')
    
    if admin_password != ADMIN_PASSWORD:
        return jsonify({'success': False, 'message': 'Invalid admin password'})
    
    # Create new user
    user_id = 'TITAN-' + uuid.uuid4().hex[:6].upper()
    access_key = 'TITAN-' + uuid.uuid4().hex[:8].upper()
    
    conn = get_db()
    conn.execute('''INSERT INTO users (id, access_key, tokens, analyses, online, kicked, is_admin, joined_at)
                    VALUES (?, ?, ?, 0, 0, 0, 0, ?)''',
                 (user_id, access_key, DEFAULT_TOKENS, get_ist_now().isoformat()))
    conn.execute('''INSERT INTO keys (key, user_id, created_at, used, ip_address)
                    VALUES (?, ?, ?, 0, NULL)''',
                 (access_key, user_id, get_ist_now().isoformat()))
    conn.commit()
    conn.close()
    
    return jsonify({
        'success': True,
        'key': access_key,
        'user_id': user_id,
        'tokens': DEFAULT_TOKENS
    })

@app.route('/api/admin/keys', methods=['GET'])
def admin_keys():
    conn = get_db()
    keys = conn.execute('''SELECT k.*, u.tokens, u.analyses, u.online, u.kicked 
                           FROM keys k JOIN users u ON k.user_id = u.id 
                           ORDER BY k.created_at DESC''').fetchall()
    conn.close()
    return jsonify([dict(k) for k in keys])

@app.route('/api/rejoin', methods=['POST'])
def api_rejoin():
    data = request.json
    user_id = data.get('user_id', '')
    code = data.get('code', '')
    user = get_user(user_id)
    if not user: return jsonify({'success': False})
    if code == 'ADMIN-OVERRIDE' or code == user['rejoin_code']:
        update_user(user_id, kicked=0, tokens=max(user['tokens'], 5), online=1)
        return jsonify({'success': True, 'tokens': max(user['tokens'], 5)})
    return jsonify({'success': False})

@app.route('/api/analyze', methods=['POST'])
def api_analyze():
    data = request.json
    user_id = data.get('user_id', '')
    user = get_user(user_id)
    if not user: return jsonify({'success': False, 'message': 'User not found'})
    
    is_unlimited = False
    if user['unlimited_until']:
        unlimited_date = datetime.fromisoformat(user['unlimited_until'])
        if get_ist_now() < unlimited_date: is_unlimited = True
        else: update_user(user_id, unlimited_until=None)
    
    if not is_unlimited:
        if user['tokens'] <= 0: return jsonify({'success': False, 'message': 'No tokens!'})
        update_user(user_id, tokens=user['tokens'] - 1)
    
    update_user(user_id, analyses=user['analyses'] + 1)
    
    now = get_ist_now()
    next_min = now + timedelta(minutes=1)
    next_min = next_min.replace(second=0, microsecond=0)
    trade_time = next_min.strftime('%H:%M')
    
    r = random.random()
    if r < 0.25:
        result_type, direction = 'buy', 'BUY'
    elif r < 0.50:
        result_type, direction = 'sell', 'SELL'
    else:
        result_type, direction = 'unstable', 'UNSTABLE'
    
    conn = get_db()
    conn.execute('''INSERT INTO signals (user_id, direction, price, trade_time, trade_end_time, result_type, screenshot_name, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                 (user_id, direction, 0, trade_time, '', result_type, '', now.isoformat()))
    conn.commit()
    conn.close()
    
    updated_user = get_user(user_id)
    return jsonify({
        'success': True, 'signal_type': result_type, 'direction': direction,
        'trade_time': trade_time, 'tokens': updated_user['tokens']
    })

@app.route('/api/purchase', methods=['POST'])
def api_purchase():
    data = request.json
    user_id = data.get('user_id', '')
    package_key = data.get('package', '')
    if package_key not in PACKAGES: return jsonify({'success': False})
    package = PACKAGES[package_key]
    conn = get_db()
    conn.execute('''INSERT INTO purchases (user_id, package, amount, tokens, status, created_at)
                    VALUES (?, ?, ?, ?, 'pending', ?)''',
                 (user_id, package_key, package['price'], package['tokens'], get_ist_now().isoformat()))
    conn.commit()
    conn.close()
    telegram_msg = f"BUY%20REQUEST%0AUser:%20{user_id}%0APackage:%20{package_key}%0APrice:%20{package['price']}"
    return jsonify({'success': True, 'telegram_link': f"https://t.me/vikranthxx0?text={telegram_msg}"})

@app.route('/api/admin/verify', methods=['POST'])
def api_admin_verify():
    return jsonify({'success': request.json.get('password') == ADMIN_PASSWORD})

@app.route('/api/admin/users', methods=['GET'])
def api_admin_users():
    return jsonify([dict(u) for u in get_db().execute("SELECT * FROM users WHERE kicked = 0").fetchall()])

@app.route('/api/admin/revenue', methods=['GET'])
def api_admin_revenue():
    total = get_db().execute("SELECT COUNT(*) as total, SUM(tokens) as tokens FROM revenue").fetchone()
    return jsonify({'total_purchases': total['total'] or 0, 'total_tokens_sold': total['tokens'] or 0})

@app.route('/api/admin/approve-purchase', methods=['POST'])
def api_approve_purchase():
    data = request.json
    conn = get_db()
    purchase = conn.execute("SELECT * FROM purchases WHERE id = ?", (data.get('purchase_id', ''),)).fetchone()
    if not purchase: conn.close(); return jsonify({'success': False})
    user = get_user(purchase['user_id'])
    if purchase['package'] == 'unlimited':
        update_user(purchase['user_id'], unlimited_until=(get_ist_now() + timedelta(days=30)).isoformat())
    else:
        update_user(purchase['user_id'], tokens=user['tokens'] + purchase['tokens'])
    update_user(purchase['user_id'], total_purchased=user['total_purchased'] + purchase['tokens'])
    conn.execute('''INSERT INTO revenue (user_id, package, amount, tokens, created_at)
                    VALUES (?, ?, ?, ?, ?)''',
                 (purchase['user_id'], purchase['package'], purchase['amount'], purchase['tokens'], get_ist_now().isoformat()))
    conn.execute("DELETE FROM purchases WHERE id = ?", (data.get('purchase_id', ''),))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/api/admin/pending-purchases', methods=['GET'])
def api_pending_purchases():
    return jsonify([dict(p) for p in get_db().execute("SELECT * FROM purchases WHERE status = 'pending' ORDER BY id DESC").fetchall()])

@app.route('/api/admin/add-tokens', methods=['POST'])
def api_admin_add_tokens():
    data = request.json
    user = get_user(data.get('user_id', ''))
    if not user: return jsonify({'success': False})
    update_user(data['user_id'], tokens=user['tokens'] + int(data.get('amount', 0)))
    return jsonify({'success': True})

@app.route('/api/admin/kick', methods=['POST'])
def api_admin_kick():
    data = request.json
    if data.get('user_id') == ADMIN_ID: return jsonify({'success': False})
    rejoin_code = 'TITAN-' + uuid.uuid4().hex[:8].upper()
    update_user(data['user_id'], kicked=1, online=0, rejoin_code=rejoin_code)
    return jsonify({'success': True, 'rejoin_code': rejoin_code})

@app.route('/api/admin/delete-key', methods=['POST'])
def api_admin_delete_key():
    data = request.json
    key = data.get('key', '')
    conn = get_db()
    key_data = conn.execute("SELECT * FROM keys WHERE key = ?", (key,)).fetchone()
    if key_data:
        conn.execute("DELETE FROM keys WHERE key = ?", (key,))
        conn.execute("DELETE FROM users WHERE id = ?", (key_data['user_id'],))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/api/user/info', methods=['POST'])
def api_user_info():
    user = get_user(request.json.get('user_id', ''))
    return jsonify({'success': True, **dict(user)}) if user else jsonify({'success': False})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
