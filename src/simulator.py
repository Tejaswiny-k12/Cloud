import paho.mqtt.client as mqtt
import json
import time
import random
from datetime import datetime
import os
import ssl

# Configuration
MQTT_BROKER = os.getenv('MQTT_BROKER', 'localhost')
MQTT_PORT = int(os.getenv('MQTT_PORT', 8883))  # Changed to secure port
MQTT_TOPIC = os.getenv('MQTT_TOPIC', '/iot/health')
MQTT_USE_TLS = os.getenv('MQTT_USE_TLS', 'true').lower() == 'true'
MQTT_TLS_CA_CERTS = os.getenv('MQTT_TLS_CA_CERTS', './certs/ca.crt')
DEVICE_ID = os.getenv('DEVICE_ID', 'ESP32_001')
SEND_INTERVAL = int(os.getenv('SEND_INTERVAL', 3))  # seconds

# Normal medical ranges
NORMAL_HR = (60, 100)
NORMAL_TEMP = (36.0, 37.5)
NORMAL_SIGNAL = (-80, -30)
NORMAL_BATTERY = (20, 100)

client = None

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print(f"✓ Simulator connected to MQTT broker at {MQTT_BROKER}:{MQTT_PORT}")
    else:
        print(f"✗ Connection failed with code {rc}")

def on_disconnect(client, userdata, rc):
    if rc != 0:
        print(f"✗ Unexpected disconnection: {rc}")

def simulate_data():
    """Simulate realistic medical telemetry data"""
    data = {
        'device_id': DEVICE_ID,
        'timestamp': datetime.now().isoformat(),
        'heart_rate': random.randint(NORMAL_HR[0], NORMAL_HR[1]),
        'body_temp': round(random.uniform(NORMAL_TEMP[0], NORMAL_TEMP[1]), 2),
        'signal_strength': random.randint(NORMAL_SIGNAL[0], NORMAL_SIGNAL[1]),
        'battery_level': random.randint(NORMAL_BATTERY[0], NORMAL_BATTERY[1])
    }
    return data

def simulate_anomaly():
    """Occasionally inject anomalies to test detection"""
    anomaly_type = random.choice(['hr', 'temp', 'signal', 'battery'])
    data = {
        'device_id': DEVICE_ID,
        'timestamp': datetime.now().isoformat(),
        'heart_rate': random.choice([150, 30]) if anomaly_type == 'hr' else random.randint(NORMAL_HR[0], NORMAL_HR[1]),
        'body_temp': random.choice([39.0, 34.0]) if anomaly_type == 'temp' else round(random.uniform(NORMAL_TEMP[0], NORMAL_TEMP[1]), 2),
        'signal_strength': -120 if anomaly_type == 'signal' else random.randint(NORMAL_SIGNAL[0], NORMAL_SIGNAL[1]),
        'battery_level': 5 if anomaly_type == 'battery' else random.randint(NORMAL_BATTERY[0], NORMAL_BATTERY[1])
    }
    return data

def publish_data():
    """Continuously publish telemetry data"""
    counter = 0
    while True:
        try:
            # Every 10th reading, inject an anomaly
            if counter % 10 == 0 and counter > 0:
                data = simulate_anomaly()
                print(f"⚠️  Injecting anomaly: {data}")
            else:
                data = simulate_data()
            
            payload = json.dumps(data)
            client.publish(MQTT_TOPIC, payload)
            print(f"[{data['timestamp']}] Published (#{counter}): HR={data['heart_rate']}, Temp={data['body_temp']}°C, Signal={data['signal_strength']}, Battery={data['battery_level']}%")
            
            counter += 1
            time.sleep(SEND_INTERVAL)
            
        except KeyboardInterrupt:
            print("\n✓ Stopping simulator...")
            break
        except Exception as e:
            print(f"✗ Error publishing data: {e}")
            time.sleep(SEND_INTERVAL)

def main():
    global client
    print("=" * 60)
    print("🏥 IoT Device Simulator - Medical Telemetry")
    print("=" * 60)
    print(f"Device ID: {DEVICE_ID}")
    print(f"MQTT Broker: {MQTT_BROKER}:{MQTT_PORT}")
    print(f"Topic: {MQTT_TOPIC}")
    print(f"Interval: {SEND_INTERVAL}s")
    print(f"TLS Enabled: {MQTT_USE_TLS}")
    print(f"Normal Ranges:")
    print(f"  Heart Rate: {NORMAL_HR[0]}-{NORMAL_HR[1]} bpm")
    print(f"  Body Temp: {NORMAL_TEMP[0]}-{NORMAL_TEMP[1]}°C")
    print(f"  Signal: {NORMAL_SIGNAL[0]} to {NORMAL_SIGNAL[1]} dBm")
    print(f"  Battery: {NORMAL_BATTERY[0]}-{NORMAL_BATTERY[1]}%")
    print("=" * 60)
    
    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    
    # Configure TLS if enabled
    if MQTT_USE_TLS:
        try:
            # Set TLS version and CA certificate
            client.tls_set(
                ca_certs=MQTT_TLS_CA_CERTS,
                certfile=None,
                keyfile=None,
                cert_reqs=ssl.CERT_NONE,
                tls_version=ssl.PROTOCOL_TLSv1_2,
                ciphers=None
            )
            # Disable hostname verification for self-signed certs
            client.tls_insecure_set(True)
            print(f"✓ TLS enabled for MQTT connection")
            print(f"  CA Certificate: {MQTT_TLS_CA_CERTS}")
        except Exception as e:
            print(f"✗ TLS configuration error: {e}")
            print("  Falling back to non-TLS connection")
    
    try:
        client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
        client.loop_start()
        time.sleep(1)  # Wait for connection
        publish_data()
    except Exception as e:
        print(f"✗ Failed to connect: {e}")
    finally:
        client.loop_stop()
        client.disconnect()

if __name__ == '__main__':
    main()
