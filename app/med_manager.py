import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
import plotly.express as px
import plotly.graph_objects as go
from PIL import Image
import io
import time

# Tamil font support
plt.rcParams['font.sans-serif'] = ['Arial Unicode MS']

# File paths
DATA_FILE = "data/மருந்துகள்.csv"
HISTORY_FILE = "data/மருந்து_வரலாறு.csv"

# Load or initialize data
def load_data():
    try:
        return pd.read_csv(DATA_FILE)
    except FileNotFoundError:
        return pd.DataFrame(columns=["பெயர்", "அளவு", "நாள் அளவு", "கையிருப்பு", 
                                   "நினைவூட்டல் நேரம்", "தொடக்க தேதி", 
                                   "முடிவு தேதி", "குறிப்புகள்", "முன்னுரிமை", "வகை"])

def load_history():
    try:
        return pd.read_csv(HISTORY_FILE)
    except FileNotFoundError:
        return pd.DataFrame(columns=["தேதி", "மருந்து", "செயல்", "விவரங்கள்"])

def save_data(df):
    df.to_csv(DATA_FILE, index=False)

def save_history(df):
    df.to_csv(HISTORY_FILE, index=False)

# Enhanced stock status
def get_stock_status(stock, times_per_day):
    days_remaining = stock / times_per_day
    if days_remaining > 30:
        return "✅ போதுமானது", f"{days_remaining:.0f} நாட்கள் உள்ளன"
    elif days_remaining > 7:
        return "⚠️ விரைவில் வாங்கவும்", f"{days_remaining:.0f} நாட்கள் மட்டுமே உள்ளன"
    else:
        return "❌ அவசரம்!", f"வெறும் {days_remaining:.0f} நாட்கள் மட்டுமே! உடனே வாங்கவும்!"

# Streamlit configuration
st.set_page_config(page_title="மருந்து மேலாண்மை", layout="wide", page_icon="💊")

# Load data
med_data = load_data()
history_df = load_history()

# Custom header
st.markdown("""
    <style>
    .tamil-font {
        font-size:30px !important;
        color: #1f77b4;
    }
    </style>
    <p class="tamil-font">💊 மேம்பட்ட மருந்து மேலாண்மை அமைப்பு</p>
    """, unsafe_allow_html=True)

# Navigation
st.sidebar.header("பட்டியல்")
page = st.sidebar.radio("பக்கத்தை தேர்வு செய்க", [
    "டாஷ்போர்டு", 
    "மருந்து சேர்க்க", 
    "கையிருப்பு மேலாண்மை",
    "மருந்து வரலாறு",
    "புள்ளிவிவரங்கள்",
    "அறிக்கைகள்",
    "அமைப்புகள்"
])

# Dashboard
if page == "டாஷ்போர்டு":
    st.header("📊 டாஷ்போர்டு")
    
    # Summary metrics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("மொத்த மருந்துகள்", len(med_data))
    with col2:
        st.metric("மொத்த கையிருப்பு", med_data["கையிருப்பு"].sum())
    with col3:
        low_stock = len(med_data[med_data["கையிருப்பு"] <= 10])
        st.metric("குறைந்த கையிருப்பு எச்சரிக்கை", f"{low_stock} மருந்துகள்")
    with col4:
        daily_doses = med_data["நாள் அளவு"].sum()
        st.metric("தினசரி அளவுகள்", daily_doses)

    # Stock visualization
    if not med_data.empty:
        fig = px.bar(med_data, x="பெயர்", y="கையிருப்பு",
                    title="மருந்து கையிருப்பு நிலை",
                    color="கையிருப்பு",
                    color_continuous_scale="RdYlBu")
        st.plotly_chart(fig)

        # Today's schedule
        st.subheader("இன்றைய மருந்து அட்டவணை")
        schedule_data = []
        current_time = datetime.now()
        for _, med in med_data.iterrows():
            times = med["நினைவூட்டல் நேரம்"].split(", ")
            for time in times:
                schedule_time = datetime.strptime(time, "%H:%M")
                schedule_data.append({
                    "மருந்து": med["பெயர்"],
                    "நேரம்": time,
                    "நிலை": "எடுக்கப்பட்டது" if schedule_time.time() < current_time.time() else "நிலுவையில்"
                })
        
        schedule_df = pd.DataFrame(schedule_data)
        if not schedule_df.empty:
            st.table(schedule_df)

