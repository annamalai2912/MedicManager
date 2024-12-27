import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import pytz
import json
import os
import base64
from io import BytesIO
import qrcode
import io
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import calendar
from plyer import notification

# Default settings
DEFAULT_SETTINGS = {
    "notification_enabled": True,
    "low_stock_threshold": 10,
    "reminder_advance_minutes": 5,
    "email_settings": {
        "enabled": False,
        "email": "",
        "password": ""
    },
    "reminder_settings": {
        "advance_reminder": 15,
        "remind_until_taken": True
    }
}

# Configuration
TIMEZONE = pytz.timezone('Asia/Kolkata')
DATA_DIR = "data"
DATA_FILE = os.path.join(DATA_DIR, "மருந்துகள்.csv")
HISTORY_FILE = os.path.join(DATA_DIR, "மருந்து_வரலாறு.csv")
REMINDER_LOG_FILE = os.path.join(DATA_DIR, "reminder_log.json")
SETTINGS_FILE = os.path.join(DATA_DIR, "settings.json")
BACKUP_DIR = os.path.join(DATA_DIR, "backups")

# Ensure directories exist
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(BACKUP_DIR, exist_ok=True)

# File Operations
def safe_load_json(file_path, default_value):
    try:
        with open(file_path, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default_value

def safe_save_json(file_path, data):
    try:
        with open(file_path, 'w') as f:
            json.dump(data, f)
        return True
    except Exception as e:
        st.error(f"Error saving file {file_path}: {str(e)}")
        return False

def load_settings():
    settings = safe_load_json(SETTINGS_FILE, DEFAULT_SETTINGS)
    for key, value in DEFAULT_SETTINGS.items():
        if key not in settings:
            settings[key] = value
        elif isinstance(value, dict):
            for sub_key, sub_value in value.items():
                if sub_key not in settings[key]:
                    settings[key][sub_key] = sub_value
    return settings

def save_settings(new_settings):
    current_settings = load_settings()
    current_settings.update(new_settings)
    return safe_save_json(SETTINGS_FILE, current_settings)

def load_data():
    try:
        return pd.read_csv(DATA_FILE)
    except FileNotFoundError:
        return pd.DataFrame(columns=["பெயர்", "அளவு", "நாள் அளவு", "கையிருப்பு", 
                                   "நினைவூட்டல் நேரம்", "தொடக்க தேதி", 
                                   "முடிவு தேதி", "குறிப்புகள்", "முன்னுரிமை", 
                                   "வகை", "விலை"])
    except Exception as e:
        st.error(f"Error loading medication data: {str(e)}")
        return pd.DataFrame()

def load_history():
    try:
        return pd.read_csv(HISTORY_FILE)
    except FileNotFoundError:
        return pd.DataFrame(columns=["தேதி", "மருந்து", "செயல்", "விவரங்கள்"])
    except Exception as e:
        st.error(f"Error loading history data: {str(e)}")
        return pd.DataFrame()

def safe_save_data(df, file_path):
    try:
        df.to_csv(file_path, index=False)
        return True
    except Exception as e:
        st.error(f"Error saving data to {file_path}: {str(e)}")
        return False

def save_data(df):
    return safe_save_data(df, DATA_FILE)

def save_history(df):
    return safe_save_data(df, HISTORY_FILE)

def get_stock_status(stock, times_per_day, cost=0):
    settings = load_settings()
    try:
        stock = float(stock)
        times_per_day = float(times_per_day)
        cost = float(cost)
        
        days_remaining = stock / times_per_day if times_per_day > 0 else 0
        monthly_cost = cost * times_per_day * 30
        
        status_info = {
            "days_remaining": days_remaining,
            "monthly_cost": monthly_cost,
            "status": "✅",
            "message": f"{days_remaining:.0f} நாட்கள் உள்ளன"
        }
        
        threshold = settings.get("low_stock_threshold", DEFAULT_SETTINGS["low_stock_threshold"])
        
        if days_remaining <= threshold:
            status_info["status"] = "❌"
            status_info["message"] = f"வெறும் {days_remaining:.0f} நாட்கள்! உடனே வாங்கவும்!"
        elif days_remaining <= 30:
            status_info["status"] = "⚠️"
            status_info["message"] = f"{days_remaining:.0f} நாட்கள் மட்டுமே உள்ளன"
        
        return status_info
    except (ValueError, TypeError, ZeroDivisionError) as e:
        return {
            "days_remaining": 0,
            "monthly_cost": 0,
            "status": "❌",
            "message": "தரவு பிழை"
        }

def check_and_notify_reminders():
    if not load_settings()["notification_enabled"]:
        return
        
    med_data = load_data()
    reminder_log = safe_load_json(REMINDER_LOG_FILE, {})
    current_time = datetime.now(TIMEZONE)
    
    for _, med in med_data.iterrows():
        if pd.isna(med["நினைவூட்டல் நேரம்"]):
            continue
            
        reminder_times = med["நினைவூட்டல் நேரம்"].split(", ")
        for time_str in reminder_times:
            try:
                reminder_time = datetime.strptime(f"{current_time.date()} {time_str}", 
                                                "%Y-%m-%d %H:%M")
                reminder_time = TIMEZONE.localize(reminder_time)
                
                reminder_key = f"{med['பெயர்']}_{current_time.date()}_{time_str}"
                time_diff = abs((current_time - reminder_time).total_seconds() / 60)
                
                if (time_diff <= load_settings()["reminder_advance_minutes"] and 
                    reminder_key not in reminder_log):
                    notification.notify(
                        title=f"மருந்து நினைவூட்டல் - {med['பெயர்']}",
                        message=f"மருந்து எடுக்க நேரம்!\nஅளவு: {med['அளவு']}",
                        app_icon=None,
                        timeout=10,
                    )
                    
                    reminder_log[reminder_key] = {
                        "timestamp": current_time.strftime("%Y-%m-%d %H:%M:%S"),
                        "status": "notified"
                    }
                    safe_save_json(REMINDER_LOG_FILE, reminder_log)
                    
                    history_df = load_history()
                    new_history = pd.DataFrame([{
                        "தேதி": current_time.strftime("%Y-%m-%d %H:%M:%S"),
                        "மருந்து": med["பெயர்"],
                        "செயல்": "நினைவூட்டல்",
                        "விவரங்கள்": f"நேரம்: {time_str}"
                    }])
                    history_df = pd.concat([history_df, new_history], ignore_index=True)
                    save_history(history_df)
            except Exception as e:
                st.error(f"Reminder error for {med['பெயர்']}: {str(e)}")

def create_backup():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_folder = os.path.join(BACKUP_DIR, timestamp)
    os.makedirs(backup_folder, exist_ok=True)
    
    for file in [DATA_FILE, HISTORY_FILE, REMINDER_LOG_FILE, SETTINGS_FILE]:
        if os.path.exists(file):
            backup_file = os.path.join(backup_folder, os.path.basename(file))
            with open(file, 'rb') as f_src, open(backup_file, 'wb') as f_dst:
                f_dst.write(f_src.read())
    return backup_folder

def generate_qr_code(med_data):
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(str(med_data))
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format='PNG')
    return img_byte_arr.getvalue()

