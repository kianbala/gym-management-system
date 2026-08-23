import pyodbc
import pandas as pd
import sys
from datetime import datetime, date

if sys.stdout.encoding.lower() != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except AttributeError:
        pass

SERVER_NAME = r'(local)\SQLSERVER2022'
DATABASE_NAME = 'GymManagementDB'
USERNAME = 'sa'
PASSWORD = 'kian123456'

CONN_STR = (
    f"DRIVER={{SQL Server}};"
    f"SERVER={SERVER_NAME};"
    f"DATABASE={DATABASE_NAME};"
    f"UID={USERNAME};"
    f"PWD={PASSWORD};"
)

def get_connection():
    return pyodbc.connect(CONN_STR)

# --- ۱. تابع جستجوی اعضای دارای اشتراک فعال جهت ثبت ورود ---
def search_members_for_checkin(search_term=""):
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        UPDATE Subscriptions 
        SET status = 'EXPIRED' 
        WHERE end_date < GETDATE() AND status = 'ACTIVE'
    """)
    conn.commit()
    
    query = """
        SELECT 
            m.member_id,
            s.subscription_id, 
            m.full_name, 
            m.phone_number, 
            m.national_id, 
            s.remaining_sessions, 
            s.end_date
        FROM Subscriptions s
        JOIN Members m ON s.member_id = m.member_id
        WHERE s.status = 'ACTIVE' AND s.remaining_sessions > 0
    """
    
    if search_term and search_term.strip():
        query += " AND (m.full_name LIKE ? OR m.phone_number LIKE ? OR m.national_id LIKE ?)"
        term = f"%{search_term.strip()}%"
        cursor.execute(query, (term, term, term))
    else:
        cursor.execute(query)
        
    rows = cursor.fetchall()
    conn.close()
    
    result = []
    for r in rows:
        result.append({
            'member_id': r[0],
            'subscription_id': r[1],
            'full_name': r[2],
            'phone_number': r[3],
            'national_id': r[4],
            'remaining_sessions': r[5],
            'end_date': r[6]
        })
    return result

# --- ۲. تابع افزودن عضو جدید (اصلاح‌شده برای تفکیک نام) ---
def add_member(first_name, last_name, national_id, phone_number):
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT national_id, phone_number 
        FROM Members 
        WHERE national_id = ? OR phone_number = ?
    """, (national_id, phone_number))
    
    existing_member = cursor.fetchone()
    
    if existing_member:
        conn.close()
        if existing_member[0] == national_id:
            return False, "خطا: عضوی با این کد ملی قبلاً ثبت شده است!"
        else:
            return False, "خطا: عضوی با این شماره تماس قبلاً ثبت شده است!"
            
    try:
        cursor.execute(
            "INSERT INTO Members (first_name, last_name, national_id, phone_number) VALUES (?, ?, ?, ?)", 
            (first_name, last_name, national_id, phone_number)
        )
        conn.commit()
        conn.close()
        return True, f"عضو جدید '{first_name} {last_name}' با موفقیت ثبت شد."
    except Exception as e:
        conn.close()
        return False, f"خطا در ثبت عضو: {e}"

# --- ۳. تابع حذف عضو ---
def delete_member(member_id):
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT member_id FROM Members WHERE member_id = ?", (member_id,))
    if not cursor.fetchone():
        conn.close()
        return False, f"خطا: عضوی با کد عضویت {member_id} یافت نشد!"

    try:
        cursor.execute("SELECT subscription_id FROM Subscriptions WHERE member_id = ?", (member_id,))
        subs = cursor.fetchall()
        sub_ids = [s[0] for s in subs]
        
        for s_id in sub_ids:
            cursor.execute("DELETE FROM CheckIns WHERE subscription_id = ?", (s_id,))
            
        cursor.execute("DELETE FROM AI_Analytics WHERE member_id = ?", (member_id,))
        cursor.execute("DELETE FROM Subscriptions WHERE member_id = ?", (member_id,))
        cursor.execute("DELETE FROM Members WHERE member_id = ?", (member_id,))
        
        conn.commit()
        conn.close()
        return True, f"عضو شماره {member_id} و تمامی سوابق مربوطه با موفقیت حذف شدند."
    except Exception as e:
        conn.close()
        return False, f"خطا در حذف عضو: {e}"

