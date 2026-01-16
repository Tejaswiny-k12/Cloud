from flask import Flask, request, jsonify
import paho.mqtt.client as mqtt
import joblib
import sqlite3
import json
from datetime import datetime
import threading
import os
import ssl

app = Flask(__name__)

# Configuration
MQTT_BROKER = os.getenv('MQTT_BROKER', 'mosquitto')
MQTT_PORT = int(os.getenv('MQTT_PORT', 8883))  # Changed to secure port
MQTT_TOPIC = os.getenv('MQTT_TOPIC', '/iot/health')
MQTT_USE_TLS = os.getenv('MQTT_USE_TLS', 'true').lower() == 'true'
MQTT_TLS_CA_CERTS = os.getenv('MQTT_TLS_CA_CERTS', '/app/certs/ca.crt')
DB_PATH = 'anomalies.db'
MODEL_PATH = 'model.pkl'

# Global variables
model = None
mqtt_client = None
device_registry = {}  # Track known devices

# Initialize SQLite Database
def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS anomalies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            device_id TEXT NOT NULL,
            heart_rate REAL,
            body_temp REAL,
            signal_strength REAL,
            battery_level REAL,
            is_anomaly INTEGER,
            anomaly_type TEXT,
            raw_data TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS devices (
            device_id TEXT PRIMARY KEY,
            first_seen TEXT,
            last_seen TEXT,
            total_readings INTEGER,
            status TEXT
        )
    ''')
    conn.commit()
    conn.close()

# Load ML Model
def load_model():
    global model
    if os.path.exists(MODEL_PATH):
        model = joblib.load(MODEL_PATH)
        print(f"✓ Model loaded from {MODEL_PATH}")
    else:
        print(f"✗ Model not found at {MODEL_PATH}")
        model = None

# MQTT Callbacks
def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print(f"✓ MQTT Connected to {MQTT_BROKER}:{MQTT_PORT}")
        client.subscribe(MQTT_TOPIC)
        print(f"✓ Subscribed to {MQTT_TOPIC}")
    else:
        print(f"✗ MQTT Connection failed with code {rc}")

def on_message(client, userdata, msg):
    try:
        payload = json.loads(msg.payload.decode())
        process_telemetry(payload)
    except json.JSONDecodeError:
        print(f"✗ Invalid JSON from MQTT: {msg.payload}")
    except Exception as e:
        print(f"✗ Error processing MQTT message: {e}")

def on_disconnect(client, userdata, rc):
    if rc != 0:
        print(f"✗ Unexpected disconnection: {rc}")

# Process incoming telemetry
def process_telemetry(data):
    timestamp = datetime.now().isoformat()
    device_id = data.get('device_id', 'UNKNOWN')
    
    # Validate required fields
    required_fields = ['heart_rate', 'body_temp', 'signal_strength', 'battery_level']
    if not all(field in data for field in required_fields):
        log_anomaly(device_id, data, timestamp, 'MISSING_FIELDS', data)
        return
    
    # Extract features
    features = [[
        data['heart_rate'],
        data['body_temp'],
        data['signal_strength'],
        data['battery_level']
    ]]
    
    # Detect anomalies
    is_anomaly = False
    anomaly_type = None
    
    # Check medical ranges
    if not (60 <= data['heart_rate'] <= 100):
        is_anomaly = True
        anomaly_type = 'OUT_OF_RANGE_HR'
    if not (36.0 <= data['body_temp'] <= 37.5):
        is_anomaly = True
        anomaly_type = 'OUT_OF_RANGE_TEMP'
    if data['battery_level'] < 10:
        is_anomaly = True
        anomaly_type = 'LOW_BATTERY'
    if data['signal_strength'] < -100:
        is_anomaly = True
        anomaly_type = 'WEAK_SIGNAL'
    
    # ML Model prediction
    if model is not None:
        prediction = model.predict(features)
        if prediction[0] == -1:
            is_anomaly = True
            anomaly_type = 'ML_ANOMALY'
    
    # Log data
    log_data(device_id, data, timestamp, is_anomaly, anomaly_type)
    
    # Update device registry
    update_device_registry(device_id, timestamp)
    
    if is_anomaly:
        print(f"⚠️  [{timestamp}] ANOMALY from {device_id}: {anomaly_type}")
        print(f"   Data: {data}")

# Log data to SQLite
def log_data(device_id, data, timestamp, is_anomaly, anomaly_type):
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO anomalies 
            (timestamp, device_id, heart_rate, body_temp, signal_strength, battery_level, is_anomaly, anomaly_type, raw_data)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            timestamp,
            device_id,
            data.get('heart_rate'),
            data.get('body_temp'),
            data.get('signal_strength'),
            data.get('battery_level'),
            1 if is_anomaly else 0,
            anomaly_type,
            json.dumps(data)
        ))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"✗ Error logging data: {e}")

def log_anomaly(device_id, data, timestamp, anomaly_type, raw_data):
    log_data(device_id, data, timestamp, True, anomaly_type)

def update_device_registry(device_id, timestamp):
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM devices WHERE device_id = ?', (device_id,))
        if cursor.fetchone():
            cursor.execute('''
                UPDATE devices 
                SET last_seen = ?, total_readings = total_readings + 1
                WHERE device_id = ?
            ''', (timestamp, device_id))
        else:
            cursor.execute('''
                INSERT INTO devices (device_id, first_seen, last_seen, total_readings, status)
                VALUES (?, ?, ?, 1, 'ACTIVE')
            ''', (device_id, timestamp, timestamp))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"✗ Error updating device registry: {e}")

# Flask Routes
@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'running', 'model_loaded': model is not None}), 200

@app.route('/api/telemetry', methods=['POST'])
def receive_telemetry():
    try:
        data = request.get_json()
        timestamp = datetime.now().isoformat()
        print(f"[{timestamp}] HTTP POST: {data}")
        process_telemetry(data)
        return jsonify({'status': 'received'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/api/devices', methods=['GET'])
def get_devices():
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM devices')
        devices = cursor.fetchall()
        conn.close()
        return jsonify(devices), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/api/anomalies', methods=['GET'])
def get_anomalies():
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM anomalies WHERE is_anomaly = 1 ORDER BY timestamp DESC')
        anomalies = cursor.fetchall()
        conn.close()
        return jsonify(anomalies), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 400

# MQTT Connection in background thread
def init_mqtt():
    global mqtt_client
    mqtt_client = mqtt.Client()
    mqtt_client.on_connect = on_connect
    mqtt_client.on_message = on_message
    mqtt_client.on_disconnect = on_disconnect
    
    # Configure TLS if enabled
    if MQTT_USE_TLS:
        try:
            # Set TLS version and CA certificate
            mqtt_client.tls_set(
                ca_certs=MQTT_TLS_CA_CERTS,
                certfile=None,
                keyfile=None,
                cert_reqs=ssl.CERT_NONE,
                tls_version=ssl.PROTOCOL_TLSv1_2,
                ciphers=None
            )
            # Disable hostname verification for self-signed certs
            mqtt_client.tls_insecure_set(True)
            print(f"✓ TLS enabled for MQTT connection")
            print(f"  CA Certificate: {MQTT_TLS_CA_CERTS}")
        except Exception as e:
            print(f"✗ TLS configuration error: {e}")
            print("  Falling back to non-TLS connection")
    
    def connect_mqtt():
        try:
            print(f"Connecting to {MQTT_BROKER}:{MQTT_PORT} (TLS: {MQTT_USE_TLS})...")
            mqtt_client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
            mqtt_client.loop_forever()
        except Exception as e:
            print(f"✗ MQTT Connection error: {e}")
    
    thread = threading.Thread(target=connect_mqtt, daemon=True)
    thread.start()

if __name__ == '__main__':
    print("=" * 50)
    print("🏥 Healthcare IoT Monitoring System - Flask API")
    print("=" * 50)
    init_db()
    load_model()
    init_mqtt()
    print(f"Starting Flask on 0.0.0.0:5000")
    app.run(host='0.0.0.0', port=5000, debug=False)