def send_email_report(email_settings, report_type, data):
    if not email_settings.get("enabled", False):
        return False
        
    msg = MIMEMultipart()
    msg['From'] = email_settings['email']
    msg['To'] = email_settings['email']
    msg['Subject'] = f"மருந்து அறிக்கை - {report_type}"
    msg.attach(MIMEText(str(data), 'plain'))
    
    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(email_settings['email'], email_settings['password'])
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        st.error(f"Email error: {str(e)}")
        return False

def main():
    st.set_page_config(page_title="மருந்து கண்காணிப்பு செயலி", page_icon="💊", layout="wide")
    
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    
    st.sidebar.title("💊 மருந்து கண்காணிப்பு")
    
    pages = {
        "🏠 முகப்பு": render_dashboard,
        "➕ புதிய மருந்து": render_add_medication,
        "📦 கையிருப்பு": render_stock_management,
        "📝 வரலாறு": render_medication_history,
        "📈 புள்ளிவிவரங்கள்": render_analytics,
        "⚙️ அமைப்புகள்": render_settings
    }
    
    selection = st.sidebar.radio("மெனு", list(pages.keys()))
    
    if st.sidebar.button("வெளியேறு"):
        st.session_state.authenticated = False
        st.experimental_rerun()
    
    st.sidebar.markdown("---")
    st.sidebar.markdown("v1.0.0")
    
    try:
        pages[selection]()
    except Exception as e:
        st.error(f"Error in {selection}: {str(e)}")
    
    st.markdown("---")
    st.markdown(
        """
        <div style='text-align: center'>
            💊 மருந்து கண்காணிப்பு செயலி © 2024
        </div>
        """,
        unsafe_allow_html=True
    )

