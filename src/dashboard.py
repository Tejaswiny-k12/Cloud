import streamlit as st
import sqlite3
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
import os

# Page configuration
st.set_page_config(
    page_title="🏥 IoT Health Monitor",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Styling
st.markdown("""
    <style>
        .metric-card {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 20px;
            border-radius: 10px;
            color: white;
            text-align: center;
            font-size: 18px;
        }
        .anomaly-card {
            background: #ff6b6b;
            padding: 15px;
            border-radius: 8px;
            color: white;
            margin: 5px 0;
        }
        .normal-card {
            background: #51cf66;
            padding: 15px;
            border-radius: 8px;
            color: white;
            margin: 5px 0;
        }
    </style>
""", unsafe_allow_html=True)

# Database connection
DB_PATH = 'anomalies.db'

@st.cache_resource
def get_db_connection():
    return sqlite3.connect(DB_PATH)

def query_db(query):
    """Execute a SQL query and return results as DataFrame"""
    try:
        conn = get_db_connection()
        df = pd.read_sql_query(query, conn)
        return df
    except Exception as e:
        st.error(f"Database error: {e}")
        return pd.DataFrame()

def get_anomalies_last_n_hours(hours=24):
    """Get anomalies from last N hours"""
    query = f"""
        SELECT * FROM anomalies 
        WHERE is_anomaly = 1 
        AND timestamp > datetime('now', '-{hours} hours')
        ORDER BY timestamp DESC
    """
    return query_db(query)

def get_all_readings(hours=24):
    """Get all readings from last N hours"""
    query = f"""
        SELECT * FROM anomalies 
        WHERE timestamp > datetime('now', '-{hours} hours')
        ORDER BY timestamp DESC
    """
    return query_db(query)

def get_devices_status():
    """Get current status of all devices"""
    query = "SELECT * FROM devices ORDER BY last_seen DESC"
    return query_db(query)

def get_anomaly_stats():
    """Get anomaly statistics"""
    query = """
        SELECT 
            anomaly_type,
            COUNT(*) as count,
            MAX(timestamp) as last_detected
        FROM anomalies 
        WHERE is_anomaly = 1
        GROUP BY anomaly_type
        ORDER BY count DESC
    """
    return query_db(query)

def main():
    # Header
    st.title("🏥 Healthcare IoT Monitoring Dashboard")
    st.markdown("Real-time medical device telemetry & anomaly detection")
    
    # Sidebar filters
    st.sidebar.header("⚙️ Filters")
    hours_filter = st.sidebar.slider("Time Range (hours)", 1, 72, 24)
    device_filter = st.sidebar.multiselect(
        "Select Devices",
        query_db("SELECT DISTINCT device_id FROM devices")['device_id'].tolist(),
        default=None
    )
    
    # Top metrics row
    st.header("📊 System Overview")
    
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        total_devices = len(query_db("SELECT COUNT(DISTINCT device_id) as count FROM devices"))
        st.metric("Total Devices", total_devices, delta=None)
    
    with col2:
        df_readings = get_all_readings(hours_filter)
        total_readings = len(df_readings)
        st.metric("Total Readings", total_readings, delta=None)
    
    with col3:
        df_anomalies = get_anomalies_last_n_hours(hours_filter)
        anomaly_count = len(df_anomalies)
        st.metric("🚨 Anomalies Detected", anomaly_count, delta=None)
    
    with col4:
        if total_readings > 0:
            anomaly_rate = (anomaly_count / total_readings) * 100
            st.metric("Anomaly Rate", f"{anomaly_rate:.2f}%", delta=None)
        else:
            st.metric("Anomaly Rate", "0%", delta=None)
    
    with col5:
        active_devices = len(query_db(
            f"SELECT DISTINCT device_id FROM anomalies WHERE timestamp > datetime('now', '-1 hour')"
        ))
        st.metric("🟢 Active (1h)", active_devices, delta=None)
    
    # Tabs
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📈 Real-time Data",
        "🚨 Anomalies",
        "📱 Devices",
        "📊 Statistics",
        "📝 Logs"
    ])
    
    # Tab 1: Real-time Data
    with tab1:
        st.subheader("Real-time Telemetry")
        df_all = get_all_readings(hours_filter)
        
        if not df_all.empty:
            # Time series plots
            col1, col2 = st.columns(2)
            
            with col1:
                fig_hr = px.line(
                    df_all.sort_values('timestamp'),
                    x='timestamp',
                    y='heart_rate',
                    color='device_id',
                    title='Heart Rate Over Time',
                    markers=True
                )
                fig_hr.update_layout(height=400)
                st.plotly_chart(fig_hr, use_container_width=True)
            
            with col2:
                fig_temp = px.line(
                    df_all.sort_values('timestamp'),
                    x='timestamp',
                    y='body_temp',
                    color='device_id',
                    title='Body Temperature Over Time',
                    markers=True
                )
                fig_temp.update_layout(height=400)
                st.plotly_chart(fig_temp, use_container_width=True)
            
            col3, col4 = st.columns(2)
            
            with col3:
                fig_signal = px.line(
                    df_all.sort_values('timestamp'),
                    x='timestamp',
                    y='signal_strength',
                    color='device_id',
                    title='Signal Strength Over Time',
                    markers=True
                )
                fig_signal.update_layout(height=400)
                st.plotly_chart(fig_signal, use_container_width=True)
            
            with col4:
                fig_battery = px.line(
                    df_all.sort_values('timestamp'),
                    x='timestamp',
                    y='battery_level',
                    color='device_id',
                    title='Battery Level Over Time',
                    markers=True
                )
                fig_battery.update_layout(height=400)
                st.plotly_chart(fig_battery, use_container_width=True)
            
            st.subheader("Recent Readings")
            st.dataframe(
                df_all.sort_values('timestamp', ascending=False).head(20),
                use_container_width=True
            )
        else:
            st.info("No data available for the selected time range.")
    
    # Tab 2: Anomalies
    with tab2:
        st.subheader("🚨 Detected Anomalies")
        df_anom = get_anomalies_last_n_hours(hours_filter)
        
        if not df_anom.empty:
            # Anomaly type distribution
            col1, col2 = st.columns(2)
            
            with col1:
                fig_anom_type = px.bar(
                    df_anom['anomaly_type'].value_counts().reset_index(),
                    x='count',
                    y='anomaly_type',
                    title='Anomalies by Type',
                    orientation='h'
                )
                st.plotly_chart(fig_anom_type, use_container_width=True)
            
            with col2:
                fig_anom_device = px.bar(
                    df_anom['device_id'].value_counts().reset_index(),
                    x='count',
                    y='device_id',
                    title='Anomalies by Device',
                    orientation='h'
                )
                st.plotly_chart(fig_anom_device, use_container_width=True)
            
            st.subheader("Anomaly Details")
            
            # Filter by severity/type
            anom_types = df_anom['anomaly_type'].unique().tolist()
            selected_anom_types = st.multiselect(
                "Filter by Anomaly Type",
                anom_types,
                default=anom_types
            )
            
            df_filtered_anom = df_anom[df_anom['anomaly_type'].isin(selected_anom_types)]
            
            for idx, row in df_filtered_anom.iterrows():
                severity = "🔴 CRITICAL" if row['anomaly_type'] in ['ML_ANOMALY', 'OUT_OF_RANGE_HR', 'OUT_OF_RANGE_TEMP'] else "🟠 WARNING"
                st.markdown(f"""
                    **{severity}** | {row['anomaly_type']} | {row['device_id']}
                    
                    📅 **Timestamp:** {row['timestamp']}
                    
                    ❤️ HR: {row['heart_rate']} bpm | 🌡️ Temp: {row['body_temp']}°C | 📶 Signal: {row['signal_strength']} dBm | 🔋 Battery: {row['battery_level']}%
                    
                    ---
                """)
        else:
            st.success("✅ No anomalies detected in this time range!")
    
    # Tab 3: Devices
    with tab3:
        st.subheader("📱 Connected Devices")
        df_devices = get_devices_status()
        
        if not df_devices.empty:
            # Device status cards
            for idx, device in df_devices.iterrows():
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    st.metric("Device ID", device['device_id'], delta=None)
                with col2:
                    st.metric("Status", device['status'], delta=None)
                with col3:
                    st.metric("Total Readings", device['total_readings'], delta=None)
                with col4:
                    st.metric("Last Seen", device['last_seen'][-8:], delta=None)
                
                st.divider()
        else:
            st.info("No devices registered yet.")
    
    # Tab 4: Statistics
    with tab4:
        st.subheader("📊 Anomaly Statistics")
        df_stats = get_anomaly_stats()
        
        if not df_stats.empty:
            st.dataframe(df_stats, use_container_width=True)
            
            # Charts
            fig_stats = px.pie(
                df_stats,
                values='count',
                names='anomaly_type',
                title='Distribution of Anomaly Types'
            )
            st.plotly_chart(fig_stats, use_container_width=True)
        else:
            st.info("No anomaly statistics available yet.")
    
    # Tab 5: Logs
    with tab5:
        st.subheader("📝 Complete Logs")
        df_logs = get_all_readings(hours_filter)
        
        if not df_logs.empty:
            # Download button
            csv = df_logs.to_csv(index=False)
            st.download_button(
                label="📥 Download as CSV",
                data=csv,
                file_name=f"iot_telemetry_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv"
            )
            
            st.dataframe(
                df_logs.sort_values('timestamp', ascending=False),
                use_container_width=True,
                height=600
            )
        else:
            st.info("No logs available.")
    
    # Auto-refresh
    st.sidebar.markdown("---")
    if st.sidebar.checkbox("🔄 Auto-refresh", value=False):
        st.rerun()
    
    # Footer
    st.sidebar.markdown("---")
    st.sidebar.markdown("""
        **Healthcare IoT Monitoring System**
        
        - 🏥 Real-time medical device monitoring
        - 🧠 ML-based anomaly detection
        - 📊 Historical analytics
        - 🚨 Alert system
    """)

if __name__ == '__main__':
    main()
