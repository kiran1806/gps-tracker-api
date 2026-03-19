from flask import Flask, jsonify, request
import json

app = Flask(__name__)

latest_location = {}

@app.route('/update', methods=['POST'])
def update_location():
    global latest_location
    latest_location = request.json
    return jsonify({"status": "ok"})

@app.route('/location', methods=['GET'])
def get_location():
    if latest_location:
        return jsonify(latest_location)
    return jsonify({"error": "No data yet"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