# Page rendering functions
def render_dashboard():
    st.header("📊 டாஷ்போர்டு")
    med_data = load_data()
    
    if med_data.empty:
        st.info("மருந்துகளை சேர்க்கவும்")
        return
    
    try:
        # Data preprocessing
        if 'விலை' not in med_data.columns:
            med_data['விலை'] = 0.0
        if 'காலாவதி தேதி' not in med_data.columns:
            med_data['காலாவதி தேதி'] = None
        if 'வகை' not in med_data.columns:
            med_data['வகை'] = 'பொது'
            
        med_data['விலை'] = med_data['விலை'].fillna(0).astype(float)
        
        # Main metrics
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("மொத்த மருந்துகள்", len(med_data))
        with col2:
            st.metric("மொத்த கையிருப்பு", med_data["கையிருப்பு"].sum())
        with col3:
            low_stock = len(med_data[med_data.apply(
                lambda x: get_stock_status(x["கையிருப்பு"], 
                                         x["நாள் அளவு"])["status"] == "❌", axis=1)])
            st.metric("குறைந்த கையிருப்பு", f"{low_stock} மருந்துகள்")
        with col4:
            total_value = (med_data['விலை'] * med_data['கையிருப்பு']).sum()
            st.metric("மொத்த மதிப்பு", f"₹{total_value:,.2f}")
            
        st.subheader("📋 மருந்துகள் மற்றும் விவரங்கள்")
        if not med_data.empty:
            st.dataframe(med_data)

        # Expiry Alerts
        st.subheader("⚠️ காலாவதி எச்சரிக்கைகள்")
        if 'காலாவதி தேதி' in med_data.columns:
            today = pd.Timestamp.now()
            expiring_soon = med_data[pd.to_datetime(med_data['காலாவதி தேதி']) - today <= pd.Timedelta(days=30)]
            if not expiring_soon.empty:
                st.warning(f"{len(expiring_soon)} மருந்துகள் அடுத்த 30 நாட்களில் காலாவதியாகின்றன")
                st.dataframe(expiring_soon[['பெயர்', 'காலாவதி தேதி', 'கையிருப்பு']])

        # Category Analysis
        st.subheader("📊 வகை வாரியான பகுப்பாய்வு")
        if 'வகை' in med_data.columns:
            cat_data = med_data.groupby('வகை').agg({
                'பெயர்': 'count',
                'கையிருப்பு': 'sum',
                'விலை': lambda x: (x * med_data.loc[x.index, 'கையிருப்பு']).sum()
            }).reset_index()
            cat_data.columns = ['வகை', 'மருந்துகள்', 'மொத்த கையிருப்பு', 'மொத்த மதிப்பு']
            st.dataframe(cat_data)

        # Stock Level Visualization
        st.subheader("📈 கையிருப்பு நிலை")
        stock_fig = px.bar(med_data.nlargest(10, 'கையிருப்பு'),
                          x='பெயர்', y='கையிருப்பு',
                          title='அதிக கையிருப்பு உள்ள 10 மருந்துகள்')
        st.plotly_chart(stock_fig)

        # Value Analysis
        st.subheader("💰 மதிப்பு பகுப்பாய்வு")
        med_data['மொத்த மதிப்பு'] = med_data['விலை'] * med_data['கையிருப்பு']
        value_fig = px.pie(med_data.nlargest(5, 'மொத்த மதிப்பு'),
                          values='மொத்த மதிப்பு',
                          names='பெயர்',
                          title='அதிக மதிப்புள்ள 5 மருந்துகள்')
        st.plotly_chart(value_fig)

    except Exception as e:
        st.error(f"டாஷ்போர்டு பிழை: {str(e)}")
