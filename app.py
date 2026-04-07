from flask import Flask, request, jsonify
import sqlite3
import time
import os
from datetime import datetime, timezone

app = Flask(__name__)
DB_PATH = 'gps.db'

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS locations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        lat REAL, lng REAL, speed REAL,
        satellites INTEGER, rssi INTEGER, battery INTEGER,
        belt_cut INTEGER DEFAULT 0,
        snr REAL DEFAULT 0,
        hdop REAL DEFAULT 0,
        freq_error REAL DEFAULT 0,
        module_temp INTEGER DEFAULT 0,
        packets_received INTEGER DEFAULT 0,
        packets_corrupted INTEGER DEFAULT 0,
        packet_loss REAL DEFAULT 0,
        timestamp TEXT
    )''')
    existing = [row[1] for row in c.execute("PRAGMA table_info(locations)")]
    new_cols = {
        'snr': 'REAL DEFAULT 0',
        'hdop': 'REAL DEFAULT 0',
        'freq_error': 'REAL DEFAULT 0',
        'module_temp': 'INTEGER DEFAULT 0',
        'packets_received': 'INTEGER DEFAULT 0',
        'packets_corrupted': 'INTEGER DEFAULT 0',
        'packet_loss': 'REAL DEFAULT 0',
        'belt_cut': 'INTEGER DEFAULT 0',
    }
    for col, col_type in new_cols.items():
        if col not in existing:
            c.execute(f'ALTER TABLE locations ADD COLUMN {col} {col_type}')
    conn.commit()
    conn.close()

init_db()

@app.route('/update', methods=['POST'])
def update_location():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data'}), 400
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''INSERT INTO locations
        (lat, lng, speed, satellites, rssi, battery, belt_cut,
         snr, hdop, freq_error, module_temp,
         packets_received, packets_corrupted, packet_loss, timestamp)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''', (
        data.get('lat', 0),
        data.get('lng', 0),
        data.get('speed', 0),
        data.get('satellites', 0),
        data.get('rssi', 0),
        data.get('battery', 0),
        data.get('belt_cut', 0),
        data.get('snr', 0),
        data.get('hdop', 0),
        data.get('freq_error', 0),
        data.get('module_temp', 0),
        data.get('packets_received', 0),
        data.get('packets_corrupted', 0),
        data.get('packet_loss', 0),
        datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S'),
    ))
    conn.commit()
    conn.close()
    return jsonify({'status': 'ok'})

@app.route('/location', methods=['GET'])
def get_location():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''SELECT lat, lng, speed, satellites, rssi, battery, belt_cut,
                        snr, hdop, freq_error, module_temp,
                        packets_received, packets_corrupted, packet_loss, timestamp
                 FROM locations ORDER BY id DESC LIMIT 1''')
    row = c.fetchone()
    conn.close()
    if row:
        return jsonify({
            'lat': row[0], 'lng': row[1], 'speed': row[2],
            'satellites': row[3], 'rssi': row[4], 'battery': row[5],
            'belt_cut': row[6],
            'snr': row[7], 'hdop': row[8], 'freq_error': row[9],
            'module_temp': row[10],
            'packets_received': row[11], 'packets_corrupted': row[12],
            'packet_loss': row[13],
            'timestamp': row[14],
        })
    return jsonify({'error': 'No data'}), 404

@app.route('/history', methods=['GET'])
def get_history():
    date = request.args.get('date', datetime.now(timezone.utc).strftime('%Y-%m-%d'))
    limit = request.args.get('limit', 500)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''SELECT lat, lng, speed, satellites, rssi, battery,
                        snr, hdop, freq_error, module_temp,
                        packets_received, packets_corrupted, packet_loss, timestamp
                 FROM locations WHERE timestamp LIKE ?
                 ORDER BY id DESC LIMIT ?''', (f'{date}%', limit))
    rows = c.fetchall()
    conn.close()
    return jsonify([{
        'lat': r[0], 'lng': r[1], 'speed': r[2],
        'satellites': r[3], 'rssi': r[4], 'battery': r[5],
        'snr': r[6], 'hdop': r[7], 'freq_error': r[8],
        'module_temp': r[9],
        'packets_received': r[10], 'packets_corrupted': r[11],
        'packet_loss': r[12], 'timestamp': r[13],
    } for r in rows])

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
