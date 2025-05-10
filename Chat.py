import streamlit as st
import pandas as pd
import sqlite3
import google.generativeai as genai
import requests
from datetime import datetime
import re
import speech_recognition as sr

# ===== إعداد API =====
genai.configure(api_key="AIzaSyCP4FN3ocHc087VHOhsDQWsSFBefAFcsWk")  # ← استبدلها بمفتاح Gemini

# ===== تحميل البيانات =====
df = pd.read_csv("jordan_transactions.csv")

# تحويل التاريخ
df["transaction_date"] = pd.to_datetime(df["transaction_date"], format="%d/%m/%Y %H:%M", errors="coerce")

# إنشاء قاعدة بيانات مؤقتة
conn = sqlite3.connect("transactions.db")
df.to_sql("transactions", conn, if_exists="replace", index=False)

# ===== التحقق من المعاملات الفاشلة اليوم =====
today = datetime.now().date()
failed_today = df[
    (df["transaction_status"] == "Failed") &
    (df["transaction_date"].dt.date == today)
]

# ===== إرسال تنبيه إذا لزم الأمر =====
# def send_telegram_message(message):
#     BOT_TOKEN = 'YOUR_BOT_TOKEN'  # ← استبدلها
#     CHAT_ID = 'YOUR_CHAT_ID'      # ← استبدلها
#     url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
#     payload = {'chat_id': CHAT_ID, 'text': message}
#     requests.post(url, data=payload)

# if len(failed_today) > 5:
#     alert_message = f"🚨 Alert: {len(failed_today)} failed transactions today!"
#     st.error(alert_message)
#     send_telegram_message(alert_message)

# ===== واجهة Streamlit =====
st.title("💬 Gemini SQL Agent")

# ===== إدخال صوتي =====
st.markdown("### 🎙️ أدخل سؤالك بالصوت:")
voice_query = ""

if st.button("اضغط للتسجيل"):
    recognizer = sr.Recognizer()
    with sr.Microphone() as source:
        st.info("⏺️ استمع الآن... تكلّم")
        audio = recognizer.listen(source)
        st.success("✅ تم التسجيل، جاري التحويل إلى نص...")

    try:
        voice_query = recognizer.recognize_google(audio, language="ar-JO")
        st.text_area("📝 النص المُتعرف عليه:", voice_query, height=100)
    except Exception as e:
        st.error(f"❌ خطأ في التعرف على الصوت: {e}")

# ===== إدخال كتابي =====
user_query = st.text_input("✍️ أو اكتب سؤالك هنا:")

# ===== استخدام الإدخال الصوتي أو الكتابي =====
if user_query or voice_query:
    query_input = user_query if user_query else voice_query

    prompt = f"""
    You are an intelligent assistant that converts natural language questions into accurate SQL queries.

    The target table contains transaction data. Assume these column types:
    - `transaction_date`: datetime in format YYYY-MM-DD HH:MM
    - `transaction_status`: string (e.g., Completed, Failed)
    - `transaction_amount`: float
    - `tax_amount`: float
    - `mall_name`, `branch_name`: string

    IMPORTANT:
    - Understand and support various **date and time formats** from the user, such as:
      * 12/1/2025 → means 12 January 2025 (day/month/year)
      * January 12, 2025
      * 2025-01-12
      * With time: "after 14:00", "before 3:30 PM", "at 09:00", "between 10:00 and 11:30"
    - If the user provides ambiguous formats like `12/1/2025`, always treat it as **day/month/year** unless told otherwise.
    - Use accurate datetime comparisons (e.g., >=, <, BETWEEN) for filtering.

    ⚠️ When asked for the highest or lowest value (e.g., highest tax, max transaction), always use:
    ORDER BY ... DESC / ASC LIMIT 1
    to return the correct result.

    Always refer to the correct table name: `transactions`.

    Here is a sample of the table:
    {df.head(2).to_string(index=False)}

    Question: {query_input}
    SQL:
    """

    model = genai.GenerativeModel("gemini-1.5-flash")
    response = model.generate_content(prompt)

    raw_text = response.candidates[0].content.parts[0].text
    cleaned = raw_text.replace("```sql", "").replace("```", "").strip()
    sql_query = cleaned.split(';')[0].strip() + ';'
    sql_query = sql_query.replace("your_table_name", "transactions")

    try:
        result_df = pd.read_sql_query(sql_query, conn)
        st.markdown("**📊 النتائج:**")
        st.dataframe(result_df)
    except Exception as e:
        st.error(f"❌ خطأ في تنفيذ SQL:\n{e}")
