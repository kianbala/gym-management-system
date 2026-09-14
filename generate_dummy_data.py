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

    # ۱. بررسی و ساخت بسته‌های پیش‌فرض
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

    cursor.execute("SELECT package_id, total_sessions FROM Packages")
    packages = cursor.fetchall()

    print("⏳ در حال افزودن ۳۰ عضو جدید (با نسبت ۸۰٪ فعال و ۲۰٪ منقضی)...")
    now = datetime.now()
    
    peak_hours = [17, 18, 18, 19, 19, 19, 20, 20, 21]
    regular_hours = [8, 9, 10, 11, 14, 15, 16, 22]
    all_hours = peak_hours + regular_hours

    added_count = 0
    for i in range(1, 31):
        f_name = random.choice(FIRST_NAMES)
        l_name = random.choice(LAST_NAMES)
        
        unique_seed = int(now.timestamp()) + i
        national_id = f"{1000000000 + (unique_seed * 123) % 899999999}"[:10]
        phone_number = f"0912{random.randint(1000000, 9999999)}"

        cursor.execute("SELECT 1 FROM Members WHERE national_id = ? OR phone_number = ?", (national_id, phone_number))
        if cursor.fetchone():
            continue

        cursor.execute("""
            INSERT INTO Members (first_name, last_name, national_id, phone_number)
            VALUES (?, ?, ?, ?);
        """, (f_name, l_name, national_id, phone_number))
        
        cursor.execute("SELECT @@IDENTITY;")
        member_id = int(cursor.fetchone()[0])

        pkg = random.choice(packages)
        pkg_id, total_sessions = pkg[0], pkg[1]
        
        # 🎯 تعیین وضعیت اشتراک: ۸۰٪ ACTIVE و ۲۰٪ EXPIRED
        sub_status = random.choices(['ACTIVE', 'EXPIRED'], weights=[0.80, 0.20])[0]

        if sub_status == 'EXPIRED':
            # کاربر منقضی‌شده: تاریخ شروع قدیمی (۴۵ تا ۶۰ روز پیش) و انقضا در گذشته
            start_days_ago = random.randint(45, 60)
            start_date = now - timedelta(days=start_days_ago)
            end_date = start_date + timedelta(days=30)
            
            # جلسات باقی‌مانده ۰ یا عدد بسیار پایین
            remaining = random.choice([0, 0, 0, random.randint(1, 2)])
            days_active = start_days_ago
            
            # آخرین تردد مربوط به زمان فعال بودن اشتراک (۱۵ تا ۳۵ روز پیش)
            last_checkin_days_ago = random.randint(15, min(35, days_active))
            
        else:
            # کاربر فعال: ثبت‌نام در طی ۲۸ روز گذشته
            days_active = random.randint(1, 28)
            start_date = now - timedelta(days=days_active)
            end_date = start_date + timedelta(days=30)

            # تقسیم رفتار اعضای فعال به ۳ الگوی واقع‌گرایانه
            pattern = random.choices(['regular', 'at_risk', 'churning'], weights=[0.60, 0.25, 0.15])[0]

            if pattern == 'regular':
                last_checkin_days_ago = random.randint(0, min(3, days_active))
                remaining = random.randint(4, total_sessions - 1)
                
            elif pattern == 'at_risk':
                min_days = min(6, days_active)
                max_days = min(10, days_active)
                last_checkin_days_ago = random.randint(min_days, max_days)
                remaining = random.randint(1, 3)
                
            else: # churning
                min_days = min(12, days_active)
                max_days = min(25, days_active)
                last_checkin_days_ago = random.randint(min_days, max_days)
                remaining = 0

        cursor.execute("""
            INSERT INTO Subscriptions (member_id, package_id, remaining_sessions, start_date, end_date, status)
            VALUES (?, ?, ?, ?, ?, ?);
        """, (member_id, pkg_id, remaining, start_date, end_date, sub_status))

        cursor.execute("SELECT @@IDENTITY;")
        sub_id = int(cursor.fetchone()[0])

        # ثبت آخرین تردد
        hour = random.choice(all_hours)
        minute = random.randint(0, 59)
        last_checkin_time = (now - timedelta(days=last_checkin_days_ago)).replace(hour=hour, minute=minute)

        cursor.execute("""
            INSERT INTO CheckIns (member_id, subscription_id, checkin_time)
            VALUES (?, ?, ?);
        """, (member_id, sub_id, last_checkin_time))

        # ثبت ترددهای گذشته به تعداد جلسات استفاده‌شده
        used_sessions = max(0, total_sessions - remaining - 1)
        
        start_past_days = min(last_checkin_days_ago + 1, days_active)
        end_past_days = days_active
        
        for _ in range(used_sessions):
            past_days_ago = random.randint(start_past_days, end_past_days)
            past_hour = random.choice(all_hours)
            past_minute = random.randint(0, 59)
            past_checkin_time = (now - timedelta(days=past_days_ago)).replace(hour=past_hour, minute=past_minute)
            
            cursor.execute("""
                INSERT INTO CheckIns (member_id, subscription_id, checkin_time)
                VALUES (?, ?, ?);
            """, (member_id, sub_id, past_checkin_time))
            
        added_count += 1

    conn.commit()
    print(f"✅ با موفقیت {added_count} عضو جدید (با نسبت ۸۰٪ فعال و ۲۰٪ منقضی) اضافه شدند!")
    conn.close()

if __name__ == "__main__":
    generate_data()