# --- ۴. تابع اختصاص بسته ---
def assign_package(member_id, package_id):
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT member_id FROM Members WHERE member_id = ?", (member_id,))
    if not cursor.fetchone():
        conn.close()
        return False, f"خطا: عضوی با کد {member_id} وجود ندارد!"

    cursor.execute("""
        SELECT TOP 1 subscription_id, remaining_sessions, end_date 
        FROM Subscriptions 
        WHERE member_id = ? AND status = 'ACTIVE'
        ORDER BY subscription_id DESC
    """, (member_id,))
    active_sub = cursor.fetchone()
    
    today = date.today()
    
    if active_sub:
        sub_id, remaining_sessions, end_date = active_sub
        
        if isinstance(end_date, str):
            try:
                end_date = datetime.strptime(end_date, "%Y-%m-%d").date()
            except ValueError:
                end_date = datetime.strptime(end_date, "%Y-%m-%d %H:%M:%S").date()
        elif isinstance(end_date, datetime):
            end_date = end_date.date()
            
        if remaining_sessions > 0 and (end_date and end_date >= today):
            conn.close()
            return False, f"این کاربر هنوز {remaining_sessions} جلسه فعال دارد و تاریخ اشتراکش تمام نشده است!"
        else:
            cursor.execute("UPDATE Subscriptions SET status = 'EXPIRED' WHERE member_id = ? AND status = 'ACTIVE'", (member_id,))
    
    cursor.execute("SELECT total_sessions, validity_days FROM Packages WHERE package_id = ?", (package_id,))
    pkg = cursor.fetchone()
    
    if pkg:
        total_sessions, validity_days = pkg
        query = """
            INSERT INTO Subscriptions (member_id, package_id, remaining_sessions, start_date, end_date, status)
            VALUES (?, ?, ?, GETDATE(), DATEADD(day, ?, GETDATE()), N'ACTIVE')
        """
        cursor.execute(query, (member_id, package_id, total_sessions, validity_days))
        conn.commit()
        conn.close()
        return True, "اشتراک جدید با موفقیت فعال شد."
    else:
        conn.close()
        return False, "بسته مورد نظر یافت نشد."

# --- ۵. تابع ثبت ورود ---
def record_checkin(member_id):
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        UPDATE Subscriptions 
        SET status = 'EXPIRED' 
        WHERE end_date < GETDATE() AND status = 'ACTIVE'
    """)
    conn.commit()

    cursor.execute("""
        SELECT TOP 1 subscription_id, remaining_sessions 
        FROM Subscriptions 
        WHERE member_id = ? AND status = 'ACTIVE' AND remaining_sessions > 0
        ORDER BY subscription_id DESC
    """, (member_id,))
    
    active_sub = cursor.fetchone()
    
    if not active_sub:
        conn.close()
        return False, "❌ کاربر اشتراک فعال یا جلسه باقی‌مانده ندارد!"
    
    sub_id, remaining_sessions = active_sub
    
    cursor.execute("""
        INSERT INTO CheckIns (member_id, subscription_id, checkin_time)
        VALUES (?, ?, GETDATE())
    """, (member_id, sub_id))
    
    new_remaining = remaining_sessions - 1
    
    if new_remaining == 0:
        cursor.execute("""
            UPDATE Subscriptions 
            SET remaining_sessions = ?, status = 'EXPIRED' 
            WHERE subscription_id = ?
        """, (new_remaining, sub_id))
    else:
        cursor.execute("""
            UPDATE Subscriptions 
            SET remaining_sessions = ? 
            WHERE subscription_id = ?
        """, (new_remaining, sub_id))
        
    conn.commit()
    conn.close()
    
    return True, f"✅ ورود ثبت شد. جلسات باقی‌مانده: {new_remaining} جلسه"

# --- ۶. تابع دریافت لیست اعضا ---
def get_active_members():
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        UPDATE Subscriptions 
        SET status = 'EXPIRED' 
        WHERE end_date < GETDATE() AND status = 'ACTIVE'
    """)
    conn.commit()
    
    query = """
        SELECT m.member_id, m.full_name, m.national_id, m.phone_number, s.subscription_id, s.remaining_sessions, s.end_date, s.status
        FROM Members m
        LEFT JOIN Subscriptions s ON m.member_id = s.member_id
    """
    df = pd.read_sql(query, conn)
    conn.close()
    return df

# --- ۷. تابع حذف اشتراک ---
def delete_subscription(subscription_id):
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT subscription_id FROM Subscriptions WHERE subscription_id = ?", (subscription_id,))
    if not cursor.fetchone():
        conn.close()
        return False, "اشتراک مورد نظر یافت نشد."

    cursor.execute("DELETE FROM CheckIns WHERE subscription_id = ?", (subscription_id,))
    cursor.execute("DELETE FROM Subscriptions WHERE subscription_id = ?", (subscription_id,))
    conn.commit()
    conn.close()
    return True, f"اشتراک شماره {subscription_id} با موفقیت حذف شد."

# --- ۸. تابع دریافت کلیه بسته‌ها ---
def get_all_packages():
    conn = get_connection()
    query = "SELECT * FROM Packages"
    df = pd.read_sql(query, conn)
    conn.close()
    return df