def render_add_medication():
    st.header("➕ புதிய மருந்து சேர்க்க மற்றும் நிர்வகி")
    
    # Add Medication Form
    with st.form("add_med_form"):
        st.subheader("மருந்து சேர்க்கவும்")
        col1, col2 = st.columns(2)
        with col1:
            name = st.text_input("மருந்தின் பெயர்")
            dosage = st.text_input("அளவு")
            category = st.selectbox("வகை", ["மாத்திரைகள்", "திரவம்", "ஊசி", "மற்றவை"])
            priority = st.selectbox("முன்னுரிமை", ["உயர்", "நடுத்தரம்", "குறைந்த"])
            price = st.number_input("விலை", min_value=0.0, step=0.01)
        with col2:
            times_per_day = st.number_input("நாள் அளவு", min_value=1)
            stock = st.number_input("கையிருப்பு", min_value=0)
            start_date = st.date_input("தொடக்க தேதி")
            end_date = st.date_input("முடிவு தேதி")
            reminder_times = st.multiselect(
                "நினைவூட்டல் நேரம்",
                ["06:00", "07:00", "08:00", "09:00", "12:00", "13:00", 
                 "14:00", "15:00", "18:00", "19:00", "20:00", "21:00", "22:00"],
                default=[]
            )
        
        notes = st.text_area("குறிப்புகள்")
        submitted = st.form_submit_button("சேமி")
        
        if submitted and name and dosage:
            try:
                med_data = load_data()
                new_med = {
                    "பெயர்": name,
                    "அளவு": dosage,
                    "நாள் அளவு": times_per_day,
                    "கையிருப்பு": stock,
                    "நினைவூட்டல் நேரம்": ", ".join(reminder_times),
                    "தொடக்க தேதி": start_date.strftime("%Y-%m-%d"),
                    "முடிவு தேதி": end_date.strftime("%Y-%m-%d"),
                    "குறிப்புகள்": notes,
                    "முன்னுரிமை": priority,
                    "வகை": category,
                    "விலை": price
                }
                med_data = pd.concat([med_data, pd.DataFrame([new_med])], ignore_index=True)
                if save_data(med_data):
                    st.success("மருந்து சேர்க்கப்பட்டது!")
                    
                    # Add to history
                    history_df = load_history()
                    new_history = pd.DataFrame([{
                        "தேதி": datetime.now(TIMEZONE).strftime("%Y-%m-%d %H:%M:%S"),
                        "மருந்து": name,
                        "செயல்": "சேர்க்கப்பட்டது",
                        "விவரங்கள்": f"அளவு: {dosage}, கையிருப்பு: {stock}"
                    }])
                    history_df = pd.concat([history_df, new_history], ignore_index=True)
                    save_history(history_df)
            except Exception as e:
                st.error(f"பிழை ஏற்பட்டது: {str(e)}")
                history_df = load_history()
                new_history = pd.DataFrame([{
                    "தேதி": datetime.now(TIMEZONE).strftime("%Y-%m-%d %H:%M:%S"),
                    "மருந்து": name,
                    "செயல்": "பிழை",
                    "விவரங்கள்": str(e)
                }])
                history_df = pd.concat([history_df, new_history], ignore_index=True)
                save_history(history_df)

    # View Medications
    st.subheader("📋 மருந்துகள் பட்டியல்")
    try:
        med_data = load_data()
        if not med_data.empty:
            for index, row in med_data.iterrows():
                with st.expander(f"{row['பெயர்']} - {row['வகை']}"):
                    st.write(f"**அளவு:** {row['அளவு']}")
                    st.write(f"**கையிருப்பு:** {row['கையிருப்பு']}")
                    st.write(f"**நினைவூட்டல் நேரம்:** {row['நினைவூட்டல் நேரம்']}")
                    st.write(f"**முன்னுரிமை:** {row['முன்னுரிமை']}")
                    st.write(f"**விலை:** ₹{row['விலை']}")
                    st.write(f"**தொடக்க தேதி:** {row['தொடக்க தேதி']}")
                    st.write(f"**முடிவு தேதி:** {row['முடிவு தேதி']}")
                    st.write(f"**குறிப்புகள்:** {row['குறிப்புகள்']}")

                    # Update Medication
                    if st.button(f"புதுப்பிக்க {row['பெயர்']}", key=f"update_{index}"):
                        st.warning("புதுப்பிப்பு அம்சம் விரைவில்!")
                    
                    # Delete Medication
                    if st.button(f"அழிக்க {row['பெயர்']}", key=f"delete_{index}"):
                        med_data = med_data.drop(index)
                        save_data(med_data)
                        st.success(f"'{row['பெயர்']}' நீக்கப்பட்டது!")
        else:
            st.info("மருந்துகள் இல்லை!")
    except Exception as e:
        st.error(f"பிழை ஏற்பட்டது: {str(e)}")

                    
