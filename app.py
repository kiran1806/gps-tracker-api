from flask import Flask, request, jsonify
import sqlite3
import requests
import time
import os
from datetime import datetime, timezone

app = Flask(__name__)
DB_PATH = 'gps.db'

FAST2SMS_API_KEY = os.environ.get('FAST2SMS_API_KEY', 'YOUR_API_KEY_HERE')
ALERT_PHONE      = os.environ.get('ALERT_PHONE', '9999999999')

last_alert_sent = {
    'geofence': 0,
    'distance': 0,
    'offline':  0,
    'belt_cut': 0,
}
COOLDOWN_SECONDS = 300

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS locations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        lat REAL, lng REAL, speed REAL,
        satellites INTEGER, rssi INTEGER, battery INTEGER,
        belt_cut INTEGER DEFAULT 0,
        timestamp TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS sms_config (
        id INTEGER PRIMARY KEY,
        phone TEXT,
        geofence_alert INTEGER DEFAULT 1,
        distance_alert INTEGER DEFAULT 1,
        offline_alert INTEGER DEFAULT 1,
        belt_cut_alert INTEGER DEFAULT 1,
        geofence_lat REAL DEFAULT 0,
        geofence_lng REAL DEFAULT 0,
        geofence_radius REAL DEFAULT 100,
        max_distance REAL DEFAULT 500,
        home_lat REAL DEFAULT 0,
        home_lng REAL DEFAULT 0
    )''')
    c.execute('INSERT OR IGNORE INTO sms_config (id, phone) VALUES (1, ?)', (ALERT_PHONE,))
    conn.commit()
    conn.close()

init_db()

def send_sms(phone, message, alert_type):
    now = time.time()
    if now - last_alert_sent.get(alert_type, 0) < COOLDOWN_SECONDS:
        print(f"[SMS] Cooldown active for '{alert_type}', skipping.")
        return False
    try:
        response = requests.post(
            'https://www.fast2sms.com/dev/bulkV2',
            headers={'authorization': FAST2SMS_API_KEY},
            json={'route': 'q', 'message': message, 'language': 'english', 'flash': 0, 'numbers': phone},
            timeout=10
        )
        data = response.json()
        if data.get('return') is True:
            last_alert_sent[alert_type] = now
            print(f"[SMS] Sent '{alert_type}' to {phone}")
            return True
        else:
            print(f"[SMS] Failed: {data}")
            return False
    except Exception as e:
        print(f"[SMS] Error: {e}")
        return False

def get_sms_config():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT * FROM sms_config WHERE id=1')
    row = c.fetchone()
    conn.close()
    if row:
        return {
            'phone': row[1],
            'geofence_alert': bool(row[2]),
            'distance_alert': bool(row[3]),
            'offline_alert':  bool(row[4]),
            'belt_cut_alert': bool(row[5]),
            'geofence_lat':   row[6],
            'geofence_lng':   row[7],
            'geofence_radius':row[8],
            'max_distance':   row[9],
            'home_lat':       row[10],
            'home_lng':       row[11],
        }
    return None

def haversine(la1, lo1, la2, lo2):
    from math import radians, sin, cos, sqrt, atan2
    R = 6371000
    f1, f2 = radians(la1), radians(la2)
    df, dl = radians(la2-la1), radians(lo2-lo1)
    a = sin(df/2)**2 + cos(f1)*cos(f2)*sin(dl/2)**2
    return R * 2 * atan2(sqrt(a), sqrt(1-a))

def check_and_send_alerts(data):
    cfg = get_sms_config()
    if not cfg or not cfg['phone']:
        return
    phone = cfg['phone']
    lat   = data.get('lat', 0)
    lng   = data.get('lng', 0)
    belt  = data.get('belt_cut', 0)
    ts    = data.get('timestamp', '')

    if belt == 1 and cfg['belt_cut_alert']:
        send_sms(phone, f"ALERT! Cow collar removed/cut at {ts}. Last location: {lat:.5f},{lng:.5f}. Check immediately!", 'belt_cut')

    if cfg['geofence_alert'] and cfg['geofence_lat'] != 0:
        dist = haversine(lat, lng, cfg['geofence_lat'], cfg['geofence_lng'])
        if dist > cfg['geofence_radius']:
            send_sms(phone, f"ALERT! Cow left safe zone at {ts}. Location: {lat:.5f},{lng:.5f}. Distance: {dist:.0f}m.", 'geofence')

    if cfg['distance_alert'] and cfg['home_lat'] != 0:
        dist = haversine(lat, lng, cfg['home_lat'], cfg['home_lng'])
        if dist > cfg['max_distance']:
            send_sms(phone, f"ALERT! Cow is {dist:.0f}m from home at {ts}. Location: {lat:.5f},{lng:.5f}.", 'distance')

@app.route('/update', methods=['POST'])
def update_location():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data'}), 400
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('INSERT INTO locations (lat,lng,speed,satellites,rssi,battery,belt_cut,timestamp) VALUES (?,?,?,?,?,?,?,?)', (
        data.get('lat',0), data.get('lng',0), data.get('speed',0),
        data.get('satellites',0), data.get('rssi',0), data.get('battery',0),
        data.get('belt_cut',0), datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S'),
    ))
    conn.commit()
    conn.close()
    check_and_send_alerts(data)
    return jsonify({'status': 'ok'})

@app.route('/location', methods=['GET'])
def get_location():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT lat,lng,speed,satellites,rssi,battery,belt_cut,timestamp FROM locations ORDER BY id DESC LIMIT 1')
    row = c.fetchone()
    conn.close()
    if row:
        return jsonify({'lat':row[0],'lng':row[1],'speed':row[2],'satellites':row[3],'rssi':row[4],'battery':row[5],'belt_cut':row[6],'timestamp':row[7]})
    return jsonify({'error':'No data'}), 404

@app.route('/history', methods=['GET'])
def get_history():
    limit = request.args.get('limit', 100)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT lat,lng,speed,satellites,rssi,battery,belt_cut,timestamp FROM locations ORDER BY id DESC LIMIT ?', (limit,))
    rows = c.fetchall()
    conn.close()
    return jsonify([{'lat':r[0],'lng':r[1],'speed':r[2],'satellites':r[3],'rssi':r[4],'battery':r[5],'belt_cut':r[6],'timestamp':r[7]} for r in rows])

@app.route('/offline-alert', methods=['POST'])
def offline_alert():
    cfg = get_sms_config()
    if cfg and cfg['phone'] and cfg['offline_alert']:
        ts = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
        send_sms(cfg['phone'], f"ALERT! Cow tracker went OFFLINE at {ts}. Check device and signal.", 'offline')
    return jsonify({'status': 'ok'})

@app.route('/sms-config', methods=['GET'])
def get_sms_config_route():
    return jsonify(get_sms_config() or {})

@app.route('/sms-config', methods=['POST'])
def update_sms_config():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data'}), 400
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''UPDATE sms_config SET phone=?,geofence_alert=?,distance_alert=?,
        offline_alert=?,belt_cut_alert=?,geofence_lat=?,geofence_lng=?,
        geofence_radius=?,max_distance=?,home_lat=?,home_lng=? WHERE id=1''', (
        data.get('phone',''), int(data.get('geofence_alert',1)),
        int(data.get('distance_alert',1)), int(data.get('offline_alert',1)),
        int(data.get('belt_cut_alert',1)), data.get('geofence_lat',0),
        data.get('geofence_lng',0), data.get('geofence_radius',100),
        data.get('max_distance',500), data.get('home_lat',0), data.get('home_lng',0),
    ))
    conn.commit()
    conn.close()
    return jsonify({'status': 'ok'})

@app.route('/test-sms', methods=['POST'])
def test_sms():
    cfg = get_sms_config()
    if not cfg or not cfg['phone']:
        return jsonify({'error': 'No phone configured'}), 400
    last_alert_sent['geofence'] = 0
    result = send_sms(cfg['phone'], "Cow Tracker: Test SMS working! Your alerts are configured correctly.", 'geofence')
    return jsonify({'sent': result})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