# --- ۹. تابع ریست کامل داده‌ها ---
def reset_all_data():
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("DELETE FROM CheckIns;")
    cursor.execute("DELETE FROM AI_Analytics;")
    cursor.execute("DELETE FROM Subscriptions;")
    cursor.execute("DELETE FROM Members;")
    
    cursor.execute("DBCC CHECKIDENT ('CheckIns', RESEED, 0);")
    cursor.execute("DBCC CHECKIDENT ('AI_Analytics', RESEED, 0);")
    cursor.execute("DBCC CHECKIDENT ('Subscriptions', RESEED, 0);")
    cursor.execute("DBCC CHECKIDENT ('Members', RESEED, 0);")
    
    conn.commit()
    conn.close()
    return True

# --- ۱۰. تابع جستجوی اعضا جهت تخصیص بسته ---
def search_all_members(search_term=""):
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        UPDATE Subscriptions 
        SET status = 'EXPIRED' 
        WHERE end_date < GETDATE() AND status = 'ACTIVE'
    """)
    conn.commit()
    
    query = """
        SELECT 
            m.member_id, 
            m.full_name, 
            m.phone_number, 
            m.national_id,
            s.remaining_sessions,
            s.end_date,
            s.status
        FROM Members m
        LEFT JOIN (
            SELECT member_id, remaining_sessions, end_date, status,
                   ROW_NUMBER() OVER (PARTITION BY member_id ORDER BY subscription_id DESC) as rn
            FROM Subscriptions
        ) s ON m.member_id = s.member_id AND s.rn = 1
    """
    
    if search_term and search_term.strip():
        query += " WHERE (m.full_name LIKE ? OR m.phone_number LIKE ? OR m.national_id LIKE ?)"
        term = f"%{search_term.strip()}%"
        cursor.execute(query, (term, term, term))
    else:
        cursor.execute(query)
        
    rows = cursor.fetchall()
    conn.close()
    
    today = date.today()
    result = []
    
    for r in rows:
        member_id, full_name, phone, national_id, rem_sessions, end_date, status = r
        
        is_expired = False
        if end_date:
            if isinstance(end_date, str):
                try:
                    end_date_val = datetime.strptime(end_date, "%Y-%m-%d").date()
                except ValueError:
                    end_date_val = datetime.strptime(end_date, "%Y-%m-%d %H:%M:%S").date()
            elif isinstance(end_date, datetime):
                end_date_val = end_date.date()
            else:
                end_date_val = end_date
                
            if end_date_val < today:
                is_expired = True

        if status == 'ACTIVE' and rem_sessions is not None and rem_sessions > 0 and not is_expired:
            can_assign = False
            status_text = f"🔴 دارای اشتراک فعال ({rem_sessions} جلسه باقی‌مانده)"
        else:
            can_assign = True
            if status is None:
                status_text = "🟢 مجاز به ثبت بسته (بدون اشتراک)"
            elif rem_sessions == 0:
                status_text = "🟢 مجاز به تمدید (اتمام جلسات)"
            else:
                status_text = "🟢 مجاز به تمدید (اشتراک منقضی شده)"

        result.append({
            'member_id': member_id,
            'full_name': full_name,
            'phone_number': phone,
            'national_id': national_id,
            'can_assign': can_assign,
            'status_text': status_text
        })
        
    return result

# --- ۱۱. تابع جستجوی داشبورد ---
def search_dashboard_members(search_term=""):
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        UPDATE Subscriptions 
        SET status = 'EXPIRED' 
        WHERE end_date < GETDATE() AND status = 'ACTIVE'
    """)
    conn.commit()
    
    query = """
        SELECT m.member_id, m.full_name, m.national_id, m.phone_number, s.subscription_id, s.remaining_sessions, s.end_date, s.status
        FROM Members m
        LEFT JOIN Subscriptions s ON m.member_id = s.member_id
    """
    
    if search_term and search_term.strip():
        query += " WHERE (m.full_name LIKE ? OR m.phone_number LIKE ? OR m.national_id LIKE ? OR CAST(m.member_id AS VARCHAR) LIKE ?)"
        term = f"%{search_term.strip()}%"
        df = pd.read_sql(query, conn, params=(term, term, term, term))
    else:
        df = pd.read_sql(query, conn)
        
    conn.close()
    return df

def get_churn_analytics_report():
    """دریافت گزارش تحلیل ریزش اعضا مستقیماً از View دیتابیس"""
    conn = get_connection()
    query = "SELECT * FROM vw_MemberChurnAnalytics ORDER BY [نمره ریسک ریزش (۰ تا ۱۰۰)] DESC"
    df = pd.read_sql(query, conn)
    conn.close()
    return df