def check_and_notify_reminders():
    if not load_settings()["notification_enabled"]:
        return
        
    med_data = load_data()
    reminder_log = safe_load_json(REMINDER_LOG_FILE, {})
    current_time = datetime.now(TIMEZONE)
    
    for _, med in med_data.iterrows():
        if pd.isna(med["நினைவூட்டல் நேரம்"]) or not med["நினைவூட்டல் நேரம்"]:
            continue
            
        reminder_times = med["நினைவூட்டல் நேரம்"].split(", ")
        for time_str in reminder_times:
            try:
                reminder_time = datetime.strptime(f"{current_time.date()} {time_str}", 
                                                "%Y-%m-%d %H:%M")
                reminder_time = TIMEZONE.localize(reminder_time)
                
                reminder_key = f"{med['பெயர்']}_{current_time.date()}_{time_str}"
                time_diff = abs((current_time - reminder_time).total_seconds() / 60)
                
                if (time_diff <= load_settings()["reminder_advance_minutes"] and 
                    reminder_key not in reminder_log):
                    notification.notify(
                        title=f"மருந்து நினைவூட்டல் - {med['பெயர்']}",
                        message=f"மருந்து எடுக்க நேரம்!\nஅளவு: {med['அளவு']}\nநேரம்: {time_str}",
                        app_icon=None,
                        timeout=10,
                    )
                    
                    # Play alarm sound
                    try:
                        import winsound
                        winsound.Beep(1000, 1000)  # frequency=1000Hz, duration=1000ms
                    except:
                        pass
                    
                    reminder_log[reminder_key] = {
                        "timestamp": current_time.strftime("%Y-%m-%d %H:%M:%S"),
                        "status": "notified"
                    }
                    safe_save_json(REMINDER_LOG_FILE, reminder_log)
            except Exception as e:
                st.error(f"Reminder error for {med['பெயர்']}: {str(e)}")

def render_stock_management():
    st.header("📦 கையிருப்பு மேலாண்மை")
    med_data = load_data()
    
    if med_data.empty:
        st.info("மருந்துகள் இல்லை")
        return
    
    for _, med in med_data.iterrows():
        with st.expander(f"{med['பெயர்']} - கையிருப்பு: {med['கையிருப்பு']}"):
            col1, col2 = st.columns(2)
            with col1:
                new_stock = st.number_input(
                    "புதிய கையிருப்பு",
                    min_value=0,
                    value=int(med['கையிருப்பு']),
                    key=f"stock_{med['பெயர்']}"
                )
            with col2:
                action = st.selectbox(
                    "செயல்",
                    ["புதுப்பி", "கழி", "சேர்"],
                    key=f"action_{med['பெயர்']}"
                )
            
            if st.button("சேமி", key=f"save_{med['பெயர்']}"):
                try:
                    old_stock = med['கையிருப்பு']
                    med_data.loc[med_data['பெயர்'] == med['பெயர்'], 'கையிருப்பு'] = new_stock
                    
                    if save_data(med_data):
                        st.success("கையிருப்பு புதுப்பிக்கப்பட்டது!")
                        
                        history_df = load_history()
                        new_history = pd.DataFrame([{
                            "தேதி": datetime.now(TIMEZONE).strftime("%Y-%m-%d %H:%M:%S"),
                            "மருந்து": med['பெயர்'],
                            "செயல்": action,
                            "விவரங்கள்": f"பழைய: {old_stock}, புதிய: {new_stock}"
                        }])
                        history_df = pd.concat([history_df, new_history], ignore_index=True)
                        save_history(history_df)
                except Exception as e:
                    st.error(f"பிழை: {str(e)}")

