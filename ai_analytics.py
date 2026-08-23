import pandas as pd
import numpy as np
import warnings
from datetime import datetime
from db_manager import get_connection

warnings.filterwarnings('ignore', category=UserWarning)

def get_hourly_occupancy():
    """تحلیل و استخراج میزان شلوغی باشگاه بر اساس ساعات شبانه‌روز"""
    conn = get_connection()
    query = """
        SELECT checkin_time AS checkin_datetime
        FROM CheckIns
    """
    df = pd.read_sql(query, conn)
    conn.close()
    
    if df.empty:
        return pd.DataFrame({'hour': list(range(8, 24)), 'checkin_count': [0]*16})
    
    df['checkin_datetime'] = pd.to_datetime(df['checkin_datetime'])
    df['hour'] = df['checkin_datetime'].dt.hour
    
    hourly_counts = df.groupby('hour').size().reset_index(name='checkin_count')
    
    all_hours = pd.DataFrame({'hour': list(range(8, 24))})
    result = pd.merge(all_hours, hourly_counts, on='hour', how='left').fillna(0)
    result['checkin_count'] = result['checkin_count'].astype(int)
    
    return result

def predict_churn_risk():
    """
    تحلیل ریسک ریزش اعضا با محاسبه یک امتیاز عددی (0 تا 100)
    و ذخیره آن در جدول AI_Analytics جهت هماهنگی کامل با دیتابیس
    """
    conn = get_connection()
    
    # 1. استخراج داده‌های مورد نیاز
    query = """
        SELECT 
            m.member_id,
            m.full_name,
            m.phone_number,
            s.subscription_id,
            s.remaining_sessions,
            s.end_date,
            MAX(c.checkin_time) as last_checkin
        FROM Members m
        JOIN Subscriptions s ON m.member_id = s.member_id
        LEFT JOIN CheckIns c ON s.subscription_id = c.subscription_id
        WHERE s.status = 'ACTIVE'
        GROUP BY m.member_id, m.full_name, m.phone_number, s.subscription_id, s.remaining_sessions, s.end_date
    """
    df = pd.read_sql(query, conn)
    
    if df.empty:
        conn.close()
        return pd.DataFrame()
    
    now = datetime.now()
    df['last_checkin'] = pd.to_datetime(df['last_checkin'])
    
    # محاسبه روزهای غیبت
    def calc_days(x):
        if pd.notnull(x):
            diff = (now - x).days
            return max(0, diff)
        return 30 # اگر اصلا ترددی نداشته، 30 روز در نظر گرفته می‌شود

    df['days_since_last_checkin'] = df['last_checkin'].apply(calc_days)
    
    # 2. محاسبه امتیاز هوشمند ریسک (Risk Score از 0 تا 100)
    def calculate_risk_score(row):
        days = row['days_since_last_checkin']
        sessions = row['remaining_sessions']
        
        # تاثیر روزهای غیبت (تا سقف 70 امتیاز برای 14 روز غیبت)
        risk_from_days = min(days * 5, 70)
        
        # تاثیر جلسات رو به اتمام (تا سقف 30 امتیاز)
        if sessions == 0:
            risk_from_sessions = 30
        elif sessions <= 3:
            risk_from_sessions = 15
        else:
            risk_from_sessions = 0
            
        return float(risk_from_days + risk_from_sessions)

    # ایجاد ستون امتیاز برای ثبت در دیتابیس
    df['churn_risk_score'] = df.apply(calculate_risk_score, axis=1)
    
    # 3. تبدیل امتیاز عددی به برچسب‌های متنی برای سازگاری با داشبورد (UI)
    def map_to_label(score):
        if score >= 70:
            return 'بالا (High)'
        elif score >= 40:
            return 'متوسط (Medium)'
        else:
            return 'پایین (Low)'
            
    df['risk_level'] = df['churn_risk_score'].apply(map_to_label)
    
    # 4. همگام‌سازی و ذخیره نتایج در جدول AI_Analytics دیتابیس
    cursor = conn.cursor()
    for _, row in df.iterrows():
        member_id = int(row['member_id'])
        score = float(row['churn_risk_score'])
        
        # بررسی اینکه آیا کاربر از قبل در جدول آنالیز وجود دارد یا خیر
        cursor.execute("SELECT analytics_id FROM AI_Analytics WHERE member_id = ?", (member_id,))
        exists = cursor.fetchone()
        
        if exists:
            cursor.execute("""
                UPDATE AI_Analytics 
                SET churn_risk_score = ?, last_calculated = GETDATE()
                WHERE member_id = ?
            """, (score, member_id))
        else:
            cursor.execute("""
                INSERT INTO AI_Analytics (member_id, churn_risk_score, last_calculated)
                VALUES (?, ?, GETDATE())
            """, (member_id, score))
            
    conn.commit()
    conn.close()
    
    return df