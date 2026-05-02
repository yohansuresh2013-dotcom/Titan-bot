from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import os
import uuid
import random
import psycopg2
import psycopg2.extras
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = 'titan_key_system_2024'
CORS(app)

# ============ CONFIG ============
PLATFORM_PASSWORD = 'NVTITAN'
ADMIN_PASSWORD = '2009'
ADMIN_KEY = '2009'
DEFAULT_TOKENS = 5
ADMIN_ID = 'BZ-ADMIN'
TELEGRAM_USERNAME = '@vikranthxx0'

# ============ SUPABASE DATABASE ============
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://postgres:Vikranth2009@db.trgljrubmvwzyywnwozo.supabase.co:5432/postgres")

PACKAGES = {
    '20': {'tokens': 20, 'price': '500₹'},
    '30': {'tokens': 30, 'price': '1000₹'},
    '60': {'tokens': 60, 'price': '1500₹'},
    'unlimited': {'tokens': 9999, 'price': '5000₹', 'duration_days': 30}
}

def get_ist_now():
    return datetime.utcnow() + timedelta(hours=5, minutes=30)

def get_db():
    """Connect to Supabase PostgreSQL"""
    conn = psycopg2.connect(DATABASE_URL)
    conn.row_factory = psycopg2.extras.DictRow
    return conn

def init_db():
    conn = get_db()
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
    
    c.execute('''CREATE TABLE IF NOT EXISTS purchases (
        id SERIAL PRIMARY KEY,
        user_id TEXT,
        package TEXT,
        amount TEXT,
        tokens INTEGER,
        status TEXT DEFAULT 'pending',
        created_at TEXT
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS revenue (
        id SERIAL PRIMARY KEY,
        user_id TEXT,
        package TEXT,
        amount TEXT,
        tokens INTEGER,
        created_at TEXT
    )''')
    
    # Create admin
    c.execute("SELECT id FROM users WHERE id = %s", (ADMIN_ID,))
    if not c.fetchone():
        c.execute('''INSERT INTO users (id, access_key, tokens, analyses, online, kicked, is_admin, joined_at)
                     VALUES (%s, %s, 9999, 0, 0, 0, 1, %s)''',
                  (ADMIN_ID, ADMIN_KEY, get_ist_now().isoformat()))
        c.execute('''INSERT INTO keys (key, user_id, created_at, used)
                     VALUES (%s, %s, %s, 0)''',
                  (ADMIN_KEY, ADMIN_ID, get_ist_now().isoformat()))
    
    conn.commit()
    conn.close()

init_db()

def get_user(user_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE id = %s", (user_id,))
    user = c.fetchone()
    conn.close()
    return user

def update_user(user_id, **kwargs):
    conn = get_db()
    c = conn.cursor()
    for k, v in kwargs.items():
        c.execute(f"UPDATE users SET {k} = %s WHERE id = %s", (v, user_id))
    conn.commit()
    conn.close()

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
    
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM keys WHERE key = %s", (access_key,))
    key_data = c.fetchone()
    
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
    
    c.execute("UPDATE keys SET used = 1, ip_address = %s WHERE key = %s", (ip, access_key))
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
    if data.get('password') != ADMIN_PASSWORD:
        return jsonify({'success': False})
    
    user_id = 'TITAN-' + uuid.uuid4().hex[:6].upper()
    access_key = 'TITAN-' + uuid.uuid4().hex[:8].upper()
    
    conn = get_db()
    c = conn.cursor()
    c.execute('''INSERT INTO users (id, access_key, tokens, analyses, online, kicked, is_admin, joined_at)
                 VALUES (%s, %s, %s, 0, 0, 0, 0, %s)''',
              (user_id, access_key, DEFAULT_TOKENS, get_ist_now().isoformat()))
    c.execute('''INSERT INTO keys (key, user_id, created_at, used)
                 VALUES (%s, %s, %s, 0)''',
              (access_key, user_id, get_ist_now().isoformat()))
    conn.commit()
    conn.close()
    
    return jsonify({'success': True, 'key': access_key, 'user_id': user_id, 'tokens': DEFAULT_TOKENS})

@app.route('/api/admin/keys', methods=['GET'])
def admin_keys():
    conn = get_db()
    c = conn.cursor()
    c.execute('''SELECT k.*, u.tokens, u.analyses, u.online, u.kicked 
                 FROM keys k JOIN users u ON k.user_id = u.id 
                 ORDER BY k.created_at DESC''')
    keys = c.fetchall()
    conn.close()
    return jsonify([dict(k) for k in keys])

@app.route('/api/analyze', methods=['POST'])
def api_analyze():
    data = request.json
    user_id = data.get('user_id', '')
    user = get_user(user_id)
    if not user: return jsonify({'success': False})
    
    if user['tokens'] <= 0: return jsonify({'success': False, 'message': 'No tokens!'})
    
    update_user(user_id, tokens=user['tokens'] - 1, analyses=user['analyses'] + 1)
    
    now = get_ist_now()
    next_min = now + timedelta(minutes=1)
    next_min = next_min.replace(second=0, microsecond=0)
    trade_time = next_min.strftime('%H:%M')
    
    r = random.random()
    if r < 0.25: result_type, direction = 'buy', 'BUY'
    elif r < 0.50: result_type, direction = 'sell', 'SELL'
    else: result_type, direction = 'unstable', 'UNSTABLE'
    
    conn = get_db()
    c = conn.cursor()
    c.execute('''INSERT INTO signals (user_id, direction, price, trade_time, trade_end_time, result_type, screenshot_name, created_at)
                 VALUES (%s, %s, 0, %s, '', %s, '', %s)''',
              (user_id, direction, trade_time, result_type, now.isoformat()))
    conn.commit()
    conn.close()
    
    updated = get_user(user_id)
    return jsonify({'success': True, 'signal_type': result_type, 'direction': direction, 'trade_time': trade_time, 'tokens': updated['tokens']})

@app.route('/api/purchase', methods=['POST'])
def api_purchase():
    data = request.json
    user_id = data.get('user_id', '')
    pkg = data.get('package', '')
    if pkg not in PACKAGES: return jsonify({'success': False})
    package = PACKAGES[pkg]
    conn = get_db()
    c = conn.cursor()
    c.execute('''INSERT INTO purchases (user_id, package, amount, tokens, status, created_at)
                 VALUES (%s, %s, %s, %s, 'pending', %s)''',
              (user_id, pkg, package['price'], package['tokens'], get_ist_now().isoformat()))
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'telegram_link': f"https://t.me/vikranthxx0?text=BUY%20{user_id}%20{pkg}"})

