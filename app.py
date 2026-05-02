from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import os
import uuid
import random
import pg8000.native
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = 'titan_key_system_2024'
CORS(app)

# ============ CONFIG ============
ADMIN_PASSWORD = '2009'
ADMIN_KEY = '2009'
DEFAULT_TOKENS = 5
ADMIN_ID = 'BZ-ADMIN'
TELEGRAM_USERNAME = '@vikranthxx0'

# ============ SUPABASE DATABASE ============
DB_CONFIG = {
    "database": "postgres",
    "user": "postgres",
    "password": "Vikranth2009",
    "host": "db.trgljrubmvwzyywnwozo.supabase.co",
    "port": 5432
}

PACKAGES = {
    '20': {'tokens': 20, 'price': '500₹'},
    '30': {'tokens': 30, 'price': '1000₹'},
    '60': {'tokens': 60, 'price': '1500₹'},
    'unlimited': {'tokens': 9999, 'price': '5000₹', 'duration_days': 30}
}

def get_ist_now():
    return (datetime.utcnow() + timedelta(hours=5, minutes=30)).isoformat()

def get_db():
    return pg8000.native.Connection(**DB_CONFIG)

def dict_row(columns, row):
    if row is None:
        return None
    return dict(zip(columns, row))

def init_db():
    conn = get_db()
    
    conn.run('''CREATE TABLE IF NOT EXISTS users (
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
    
    conn.run('''CREATE TABLE IF NOT EXISTS keys (
        key TEXT PRIMARY KEY,
        user_id TEXT,
        created_at TEXT,
        used INTEGER DEFAULT 0,
        ip_address TEXT
    )''')
    
    conn.run('''CREATE TABLE IF NOT EXISTS signals (
        id SERIAL PRIMARY KEY,
        user_id TEXT,
        direction TEXT,
        price REAL,
        trade_time TEXT,
        trade_end_time TEXT,
        result_type TEXT,
        screenshot_name TEXT,
        created_at TEXT
    )''')
    
    conn.run('''CREATE TABLE IF NOT EXISTS purchases (
        id SERIAL PRIMARY KEY,
        user_id TEXT,
        package TEXT,
        amount TEXT,
        tokens INTEGER,
        status TEXT DEFAULT 'pending',
        created_at TEXT
    )''')
    
    conn.run('''CREATE TABLE IF NOT EXISTS revenue (
        id SERIAL PRIMARY KEY,
        user_id TEXT,
        package TEXT,
        amount TEXT,
        tokens INTEGER,
        created_at TEXT
    )''')
    
    # Create admin
    rows = conn.run("SELECT id FROM users WHERE id = :id", id=ADMIN_ID)
    if not rows:
        conn.run("INSERT INTO users (id, access_key, tokens, analyses, online, kicked, is_admin, joined_at) VALUES (:id, :key, 9999, 0, 0, 0, 1, :now)",
                  id=ADMIN_ID, key=ADMIN_KEY, now=get_ist_now())
        conn.run("INSERT INTO keys (key, user_id, created_at, used) VALUES (:key, :uid, :now, 0)",
                  key=ADMIN_KEY, uid=ADMIN_ID, now=get_ist_now())
    
    conn.close()

init_db()

def get_user(user_id):
    conn = get_db()
    rows = conn.run("SELECT * FROM users WHERE id = :id", id=user_id)
    conn.close()
    if rows:
        cols = ['id', 'access_key', 'tokens', 'analyses', 'online', 'kicked', 'is_admin', 'rejoin_code', 'joined_at', 'unlimited_until', 'total_purchased', 'ip_address']
        return dict_row(cols, rows[0])
    return None

def update_user(user_id, **kwargs):
    conn = get_db()
    for k, v in kwargs.items():
        conn.run(f"UPDATE users SET {k} = :val WHERE id = :uid", val=v, uid=user_id)
    conn.close()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/login', methods=['POST'])
def api_login():
    data = request.json
    access_key = data.get('key', '').strip().upper()
    ip = request.remote_addr or '0.0.0.0'
    
    if not access_key:
        return jsonify({'success': False, 'message': 'Enter access key'})
    
    conn = get_db()
    rows = conn.run("SELECT * FROM keys WHERE key = :key", key=access_key)
    
    if not rows:
        conn.close()
        return jsonify({'success': False, 'message': 'Invalid key'})
    
    key_data = rows[0]
    user = get_user(key_data[1])  # user_id is second column
    
    if not user:
        conn.close()
        return jsonify({'success': False, 'message': 'User not found'})
    
    if user['kicked']:
        conn.close()
        return jsonify({'success': False, 'kicked': True, 'message': 'Account restricted'})
    
    conn.run("UPDATE keys SET used = 1, ip_address = :ip WHERE key = :key", ip=ip, key=access_key)
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
    if data.get('password') != ADMIN_PASSWORD:
        return jsonify({'success': False})
    
    user_id = 'TITAN-' + uuid.uuid4().hex[:6].upper()
    access_key = 'TITAN-' + uuid.uuid4().hex[:8].upper()
    
    conn = get_db()
    conn.run("INSERT INTO users (id, access_key, tokens, analyses, online, kicked, is_admin, joined_at) VALUES (:id, :key, :tokens, 0, 0, 0, 0, :now)",
              id=user_id, key=access_key, tokens=DEFAULT_TOKENS, now=get_ist_now())
    conn.run("INSERT INTO keys (key, user_id, created_at, used) VALUES (:key, :uid, :now, 0)",
              key=access_key, uid=user_id, now=get_ist_now())
    conn.close()
    
    return jsonify({'success': True, 'key': access_key, 'user_id': user_id, 'tokens': DEFAULT_TOKENS})

@app.route('/api/admin/keys', methods=['GET'])
def admin_keys():
    conn = get_db()
    rows = conn.run("SELECT k.key, k.user_id, k.created_at, k.used, k.ip_address, u.tokens, u.analyses, u.online, u.kicked FROM keys k JOIN users u ON k.user_id = u.id ORDER BY k.created_at DESC")
    conn.close()
    keys = []
    for r in rows:
        keys.append({'key': r[0], 'user_id': r[1], 'created_at': r[2], 'used': r[3], 'ip_address': r[4], 'tokens': r[5], 'analyses': r[6], 'online': r[7], 'kicked': r[8]})
    return jsonify(keys)

@app.route('/api/analyze', methods=['POST'])
def api_analyze():
    data = request.json
    user_id = data.get('user_id', '')
    user = get_user(user_id)
    if not user:
        return jsonify({'success': False, 'message': 'User not found'})
    
    if user['tokens'] <= 0:
        return jsonify({'success': False, 'message': 'No tokens!'})
    
    update_user(user_id, tokens=user['tokens'] - 1, analyses=user['analyses'] + 1)
    
    now_ist = datetime.utcnow() + timedelta(hours=5, minutes=30)
    next_min = now_ist + timedelta(minutes=1)
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
    conn.run("INSERT INTO signals (user_id, direction, price, trade_time, trade_end_time, result_type, screenshot_name, created_at) VALUES (:uid, :dir, 0, :tt, '', :rt, '', :now)",
              uid=user_id, dir=direction, tt=trade_time, rt=result_type, now=get_ist_now())
    conn.close()
    
    updated = get_user(user_id)
    return jsonify({'success': True, 'signal_type': result_type, 'direction': direction, 'trade_time': trade_time, 'tokens': updated['tokens']})

@app.route('/api/purchase', methods=['POST'])
def api_purchase():
    data = request.json
    user_id = data.get('user_id', '')
    pkg = data.get('package', '')
    if pkg not in PACKAGES:
        return jsonify({'success': False})
    package = PACKAGES[pkg]
    conn = get_db()
    conn.run("INSERT INTO purchases (user_id, package, amount, tokens, status, created_at) VALUES (:uid, :pkg, :amt, :tok, 'pending', :now)",
              uid=user_id, pkg=pkg, amt=package['price'], tok=package['tokens'], now=get_ist_now())
    conn.close()
    telegram_msg = f"BUY%20REQUEST%0AUser:%20{user_id}%0APackage:%20{pkg}%0APrice:%20{package['price']}"
    return jsonify({'success': True, 'telegram_link': f"https://t.me/vikranthxx0?text={telegram_msg}"})

@app.route('/api/admin/verify', methods=['POST'])
def api_admin_verify():
    return jsonify({'success': request.json.get('password') == ADMIN_PASSWORD})

@app.route('/api/admin/users', methods=['GET'])
def api_admin_users():
    conn = get_db()
    rows = conn.run("SELECT * FROM users WHERE kicked = 0")
    conn.close()
    cols = ['id', 'access_key', 'tokens', 'analyses', 'online', 'kicked', 'is_admin', 'rejoin_code', 'joined_at', 'unlimited_until', 'total_purchased', 'ip_address']
    return jsonify([dict_row(cols, r) for r in rows])

@app.route('/api/admin/revenue', methods=['GET'])
def api_admin_revenue():
    conn = get_db()
    rows = conn.run("SELECT COUNT(*) as total, COALESCE(SUM(tokens),0) as tokens FROM revenue")
    conn.close()
    return jsonify({'total_purchases': rows[0][0] or 0, 'total_tokens_sold': rows[0][1] or 0})

@app.route('/api/admin/approve-purchase', methods=['POST'])
def api_approve_purchase():
    data = request.json
    pid = data.get('purchase_id')
    conn = get_db()
    rows = conn.run("SELECT * FROM purchases WHERE id = :id", id=pid)
    if not rows:
        conn.close()
        return jsonify({'success': False})
    purchase = rows[0]
    user = get_user(purchase[1])  # user_id
    if purchase[2] == 'unlimited':  # package
        unlimited_until = (datetime.utcnow() + timedelta(days=30, hours=5, minutes=30)).isoformat()
        conn.run("UPDATE users SET unlimited_until = :ut WHERE id = :uid", ut=unlimited_until, uid=purchase[1])
    else:
        conn.run("UPDATE users SET tokens = tokens + :tok WHERE id = :uid", tok=purchase[4], uid=purchase[1])
    conn.run("INSERT INTO revenue (user_id, package, amount, tokens, created_at) VALUES (:uid, :pkg, :amt, :tok, :now)",
              uid=purchase[1], pkg=purchase[2], amt=purchase[3], tok=purchase[4], now=get_ist_now())
    conn.run("DELETE FROM purchases WHERE id = :id", id=pid)
    conn.close()
    return jsonify({'success': True})

@app.route('/api/admin/pending-purchases', methods=['GET'])
def api_pending_purchases():
    conn = get_db()
    rows = conn.run("SELECT * FROM purchases WHERE status = 'pending' ORDER BY id DESC")
    conn.close()
    cols = ['id', 'user_id', 'package', 'amount', 'tokens', 'status', 'created_at']
    return jsonify([dict_row(cols, r) for r in rows])

@app.route('/api/admin/add-tokens', methods=['POST'])
def api_admin_add_tokens():
    data = request.json
    user = get_user(data.get('user_id'))
    if not user:
        return jsonify({'success': False})
    update_user(data['user_id'], tokens=user['tokens'] + int(data.get('amount', 0)))
    return jsonify({'success': True})

@app.route('/api/admin/kick', methods=['POST'])
def api_admin_kick():
    data = request.json
    if data.get('user_id') == ADMIN_ID:
        return jsonify({'success': False})
    code = 'TITAN-' + uuid.uuid4().hex[:8].upper()
    update_user(data['user_id'], kicked=1, online=0, rejoin_code=code)
    return jsonify({'success': True, 'rejoin_code': code})

@app.route('/api/admin/delete-key', methods=['POST'])
def api_admin_delete_key():
    data = request.json
    conn = get_db()
    conn.run("DELETE FROM keys WHERE key = :key", key=data.get('key', ''))
    conn.close()
    return jsonify({'success': True})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
