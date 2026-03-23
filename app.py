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
                  lat REAL,
                  lng REAL,
                  speed REAL,
                  satellites INTEGER,
                  rssi INTEGER,
                  hdop REAL,
                  timestamp TEXT)''')
    conn.commit()
    conn.close()

init_db()

latest_location = {}

@app.route('/update', methods=['POST'])
def update_location():
    global latest_location
    latest_location = request.json
    
    # Save to history
    try:
        conn = sqlite3.connect('tracker.db')
        c = conn.cursor()
        c.execute('''INSERT INTO location_history 
                     (lat, lng, speed, satellites, rssi, hdop, timestamp)
                     VALUES (?, ?, ?, ?, ?, ?, ?)''',
                  (latest_location.get('lat', 0),
                   latest_location.get('lng', 0),
                   latest_location.get('speed', 0),
                   latest_location.get('satellites', 0),
                   latest_location.get('rssi', 0),
                   latest_location.get('hdop', 0),
                   latest_location.get('timestamp', datetime.now().strftime("%Y-%m-%d %H:%M:%S"))))
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

@app.route('/history', methods=['GET'])
def get_history():
    try:
        date = request.args.get('date', datetime.now().strftime("%Y-%m-%d"))
        conn = sqlite3.connect('tracker.db')
        c = conn.cursor()
        c.execute('''SELECT lat, lng, speed, satellites, rssi, timestamp 
                     FROM location_history 
                     WHERE timestamp LIKE ?
                     ORDER BY timestamp DESC
                     LIMIT 100''', (f"{date}%",))
        rows = c.fetchall()
        conn.close()
        
        history = []
        for row in rows:
            history.append({
                "lat": row[0],
                "lng": row[1],
                "speed": row[2],
                "satellites": row[3],
                "rssi": row[4],
                "timestamp": row[5]
            })
        return jsonify(history)
    except Exception as e:
        return jsonify({"error": str(e)})

@app.route('/history/clear', methods=['POST'])
def clear_history():
    try:
        conn = sqlite3.connect('tracker.db')
        c = conn.cursor()
        c.execute('DELETE FROM location_history')
        conn.commit()
        conn.close()
        return jsonify({"status": "cleared"})
    except Exception as e:
        return jsonify({"error": str(e)})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
