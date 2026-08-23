import streamlit as st
import pandas as pd
import time
from db_manager import (
    get_connection, 
    add_member, 
    delete_member,
    assign_package, 
    record_checkin, 
    delete_subscription,
    get_all_packages,
    reset_all_data,
    search_members_for_checkin,
    search_all_members,
    search_dashboard_members,  
    get_churn_analytics_report
)
from ai_analytics import get_hourly_occupancy, predict_churn_risk

st.set_page_config(page_title="سامانه مدیریت هوشمند باشگاه", layout="wide")

st.markdown("""
    <style>
    html, body, [class*="css"] {
        direction: rtl;
        text-align: right;
        font-family: 'Tahoma', 'Vazirmatn', sans-serif;
    }
    div[data-baseweb="select"] {
        direction: rtl !important;
        text-align: right !important;
    }
    div[data-testid="InputInstructions"] {
        display: none !important;
    }
    [data-testid="stMetricValue"] {
        font-size: 24px !important;
        font-weight: bold;
    }
    </style>
""", unsafe_allow_html=True)

menu = [
    "داشبورد و اعضا", 
    "ثبت عضو جدید", 
    "ثبت ورود (تردد)", 
    "تخصیص بسته", 
    "📊 تحلیل و هوش مصنوعی", 
    "مدیریت و حذف"
]
choice = st.sidebar.selectbox("منوی اصلی", menu)

# --- بخش ۱: مشاهده و جستجوی اعضا ---
if choice == "داشبورد و اعضا":
    st.subheader("📋 لیست اعضا و وضعیت اشتراک‌ها")
    
    col_search, col_filter = st.columns([2, 1])
    
    with col_search:
        search_dash = st.text_input("🔍 جستجوی عضو (نام، شماره، کد ملی یا کد عضویت):", placeholder="مثلاً: کیان، کیانا، 0912 یا 1000...")
        
    df = search_dashboard_members(search_dash)
    
    with col_filter:
        status_options = ["همه", "ACTIVE", "EXPIRED"]
        selected_status = st.selectbox("فیلتر وضعیت اشتراک:", status_options)
        
    if not df.empty:
        if selected_status != "همه":
            filtered_df = df[df['status'] == selected_status]
        else:
            filtered_df = df
            
        st.caption(f"📊 تعداد اعضای یافت شده: **{len(filtered_df)} نفر**")
        
        df_display = filtered_df.rename(columns={
            'member_id': 'کد عضویت',
            'full_name': 'نام و نام خانوادگی',
            'national_id': 'کد ملی',
            'phone_number': 'شماره تماس',
            'subscription_id': 'کد اشتراک',
            'remaining_sessions': 'جلسات باقی‌مانده',
            'end_date': 'تاریخ انقضا',
            'status': 'وضعیت'
        })
        st.dataframe(df_display, use_container_width=True, hide_index=True)
    else:
        st.info("هیچ عضوی با این مشخصات یافت نشد.")

# --- بخش ۲: ثبت عضو جدید ---
elif choice == "ثبت عضو جدید":
    st.subheader("➕ ثبت عضو جدید")
    with st.form("add_member_form"):
        col1, col2 = st.columns(2)
        with col1:
            first_name = st.text_input("نام")
            last_name = st.text_input("نام خانوادگی")
        with col2:
            national_id = st.text_input("کد ملی (۱۰ رقمی)")
            phone_number = st.text_input("شماره تماس (۱۱ رقمی)")
            
        submit = st.form_submit_button("ثبت عضو")
        
        if submit:
            first_name_clean = first_name.strip()
            last_name_clean = last_name.strip()
            
            if first_name_clean and last_name_clean and national_id and phone_number:
                if len(national_id) != 10 or not national_id.isdigit():
                    st.warning("کد ملی باید دقیقاً ۱۰ رقم عددی باشد.")
                elif len(phone_number) != 11 or not phone_number.isdigit():
                    st.warning("شماره تماس باید دقیقاً ۱۱ رقم عددی باشد (مثلاً 09123456789).")
                else:
                    success, msg = add_member(first_name_clean, last_name_clean, national_id, phone_number)
                    if success:
                        st.success(msg)
                    else:
                        st.error(msg)
            else:
                st.warning("لطفاً تمامی فیلدها (از جمله نام و نام خانوادگی) را پر کنید.")

