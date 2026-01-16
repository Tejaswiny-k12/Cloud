import pandas as pd
import numpy as np
from sklearn.ensemble import IsolationForest, RandomForestClassifier
from sklearn.preprocessing import StandardScaler
import joblib
import os

# Generate synthetic normal training data
def generate_training_data(n_samples=1000):
    """Generate realistic medical telemetry training data"""
    np.random.seed(42)
    
    data = {
        'heart_rate': np.random.normal(72, 8, n_samples),  # Normal mean 72, std 8
        'body_temp': np.random.normal(36.8, 0.3, n_samples),  # Normal mean 36.8, std 0.3
        'signal_strength': np.random.normal(-60, 15, n_samples),  # Normal mean -60 dBm, std 15
        'battery_level': np.random.normal(75, 15, n_samples)  # Normal mean 75%, std 15
    }
    
    # Clip to realistic ranges
    data['heart_rate'] = np.clip(data['heart_rate'], 40, 120)
    data['body_temp'] = np.clip(data['body_temp'], 35.0, 39.0)
    data['signal_strength'] = np.clip(data['signal_strength'], -120, -20)
    data['battery_level'] = np.clip(data['battery_level'], 0, 100)
    
    return pd.DataFrame(data)

def train_isolation_forest(df):
    """Train Isolation Forest for unsupervised anomaly detection"""
    print("Training Isolation Forest...")
    
    scaler = StandardScaler()
    scaled_data = scaler.fit_transform(df)
    
    # Isolation Forest: -1 = anomaly, 1 = normal
    model = IsolationForest(contamination=0.05, random_state=42)
    model.fit(scaled_data)
    
    # Save scaler for inference
    joblib.dump(scaler, 'scaler.pkl')
    
    print(f"✓ Isolation Forest trained on {len(df)} samples")
    return model

def train_random_forest(df_normal, df_anomaly):
    """Train Random Forest for supervised anomaly classification (optional)"""
    print("Training Random Forest...")
    
    # Prepare data
    df_normal['label'] = 0  # Normal
    df_anomaly['label'] = 1  # Anomaly
    
    X = pd.concat([df_normal, df_anomaly], ignore_index=True)
    y = X['label']
    X = X.drop('label', axis=1)
    
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    
    # Random Forest
    model = RandomForestClassifier(n_estimators=100, random_state=42)
    model.fit(X_scaled, y)
    
    joblib.dump(scaler, 'rf_scaler.pkl')
    
    print(f"✓ Random Forest trained on {len(X)} samples")
    return model

def generate_anomalies(n_samples=100):
    """Generate synthetic anomalous data"""
    np.random.seed(43)
    
    data = {
        'heart_rate': np.concatenate([
            np.random.normal(30, 5, n_samples//2),
            np.random.normal(160, 10, n_samples//2)
        ]),
        'body_temp': np.concatenate([
            np.random.normal(34, 1, n_samples//2),
            np.random.normal(39, 1, n_samples//2)
        ]),
        'signal_strength': np.random.normal(-110, 5, n_samples),
        'battery_level': np.random.normal(5, 3, n_samples)
    }
    
    data['heart_rate'] = np.clip(data['heart_rate'], 0, 200)
    data['body_temp'] = np.clip(data['body_temp'], 30, 42)
    data['signal_strength'] = np.clip(data['signal_strength'], -120, -20)
    data['battery_level'] = np.clip(data['battery_level'], 0, 100)
    
    return pd.DataFrame(data)

def main():
    print("=" * 60)
    print("🧠 ML Model Training Pipeline")
    print("=" * 60)
    
    # Generate training data
    print("\n1. Generating synthetic normal data...")
    df_normal = generate_training_data(n_samples=1000)
    print(f"   Shape: {df_normal.shape}")
    print(f"   Mean HR: {df_normal['heart_rate'].mean():.1f} bpm")
    print(f"   Mean Temp: {df_normal['body_temp'].mean():.2f}°C")
    
    # Generate anomalies
    print("\n2. Generating synthetic anomalous data...")
    df_anomalies = generate_anomalies(n_samples=100)
    print(f"   Shape: {df_anomalies.shape}")
    
    # Train Isolation Forest
    print("\n3. Training Isolation Forest (unsupervised)...")
    iso_model = train_isolation_forest(df_normal)
    joblib.dump(iso_model, 'model.pkl')
    print("   Saved to model.pkl")
    
    # Train Random Forest (supervised, optional)
    print("\n4. Training Random Forest (supervised)...")
    rf_model = train_random_forest(df_normal, df_anomalies)
    joblib.dump(rf_model, 'rf_model.pkl')
    print("   Saved to rf_model.pkl")
    
    # Test predictions
    print("\n5. Testing predictions...")
    test_normal = df_normal.iloc[:5]
    test_anomaly = df_anomalies.iloc[:5]
    
    scaler = joblib.load('scaler.pkl')
    test_normal_scaled = scaler.transform(test_normal)
    test_anomaly_scaled = scaler.transform(test_anomaly)
    
    pred_normal = iso_model.predict(test_normal_scaled)
    pred_anomaly = iso_model.predict(test_anomaly_scaled)
    
    print(f"   Normal samples - Predictions (1=normal, -1=anomaly): {pred_normal[:5]}")
    print(f"   Anomaly samples - Predictions: {pred_anomaly[:5]}")
    
    print("\n" + "=" * 60)
    print("✓ Training complete! Models saved:")
    print("  - model.pkl (Isolation Forest)")
    print("  - rf_model.pkl (Random Forest)")
    print("  - scaler.pkl (Feature scaler)")
    print("  - rf_scaler.pkl (RF scaler)")
    print("=" * 60)

if __name__ == '__main__':
    main()
