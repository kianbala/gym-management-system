import random
from datetime import datetime, timedelta
from db_manager import get_connection

FIRST_NAMES = [
    'علی', 'محمد', 'امیر', 'حسین', 'مهدی', 'رضا', 'سروش', 'آرش', 'کامران', 'نوید',
    'سارا', 'نیلوفر', 'مریم', 'زهرا', 'پریسا', 'فاطمه', 'مهرنوش', 'کیانا', 'مینا', 'نرگس'
]

LAST_NAMES = [
    'رضایی', 'محمدی', 'احمدی', 'کریمی', 'حسینی', 'کاظمی', 'قاسمی', 'نوری', 'مرادی', 'ابراهیمی',
    'صادقی', 'حیدری', 'موسوی', 'نجفی', 'مظفری', 'شریفی', 'فراهانی', 'جعفری', 'اکبری', 'باقری'
]

def generate_data():
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM Packages")
    if cursor.fetchone()[0] == 0:
        print("⏳ در حال درج بسته‌های جدید ۱۲ و ۲۴ جلسه‌ای...")
        default_packages = [
            ('بسته ۱۲ جلسه ماهانه', 12, 30, 800000.00),
            ('بسته ۲۴ جلسه ماهانه', 24, 30, 1400000.00)
        ]
        cursor.executemany("""
            INSERT INTO Packages (title, total_sessions, validity_days, price)
            VALUES (?, ?, ?, ?)
        """, default_packages)
        conn.commit()

    print("⏳ در حال تولید ۳۰ عضو جدید...")
    
    members_data = []
    for i in range(1, 31):
        f_name = random.choice(FIRST_NAMES)
        l_name = random.choice(LAST_NAMES)
        national_id = f"{1000000000 + i * 123456 % 899999999}"[:10]
        phone_number = f"0912{random.randint(1000007, 9999999)}"
        members_data.append((f_name, l_name, national_id, phone_number))

    for f_name, l_name, nat_id, phone in members_data:
        cursor.execute("SELECT 1 FROM Members WHERE national_id = ? OR phone_number = ?", (nat_id, phone))
        if not cursor.fetchone():
            cursor.execute(
                "INSERT INTO Members (first_name, last_name, national_id, phone_number) VALUES (?, ?, ?, ?)",
                (f_name, l_name, nat_id, phone)
            )
    conn.commit()

    cursor.execute("SELECT package_id, total_sessions FROM Packages")
    packages = cursor.fetchall()
    
    cursor.execute("SELECT member_id FROM Members")
    members = cursor.fetchall()

    print("⏳ در حال تخصیص اشتراک‌های فعال (ACTIVE) و منقضی‌شده (EXPIRED)...")
    now = datetime.now()

    for m in members:
        m_id = m[0]
        
        cursor.execute("SELECT subscription_id FROM Subscriptions WHERE member_id = ?", (m_id,))
        if not cursor.fetchone():
            pkg = random.choice(packages)
            pkg_id, total_s = pkg[0], pkg[1]
            
            sub_status = random.choices(['ACTIVE', 'EXPIRED'], weights=[0.8, 0.2])[0]
            
            if sub_status == 'EXPIRED':
                start_date = now - timedelta(days=60)
                end_date = now - timedelta(days=random.randint(5, 25))
                remaining = random.randint(0, 5)
            else:
                start_date = now
                end_date = now + timedelta(days=30)
                scenario = random.choices(['zero_sessions', 'normal'], weights=[0.2, 0.8])[0]
                remaining = 0 if scenario == 'zero_sessions' else random.randint(1, total_s)
            
            cursor.execute("""
                INSERT INTO Subscriptions (member_id, package_id, remaining_sessions, start_date, end_date, status)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (m_id, pkg_id, remaining, start_date, end_date, sub_status))
            
    conn.commit()

    print("⏳ در حال ثبت ترددهای فرضی...")
    cursor.execute("SELECT subscription_id, member_id, status FROM Subscriptions")
    subs = cursor.fetchall()
    
    peak_hours = [17, 18, 18, 19, 19, 19, 20, 20, 21]
    regular_hours = [8, 9, 10, 11, 14, 15, 16, 22]
    all_hours = peak_hours + regular_hours

    for sub_id, member_id, status in subs:
        if status == 'EXPIRED':
            checkin_days = [random.randint(35, 55) for _ in range(random.randint(1, 4))]
        else:
            risk_profile = random.choices(['high_risk', 'medium_risk', 'low_risk'], weights=[0.25, 0.25, 0.5])[0]
            if risk_profile == 'high_risk':
                checkin_days = [random.randint(15, 25) for _ in range(random.randint(1, 3))]
            elif risk_profile == 'medium_risk':
                checkin_days = [random.randint(7, 13) for _ in range(random.randint(2, 5))]
            else:
                checkin_days = [random.randint(1, 6) for _ in range(random.randint(4, 10))]

        for days_ago in checkin_days:
            hour = random.choice(all_hours)
            minute = random.randint(0, 59)
            checkin_time = (now - timedelta(days=days_ago)).replace(hour=hour, minute=minute)
            
            cursor.execute("""
                INSERT INTO CheckIns (member_id, subscription_id, checkin_time)
                VALUES (?, ?, ?)
            """, (member_id, sub_id, checkin_time))
            
    conn.commit()
    print("✅ با موفقیت داده‌های جدید شامل اعضای فعال و EXPIRED ثبت شدند!")
    conn.close()
    
if __name__ == "__main__":
    generate_data()