@app.route('/api/admin/users', methods=['GET'])
def api_admin_users():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE kicked = 0")
    users = c.fetchall()
    conn.close()
    return jsonify([dict(u) for u in users])

@app.route('/api/admin/revenue', methods=['GET'])
def api_admin_revenue():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) as total, COALESCE(SUM(tokens),0) as tokens FROM revenue")
    total = c.fetchone()
    conn.close()
    return jsonify({'total_purchases': total['total'], 'total_tokens_sold': total['tokens']})

@app.route('/api/admin/approve-purchase', methods=['POST'])
def api_approve_purchase():
    data = request.json
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM purchases WHERE id = %s", (data.get('purchase_id'),))
    purchase = c.fetchone()
    if not purchase: conn.close(); return jsonify({'success': False})
    user = get_user(purchase['user_id'])
    if purchase['package'] == 'unlimited':
        update_user(purchase['user_id'], unlimited_until=(get_ist_now() + timedelta(days=30)).isoformat())
    else:
        update_user(purchase['user_id'], tokens=user['tokens'] + purchase['tokens'])
    c.execute("INSERT INTO revenue (user_id, package, amount, tokens, created_at) VALUES (%s,%s,%s,%s,%s)",
              (purchase['user_id'], purchase['package'], purchase['amount'], purchase['tokens'], get_ist_now().isoformat()))
    c.execute("DELETE FROM purchases WHERE id = %s", (data.get('purchase_id'),))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/api/admin/pending-purchases', methods=['GET'])
def api_pending_purchases():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM purchases WHERE status = 'pending' ORDER BY id DESC")
    purchases = c.fetchall()
    conn.close()
    return jsonify([dict(p) for p in purchases])

@app.route('/api/admin/add-tokens', methods=['POST'])
def api_admin_add_tokens():
    data = request.json
    user = get_user(data.get('user_id'))
    if not user: return jsonify({'success': False})
    update_user(data['user_id'], tokens=user['tokens'] + int(data.get('amount', 0)))
    return jsonify({'success': True})

@app.route('/api/admin/kick', methods=['POST'])
def api_admin_kick():
    data = request.json
    if data.get('user_id') == ADMIN_ID: return jsonify({'success': False})
    code = 'TITAN-' + uuid.uuid4().hex[:8].upper()
    update_user(data['user_id'], kicked=1, online=0, rejoin_code=code)
    return jsonify({'success': True, 'rejoin_code': code})

@app.route('/api/admin/delete-key', methods=['POST'])
def api_admin_delete_key():
    data = request.json
    conn = get_db()
    c = conn.cursor()
    c.execute("DELETE FROM keys WHERE key = %s", (data.get('key'),))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