# --- بخش ۳: ثبت ورود ---
elif choice == "ثبت ورود (تردد)":
    st.subheader("🚪 ثبت ورود ورزشکار و کسر جلسه")
    
    search_input = st.text_input("🔍 جستجوی ورزشکار (نام، شماره تماس یا کد ملی):", placeholder="مثلاً: سعیدی علی، یا 0912...")
    
    members_list = search_members_for_checkin(search_input)
    
    if members_list:
        st.caption(f"🔍 تعداد {len(members_list)} مورد یافت شد. از لیست زیر انتخاب کنید:")
        
        options = {}
        for m in members_list:
            label = f"👤 {m['full_name']} | 📱 {m['phone_number']} | 🔢 باقی‌مانده: {m['remaining_sessions']} جلسه (کد عضویت: {m['member_id']})"
            options[label] = m
            
        selected_label = st.selectbox("لیست افراد یافت‌شده:", list(options.keys()))
        selected_member = options[selected_label]
        
        st.info(
            f"**عضو انتخاب‌شده:** {selected_member['full_name']}  \n"
            f"**جلسات باقی‌مانده فعلی:** {selected_member['remaining_sessions']} جلسه"
        )
        
        if st.button("🟢 ثبت حضور (کاهش ۱ جلسه)", type="primary"):
            success, msg = record_checkin(selected_member['member_id'])
            if success:
                st.success(msg)
                time.sleep(1)
                st.rerun()
            else:
                st.error(msg)
    else:
        st.warning("هیچ عضو فعالی با این مشخصات یافت نشد.")

# --- بخش ۴: تخصیص بسته ---
elif choice == "تخصیص بسته":
    st.subheader("💳 اختصاص بسته جدید به عضو")
    
    search_input = st.text_input("🔍 جستجوی ورزشکار (نام، شماره تماس یا کد ملی):", placeholder="مثلاً: مه، حسین، یا 0912...", key="assign_search")
    
    all_members = search_all_members(search_input)
    
    if all_members:
        st.caption(f"🔍 تعداد {len(all_members)} مورد یافت شد:")
        
        member_options = {}
        for m in all_members:
            label = f"👤 {m['full_name']} | 📱 {m['phone_number']} | 🆔 کد ملی: {m['national_id']} | {m['status_text']}"
            member_options[label] = m
            
        selected_member_label = st.selectbox("انتخاب عضو:", list(member_options.keys()))
        selected_member = member_options[selected_member_label]
        selected_member_id = selected_member['member_id']
        
        if selected_member['can_assign']:
            st.info(f"✅ این کاربر وضعیت {selected_member['status_text']} دارد و آماده ثبت بسته جدید است.")
        else:
            st.warning(f"⚠️ {selected_member['status_text']}. تا زمانی که جلسات به اتمام نرسد یا انقضا نیاید امکان بسته جدید نیست.")

        packages_df = get_all_packages()
        if not packages_df.empty:
            package_options = {}
            packages_sorted = packages_df.sort_values(by='total_sessions')
            
            for idx, (_, row) in enumerate(packages_sorted.iterrows(), start=1):
                display_title = f"بسته {idx}"
                sessions = row.get('total_sessions', '')
                price = row.get('price')
                
                price_str = f"{int(price):,} تومان" if pd.notnull(price) else "بدون قیمت"
                label = f"{display_title} | یک ماه {sessions} جلسه | {price_str}"
                
                package_options[label] = row['package_id']
                
            selected_package_label = st.selectbox("انتخاب بسته ورزشی:", list(package_options.keys()))
            package_id = package_options[selected_package_label]
            
            if st.button("🟢 فعال‌سازی بسته", type="primary"):
                success, message = assign_package(selected_member_id, package_id)
                if success:
                    st.success(message)
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error(message)
        else:
            st.error("هیچ بسته‌ای در دیتابیس یافت نشد.")
    else:
        st.warning("هیچ عضوی با این مشخصات یافت نشد.")