# Add Medication
elif page == "மருந்து சேர்க்க":
    st.header("➕ புதிய மருந்து சேர்க்க")
    with st.form("add_med_form"):
        col1, col2 = st.columns(2)
        with col1:
            name = st.text_input("மருந்தின் பெயர்")
            dosage = st.text_input("அளவு (உ.தா: 1 மாத்திரை, 5மிலி)")
            category = st.selectbox("வகை", ["மாத்திரைகள்", "திரவம்", "ஊசி", "மற்றவை"])
            priority = st.selectbox("முன்னுரிமை", ["உயர்", "நடுத்தரம்", "குறைந்த"])
        
        with col2:
            times_per_day = st.number_input("ஒரு நாளைக்கு எத்தனை முறை", min_value=1, step=1)
            stock = st.number_input("ஆரம்ப கையிருப்பு", min_value=0, step=1)
            start_date = st.date_input("தொடக்க தேதி")
            end_date = st.date_input("முடிவு தேதி (விருப்பம்)")

        st.subheader("நினைவூட்டல் நேரங்கள்")
        reminder_times = []
        cols = st.columns(times_per_day)
        for i, col in enumerate(cols):
            with col:
                time = st.time_input(f"நேரம் {i+1}")
                reminder_times.append(time.strftime("%H:%M"))

        notes = st.text_area("குறிப்புகள் (விருப்பம்)")
        
        submitted = st.form_submit_button("மருந்து சேர்க்க")
        if submitted and name and dosage:
            new_entry = {
                "பெயர்": name,
                "அளவு": dosage,
                "நாள் அளவு": times_per_day,
                "கையிருப்பு": stock,
                "நினைவூட்டல் நேரம்": ", ".join(reminder_times),
                "தொடக்க தேதி": start_date.strftime("%Y-%m-%d"),
                "முடிவு தேதி": end_date.strftime("%Y-%m-%d"),
                "குறிப்புகள்": notes,
                "முன்னுரிமை": priority,
                "வகை": category
            }
            new_entry_df = pd.DataFrame([new_entry])
            med_data = pd.concat([med_data, new_entry_df], ignore_index=True)
            save_data(med_data)
            
            # Log action
            history_df = pd.concat([history_df, pd.DataFrame([{
                "தேதி": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "மருந்து": name,
                "செயல்": "சேர்க்கப்பட்டது",
                "விவரங்கள்": f"ஆரம்ப கையிருப்பு: {stock}"
            }])], ignore_index=True)
            save_history(history_df)
            
            st.success(f"{name} வெற்றிகரமாக சேர்க்கப்பட்டது!")

# Stock Management
elif page == "கையிருப்பு மேலாண்மை":
    st.header("📦 கையிருப்பு மேலாண்மை")
    
    if not med_data.empty:
        # Display stock management table
        med_data["Stock_Status"], med_data["Days_Remaining"] = zip(*med_data.apply(
            lambda row: get_stock_status(row["கையிருப்பு"], row["நாள் அளவு"]), axis=1))
        
        # Allow user to update stock
        st.subheader("கையிருப்பு புதுப்பிக்க")
        stock_updates = []
        for i, med in med_data.iterrows():
            new_stock = st.number_input(f"{med['பெயர்']} - கையிருப்பு", 
                                       value=med["கையிருப்பு"], key=f"stock_{i}")
            stock_updates.append(new_stock)
        
        if st.button("கையிருப்பு சேமிக்க"):
            med_data["கையிருப்பு"] = stock_updates
            save_data(med_data)
            st.success("கையிருப்பு வெற்றிகரமாக புதுப்பிக்கப்பட்டது!")
        
        # Display updated stock data
        st.table(med_data[["பெயர்", "கையிருப்பு", "Stock_Status", "Days_Remaining"]])
    else:
        st.warning("இருந்துவரை எந்த மருந்துகளும் இல்லை!")

# Medication History
elif page == "மருந்து வரலாறு":
    st.header("📝 மருந்து வரலாறு")
    
    if not history_df.empty:
        st.table(history_df)
    else:
        st.warning("இருந்துவரை எந்த வரலாற்றும் இல்லை.")

# Analytics
elif page == "புள்ளிவிவரங்கள்":
    st.header("📈 மருந்து புள்ளிவிவரங்கள்")
    
    if not med_data.empty:
        # Category distribution
        fig1 = px.pie(med_data, names="வகை", title="மருந்து வகைகளின் விநியோகம்")
        st.plotly_chart(fig1)
        
        # Stock trends
        fig2 = px.line(med_data, x="பெயர்", y="கையிருப்பு", 
                      title="மருந்து கையிருப்பு போக்குகள்")
        st.plotly_chart(fig2)

# Reports
elif page == "அறிக்கைகள்":
    st.header("📑 அறிக்கைகள்")
    
    st.subheader("⏰ நினைவூட்டல் அட்டவணை அறிக்கை")
    if not med_data.empty:
            # Prepare reminder schedule data
            reminder_data = []
            for _, med in med_data.iterrows():
                times = med["நினைவூட்டல் நேரம்"].split(", ")
                for time in times:
                    reminder_data.append({
                        "மருந்து": med["பெயர்"],
                        "நினைவூட்டல் நேரம்": time
                    })
            
            reminder_df = pd.DataFrame(reminder_data)
            st.table(reminder_df)

            # Download link for Reminder Report
            reminder_csv = reminder_df.to_csv(index=False)
            reminder_csv = reminder_csv.encode('utf-8')
            st.download_button(
                label="நினைவூட்டல் அட்டவணை அறிக்கையை பதிவிறக்கவும்",
                data=reminder_csv,
                file_name="நினைவூட்டல்_அட்டவணை.csv",
                mime="text/csv"
            )

# Settings
elif page == "அமைப்புகள்":
    st.header("⚙️ அமைப்புகள்")
    
    st.subheader("அறிவிப்பு அமைப்புகள்")
    notification_method = st.multiselect(
        "அறிவிப்பு முறைகளை தேர்வு செய்க",
        ["மின்னஞ்சல்", "குறுஞ்செய்தி", "புஷ் அறிவிப்பு", "ஒலி எச்சரிக்கை"]
    )
    
    st.subheader("காட்சி அமைப்புகள்")
    dark_mode = st.toggle("இருண்ட பயன்முறை")
    language = st.selectbox("மொழி", ["தமிழ்", "ஆங்கிலம்"])
    
    if st.button("அமைப்புகளை சேமிக்க"):
        st.success("அமைப்புகள் வெற்றிகரமாக சேமிக்கப்பட்டன!")

# Footer
st.markdown("---")
st.markdown("💊 மேம்பட்ட மருந்து மேலாண்மை அமைப்பு - ஆரோக்கியமாக வாழுங்கள்!")