def render_medication_history():
    st.header("📝 மருந்து வரலாறு")
    history_df = load_history()
    
    if history_df.empty:
        st.info("வரலாறு இல்லை")
        return
    
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("தொடக்க தேதி", 
                                  value=datetime.now().date() - timedelta(days=7))
    with col2:
        end_date = st.date_input("முடிவு தேதி", 
                                value=datetime.now().date())
    
    filtered_history = history_df[
        (pd.to_datetime(history_df['தேதி']).dt.date >= start_date) &
        (pd.to_datetime(history_df['தேதி']).dt.date <= end_date)
    ]
    
    st.dataframe(filtered_history.sort_values('தேதி', ascending=False))

def render_analytics():
    st.header("📈 புள்ளிவிவரங்கள்")
    med_data = load_data()
    history_df = load_history()
    
    if med_data.empty or history_df.empty:
        st.info("போதுமான தரவு இல்லை")
        return
    
    # Stock levels visualization
    st.subheader("கையிருப்பு நிலை")
    fig = px.bar(med_data, x="பெயர்", y="கையிருப்பு", 
                 color="முன்னுரிமை", title="மருந்து கையிருப்பு")
    st.plotly_chart(fig)
    
    # Usage trends
    st.subheader("பயன்பாட்டு போக்குகள்")
    usage_data = history_df[history_df['செயல்'] == 'கழி'].groupby(
        pd.to_datetime(history_df['தேதி']).dt.date
    ).size().reset_index()
    usage_data.columns = ['தேதி', 'எண்ணிக்கை']
    
    fig = px.line(usage_data, x='தேதி', y='எண்ணிக்கை', 
                  title="தினசரி மருந்து பயன்பாடு")
    st.plotly_chart(fig)

def render_settings():
    st.header("⚙️ அமைப்புகள்")
    settings = load_settings()
    
    with st.form("settings_form"):
        notification_enabled = st.checkbox("நினைவூட்டல்கள்", 
                                         value=settings["notification_enabled"])
        low_stock_threshold = st.number_input("குறைந்த கையிருப்பு எல்லை", 
                                            value=settings["low_stock_threshold"])
        reminder_advance = st.number_input("நினைவூட்டல் முன் நேரம் (நிமிடங்கள்)", 
                                         value=settings["reminder_advance_minutes"])
        
        email_settings = settings["email_settings"]
        st.subheader("மின்னஞ்சல் அமைப்புகள்")
        email_enabled = st.checkbox("மின்னஞ்சல் அறிக்கைகள்", 
                                  value=email_settings["enabled"])
        email = st.text_input("மின்னஞ்சல்", value=email_settings["email"])
        password = st.text_input("கடவுச்சொல்", type="password", 
                               value=email_settings["password"])
        
        if st.form_submit_button("சேமி"):
            new_settings = {
                "notification_enabled": notification_enabled,
                "low_stock_threshold": low_stock_threshold,
                "reminder_advance_minutes": reminder_advance,
                "email_settings": {
                    "enabled": email_enabled,
                    "email": email,
                    "password": password
                }
            }
            if save_settings(new_settings):
                st.success("அமைப்புகள் சேமிக்கப்பட்டன!")

if __name__ == "__main__":
    main()