# --- بخش ۵: تحلیل و هوش مصنوعی ---
elif choice == "📊 تحلیل و هوش مصنوعی":
    st.subheader("🤖 ماژول تحلیلی و پیش‌بینی هوشمند")
    
    hourly_df = get_hourly_occupancy()
    churn_df = predict_churn_risk()
    
    total_checkins = hourly_df['checkin_count'].sum() if not hourly_df.empty else 0
    if not hourly_df.empty and total_checkins > 0:
        peak_hour = hourly_df.loc[hourly_df['checkin_count'].idxmax()]['hour']
        peak_str = f"ساعت {peak_hour}:00"
    else:
        peak_str = "نامشخص"
        
    total_members = churn_df.shape[0] if not churn_df.empty else 0
    
    if total_members > 0:
        high_risk_cnt = churn_df[churn_df['risk_level'] == 'بالا (High)'].shape[0]
        medium_risk_cnt = churn_df[churn_df['risk_level'] == 'متوسط (Medium)'].shape[0]
        low_risk_cnt = churn_df[churn_df['risk_level'] == 'پایین (Low)'].shape[0]
        
        high_pct = (high_risk_cnt / total_members) * 100
        med_pct = (medium_risk_cnt / total_members) * 100
        low_pct = (low_risk_cnt / total_members) * 100
    else:
        high_risk_cnt = medium_risk_cnt = low_risk_cnt = 0
        high_pct = med_pct = low_pct = 0.0

    m1, m2, m3, m4, m5 = st.columns(5)
    
    m1.metric("مجموع ترددها", f"{total_checkins} ورود")
    m2.metric("شلوغ‌ترین زمان", peak_str)
    
    m3.metric("ریسک بالا 🔴", f"{high_risk_cnt} نفر", f"{high_pct:.1f}% از کل اعضا", delta_color="inverse")
    m4.metric("ریسک متوسط 🟡", f"{medium_risk_cnt} نفر", f"{med_pct:.1f}% از کل اعضا", delta_color="off")
    m5.metric("ریسک پایین 🟢", f"{low_risk_cnt} نفر", f"{low_pct:.1f}% از کل اعضا", delta_color="normal")
    
    st.markdown("---")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.write("### 📈 تحلیل ساعات شلوغی باشگاه")
        if not hourly_df.empty:
            st.bar_chart(data=hourly_df, x='hour', y='checkin_count', color="#1f77b4")
            st.caption("پراکندگی ورود ورزشکاران در طول ۲۴ ساعت شبانه‌روز")
        else:
            st.info("داده‌ای برای تحلیل تردد وجود ندارد.")
            
    with col2:
        st.write("### ⚠️ پیش‌بینی ریسک ریزش اعضا (گزارش مستقیم از SQL View)")
        
        # دریافت و نمایش گزارش مستقیم از View دیتابیس
        df_view = get_churn_analytics_report()
        
        if not df_view.empty:
            st.dataframe(df_view, use_container_width=True, hide_index=True)
            st.caption("این اطلاعات مستقیماً از نمای تحلیلی دیتابیس (vw_MemberChurnAnalytics) فراخوانی شده است.")
        else:
            st.info("هیچ داده‌ای در نمای تحلیلی یافت نشد.")

