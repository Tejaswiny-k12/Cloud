import sqlite3
import json
from datetime import datetime, timedelta
from typing import Dict, List, Tuple

DB_PATH = 'anomalies.db'

class AnomalyDB:
    """Database utility class for anomaly management"""
    
    @staticmethod
    def init_db():
        """Initialize database with required tables"""
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
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                device_id TEXT NOT NULL,
                alert_type TEXT,
                severity TEXT,
                message TEXT,
                is_resolved INTEGER DEFAULT 0
            )
        ''')
        
        conn.commit()
        conn.close()
    
    @staticmethod
    def log_telemetry(device_id: str, data: Dict, is_anomaly: bool, anomaly_type: str = None) -> int:
        """Log telemetry data to database"""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        timestamp = datetime.now().isoformat()
        
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
        row_id = cursor.lastrowid
        conn.close()
        
        return row_id
    
    @staticmethod
    def get_anomalies(hours: int = 24, device_id: str = None) -> List[Tuple]:
        """Retrieve anomalies from last N hours"""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        if device_id:
            cursor.execute('''
                SELECT * FROM anomalies 
                WHERE is_anomaly = 1 
                AND device_id = ?
                AND timestamp > datetime('now', '-' || ? || ' hours')
                ORDER BY timestamp DESC
            ''', (device_id, hours))
        else:
            cursor.execute('''
                SELECT * FROM anomalies 
                WHERE is_anomaly = 1 
                AND timestamp > datetime('now', '-' || ? || ' hours')
                ORDER BY timestamp DESC
            ''', (hours,))
        
        results = cursor.fetchall()
        conn.close()
        
        return results
    
    @staticmethod
    def get_device_stats(device_id: str) -> Dict:
        """Get statistics for a specific device"""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Total readings
        cursor.execute('''
            SELECT COUNT(*) as total FROM anomalies WHERE device_id = ?
        ''', (device_id,))
        total = cursor.fetchone()[0]
        
        # Anomalies
        cursor.execute('''
            SELECT COUNT(*) as anomalies FROM anomalies 
            WHERE device_id = ? AND is_anomaly = 1
        ''', (device_id,))
        anomalies = cursor.fetchone()[0]
        
        # Anomaly rate
        anomaly_rate = (anomalies / total * 100) if total > 0 else 0
        
        # Device info
        cursor.execute('SELECT * FROM devices WHERE device_id = ?', (device_id,))
        device = cursor.fetchone()
        
        conn.close()
        
        return {
            'device_id': device_id,
            'total_readings': total,
            'anomalies': anomalies,
            'anomaly_rate': anomaly_rate,
            'first_seen': device[1] if device else None,
            'last_seen': device[2] if device else None,
            'status': device[4] if device else 'UNKNOWN'
        }
    
    @staticmethod
    def create_alert(device_id: str, alert_type: str, severity: str, message: str):
        """Create an alert for an anomaly"""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        timestamp = datetime.now().isoformat()
        
        cursor.execute('''
            INSERT INTO alerts (timestamp, device_id, alert_type, severity, message)
            VALUES (?, ?, ?, ?, ?)
        ''', (timestamp, device_id, alert_type, severity, message))
        
        conn.commit()
        conn.close()
    
    @staticmethod
    def get_active_alerts(hours: int = 24) -> List[Tuple]:
        """Get unresolved alerts from last N hours"""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM alerts 
            WHERE is_resolved = 0
            AND timestamp > datetime('now', '-' || ? || ' hours')
            ORDER BY timestamp DESC
        ''', (hours,))
        
        results = cursor.fetchall()
        conn.close()
        
        return results

class AnomalyDetector:
    """Anomaly detection utility class"""
    
    # Medical reference ranges
    NORMAL_RANGES = {
        'heart_rate': (60, 100),
        'body_temp': (36.0, 37.5),
        'signal_strength': (-100, -30),
        'battery_level': (10, 100)
    }
    
    @staticmethod
    def check_medical_range(data: Dict) -> Tuple[bool, str]:
        """Check if readings are within normal medical ranges"""
        
        if data.get('heart_rate'):
            hr_min, hr_max = AnomalyDetector.NORMAL_RANGES['heart_rate']
            if not (hr_min <= data['heart_rate'] <= hr_max):
                return True, 'OUT_OF_RANGE_HR'
        
        if data.get('body_temp'):
            temp_min, temp_max = AnomalyDetector.NORMAL_RANGES['body_temp']
            if not (temp_min <= data['body_temp'] <= temp_max):
                return True, 'OUT_OF_RANGE_TEMP'
        
        if data.get('signal_strength'):
            sig_min, sig_max = AnomalyDetector.NORMAL_RANGES['signal_strength']
            if not (sig_min <= data['signal_strength'] <= sig_max):
                return True, 'WEAK_SIGNAL'
        
        if data.get('battery_level'):
            if data['battery_level'] < 10:
                return True, 'LOW_BATTERY'
        
        return False, None
    
    @staticmethod
    def get_anomaly_severity(anomaly_type: str) -> str:
        """Get severity level for anomaly type"""
        critical = ['OUT_OF_RANGE_HR', 'OUT_OF_RANGE_TEMP', 'ML_ANOMALY']
        warning = ['WEAK_SIGNAL', 'LOW_BATTERY']
        
        if anomaly_type in critical:
            return 'CRITICAL'
        elif anomaly_type in warning:
            return 'WARNING'
        else:
            return 'INFO'

def export_logs_to_csv(filepath: str, hours: int = 24):
    """Export logs to CSV file"""
    import csv
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT * FROM anomalies 
        WHERE timestamp > datetime('now', '-' || ? || ' hours')
        ORDER BY timestamp DESC
    ''', (hours,))
    
    rows = cursor.fetchall()
    conn.close()
    
    if rows:
        with open(filepath, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['ID', 'Timestamp', 'Device ID', 'Heart Rate', 'Temp', 'Signal', 'Battery', 'Anomaly', 'Type', 'Raw Data'])
            writer.writerows(rows)
    
    return len(rows)
