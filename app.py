from flask import Flask, jsonify, request
import json
import sqlite3
from datetime import datetime

app = Flask(__name__)

def init_db():
    conn = sqlite3.connect('tracker.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS location_history
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  lat REAL, lng REAL, speed REAL,
                  satellites INTEGER, rssi INTEGER,
                  hdop REAL, battery INTEGER,
                  timestamp TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS tamper_alerts
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  lat REAL, lng REAL,
                  battery INTEGER, timestamp TEXT)''')
    conn.commit()
    conn.close()

init_db()
latest_location = {}
tamper_alerts = []

@app.route('/update', methods=['POST'])
def update_location():
    global latest_location
    latest_location = request.json
    try:
        conn = sqlite3.connect('tracker.db')
        c = conn.cursor()
        c.execute('''INSERT INTO location_history
                     (lat, lng, speed, satellites, rssi, hdop, battery, timestamp)
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                  (latest_location.get('lat', 0),
                   latest_location.get('lng', 0),
                   latest_location.get('speed', 0),
                   latest_location.get('satellites', 0),
                   latest_location.get('rssi', 0),
                   latest_location.get('hdop', 0),
                   latest_location.get('battery', 0),
                   latest_location.get('timestamp',
                   datetime.now().strftime("%Y-%m-%d %H:%M:%S"))))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"DB error: {e}")
    return jsonify({"status": "ok"})

@app.route('/location', methods=['GET'])
def get_location():
    if latest_location:
        return jsonify(latest_location)
    return jsonify({"error": "No data yet"})

@app.route('/tamper', methods=['POST'])
def tamper_alert():
    global tamper_alerts
    data = request.json
    data['timestamp'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    tamper_alerts.append(data)
    try:
        conn = sqlite3.connect('tracker.db')
        c = conn.cursor()
        c.execute('''INSERT INTO tamper_alerts
                     (lat, lng, battery, timestamp)
                     VALUES (?, ?, ?, ?)''',
                  (data.get('lat', 0),
                   data.get('lng', 0),
                   data.get('battery', 0),
                   data.get('timestamp')))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"DB error: {e}")
    print(f"🚨 TAMPER ALERT received!")
    return jsonify({"status": "tamper_recorded"})

@app.route('/tamper/latest', methods=['GET'])
def get_tamper():
    if tamper_alerts:
        return jsonify(tamper_alerts[-1])
    return jsonify({"tamper": False})

@app.route('/history', methods=['GET'])
def get_history():
    try:
        date = request.args.get('date',
               datetime.now().strftime("%Y-%m-%d"))
        conn = sqlite3.connect('tracker.db')
        c = conn.cursor()
        c.execute('''SELECT lat, lng, speed, satellites,
                     rssi, battery, timestamp
                     FROM location_history
                     WHERE timestamp LIKE ?
                     ORDER BY timestamp DESC
                     LIMIT 100''', (f"{date}%",))
        rows = c.fetchall()
        conn.close()
        history = []
        for row in rows:
            history.append({
                "lat": row[0], "lng": row[1],
                "speed": row[2], "satellites": row[3],
                "rssi": row[4], "battery": row[5],
                "timestamp": row[6]
            })
        return jsonify(history)
    except Exception as e:
        return jsonify({"error": str(e)})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