# --- بخش ۶: مدیریت و حذف ---
elif choice == "مدیریت و حذف":
    st.subheader("👤 حذف دستی یک عضو مشخص")

    search_term = st.text_input("🔍 جستجوی عضو جهت حذف (بر اساس نام، شماره تماس یا کد ملی):")

    all_members = search_all_members(search_term)

    if all_members:
        member_options = {
            f"کد: {m['member_id']} | {m['full_name']} | همراه: {m['phone_number']} | کد ملی: {m['national_id']}": m['member_id']
            for m in all_members
        }
        
        selected_option = st.selectbox("عضو مورد نظر را برای حذف انتخاب کنید:", list(member_options.keys()))
        selected_member_id = member_options[selected_option]

        if st.button("❌ حذف کامل عضو"):
            success, msg = delete_member(selected_member_id)
            if success:
                st.success(msg)
                time.sleep(1)
                st.rerun()
            else:
                st.error(msg)
    else:
        st.warning("هیچ عضوی با این مشخصات یافت نشد.")

    st.markdown("---")
    st.subheader("🗑️ حذف اشتراک‌های اضافی (بدون حذف عضو)")

    sub_search_term = st.text_input("🔍 جستجوی عضو جهت مدیریت/حذف اشتراک (نام، شماره تماس یا کد ملی):", key="sub_search_input")

    all_members_sub = search_all_members(sub_search_term)

    if all_members_sub:
        sub_member_options = {
            f"کد: {m['member_id']} | {m['full_name']} | همراه: {m['phone_number']}": m['member_id']
            for m in all_members_sub
        }
        
        selected_sub_member_label = st.selectbox("عضو مورد نظر را انتخاب کنید:", list(sub_member_options.keys()), key="sub_member_select")
        selected_sub_member_id = sub_member_options[selected_sub_member_label]

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT s.subscription_id, p.title, s.remaining_sessions 
            FROM Subscriptions s
            JOIN Packages p ON s.package_id = p.package_id
            WHERE s.member_id = ?
        """, (selected_sub_member_id,))
        member_subs = cursor.fetchall()
        conn.close()

        if member_subs:
            sub_options = {
                f"کد اشتراک: {s[0]} | پکیج: {s[1]} | جلسات باقی‌مانده: {s[2]}": s[0]
                for s in member_subs
            }

            selected_sub_label = st.selectbox("اشتراکی که قصد حذف آن را دارید انتخاب کنید:", list(sub_options.keys()), key="sub_id_select")
            selected_sub_id = sub_options[selected_sub_label]

            if st.button("❌ حذف این اشتراک"):
                success, msg = delete_subscription(selected_sub_id)
                if success:
                    st.success(msg)
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error(msg)
        else:
            st.info("این عضو در حال حاضر هیچ اشتراک ثبت‌شده‌ای ندارد.")
    else:
        st.warning("هیچ عضوی با این مشخصات یافت نشد.")

    st.markdown("---")
    st.subheader("⚠️ ریست کامل دیتابیس (حذف تمامی اعضا و داده‌ها)")
    st.error("هشدار: این عملیات غیرقابل بازگشت است و تمام اعضا، اشتراک‌ها و ترددها را حذف می‌کند!")
    
    confirm_text = st.text_input("برای تایید، عبارت 'RESET' را به انگلیسی وارد کنید:")
    
    if confirm_text == "RESET":
        col1, col2 = st.columns([1, 1])
        with col1:
            start_reset = st.button("🚨 شروع پاکسازی (با مهلت ۵ ثانیه انصراف)")
            
        if start_reset:
            progress_bar = st.progress(100)
            status_text = st.empty()
            
            canceled = False
            with col2:
                if st.button("❌ انصراف و لغو عملیات"):
                    canceled = True
            
            for i in range(5, 0, -1):
                if canceled:
                    break
                status_text.warning(f"⚠️ پاکسازی دیتابیس تا {i} ثانیه دیگر انجام می‌شود... در صورت پشیمانی دکمه انصراف را بزنید!")
                progress_bar.progress(i * 20)
                time.sleep(1)
                
            if not canceled:
                status_text.empty()
                progress_bar.empty()
                try:
                    reset_all_data()
                    st.success("🎉 تمامی داده‌ها با موفقیت پاک شدند و سیستم کاملاً ریست شد.")
                except Exception as e:
                    st.error(f"خطا در ریست دیتابیس: {e}")
            else:
                status_text.empty()
                progress_bar.empty()
                st.info("عملیات پاکسازی با موفقیت لغو شد.")