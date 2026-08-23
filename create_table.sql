-- =========================================================
-- ۱. ایجاد پایگاه داده (در صورت عدم وجود)
-- =========================================================
IF NOT EXISTS (SELECT * FROM sys.databases WHERE name = N'GymManagementDB')
BEGIN
    CREATE DATABASE [GymManagementDB];
END
GO

USE [GymManagementDB];
GO

-- =========================================================
-- ۲. ساخت جداول پایه (بدون وابستگی)
-- =========================================================

-- جدول اعضا (اصلاح‌شده: تفکیک نام و نام خانوادگی)
IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[Members]') AND type in (N'U'))
BEGIN
    CREATE TABLE [dbo].[Members](
        [member_id] [int] IDENTITY(1,1) NOT NULL,
        [first_name] [nvarchar](50) NOT NULL,
        [last_name] [nvarchar](50) NOT NULL,
        -- ستون محاسباتی جهت ترکیب خودکار نام و نام خانوادگی برای هماهنگی با گزارش‌ها
        [full_name] AS (RTRIM(LTRIM([first_name])) + ' ' + RTRIM(LTRIM([last_name]))),
        [phone_number] [varchar](15) NULL,
        [national_id] [varchar](10) NULL,
        [join_date] [date] NOT NULL DEFAULT (GETDATE()),
        CONSTRAINT [PK_Members] PRIMARY KEY CLUSTERED ([member_id] ASC),
        CONSTRAINT [UQ_Members_NationalID] UNIQUE NONCLUSTERED ([national_id] ASC),
        CONSTRAINT [UQ_Members_PhoneNumber] UNIQUE NONCLUSTERED ([phone_number] ASC)
    );
END
GO

-- جدول پکیج‌ها
IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[Packages]') AND type in (N'U'))
BEGIN
    CREATE TABLE [dbo].[Packages](
        [package_id] [int] IDENTITY(1,1) NOT NULL,
        [title] [nvarchar](100) NOT NULL,
        [total_sessions] [int] NOT NULL,
        [validity_days] [int] NOT NULL,
        [price] [decimal](10, 2) NULL,
        CONSTRAINT [PK_Packages] PRIMARY KEY CLUSTERED ([package_id] ASC)
    );
END
GO

-- =========================================================
-- ۳. ساخت جداول وابسته (دارای کلید خارجی)
-- =========================================================

-- جدول اشتراک‌ها
IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[Subscriptions]') AND type in (N'U'))
BEGIN
    CREATE TABLE [dbo].[Subscriptions](
        [subscription_id] [int] IDENTITY(1,1) NOT NULL,
        [member_id] [int] NOT NULL,
        [package_id] [int] NOT NULL,
        [remaining_sessions] [int] NOT NULL,
        [start_date] [date] NOT NULL,
        [end_date] [date] NOT NULL,
        [status] [nvarchar](20) NULL DEFAULT (N'ACTIVE'),
        CONSTRAINT [PK_Subscriptions] PRIMARY KEY CLUSTERED ([subscription_id] ASC),
        CONSTRAINT [FK_Subscriptions_Members] FOREIGN KEY([member_id]) REFERENCES [dbo].[Members] ([member_id]),
        CONSTRAINT [FK_Subscriptions_Packages] FOREIGN KEY([package_id]) REFERENCES [dbo].[Packages] ([package_id])
    );
END
GO

-- جدول ثبت ورود/خروج (CheckIns)
IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[CheckIns]') AND type in (N'U'))
BEGIN
    CREATE TABLE [dbo].[CheckIns](
        [checkin_id] [int] IDENTITY(1,1) NOT NULL,
        [member_id] [int] NOT NULL,
        [subscription_id] [int] NOT NULL,
        [checkin_time] [datetime] NOT NULL DEFAULT (GETDATE()),
        CONSTRAINT [PK_CheckIns] PRIMARY KEY CLUSTERED ([checkin_id] ASC),
        CONSTRAINT [FK_CheckIns_Members] FOREIGN KEY([member_id]) REFERENCES [dbo].[Members] ([member_id]),
        CONSTRAINT [FK_CheckIns_Subscriptions] FOREIGN KEY([subscription_id]) REFERENCES [dbo].[Subscriptions] ([subscription_id])
    );
END
GO

-- جدول تحلیلی هوش مصنوعی
IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[AI_Analytics]') AND type in (N'U'))
BEGIN
    CREATE TABLE [dbo].[AI_Analytics](
        [analytics_id] [int] IDENTITY(1,1) NOT NULL,
        [member_id] [int] NOT NULL,
        [churn_risk_score] [float] NOT NULL,
        [last_calculated] [datetime] NULL DEFAULT (GETDATE()),
        CONSTRAINT [PK_AI_Analytics] PRIMARY KEY CLUSTERED ([analytics_id] ASC),
        CONSTRAINT [FK_AI_Analytics_Members] FOREIGN KEY([member_id]) REFERENCES [dbo].[Members] ([member_id])
    );
END
GO

-- =========================================================
-- ۴. ساخت نمای تحلیلی (View)
-- =========================================================
IF OBJECT_ID(N'[dbo].[vw_MemberChurnAnalytics]', N'V') IS NOT NULL
    DROP VIEW [dbo].[vw_MemberChurnAnalytics];
GO

CREATE VIEW [dbo].[vw_MemberChurnAnalytics] AS
SELECT 
    m.member_id AS [کد عضویت],
    m.full_name AS [نام ورزشکار],
    m.phone_number AS [شماره تماس],
    ai.churn_risk_score AS [نمره ریسک ریزش (۰ تا ۱۰۰)],
    CASE 
        WHEN ai.churn_risk_score >= 70 THEN N'بالا (High) 🔴'
        WHEN ai.churn_risk_score >= 40 THEN N'متوسط (Medium) 🟡'
        ELSE N'پایین (Low) 🟢'
    END AS [سطح ریسک],
    ai.last_calculated AS [تاریخ آخرین محاسبه]
FROM [dbo].[AI_Analytics] ai
JOIN [dbo].[Members] m ON ai.member_id = m.member_id;
GO