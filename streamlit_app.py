import streamlit as st
import pandas as pd
import requests
import matplotlib.pyplot as plt
from io import BytesIO
import os
import smtplib
from email.message import EmailMessage

# Load secrets
SERPAPI_API_KEY = st.secrets["SERPAPI_API_KEY"]
EMAIL_SENDER = st.secrets["EMAIL_SENDER"]
EMAIL_PASSWORD = st.secrets["EMAIL_PASSWORD"]
ALERT_EMAIL = st.secrets["ALERT_EMAIL"]

st.set_page_config(page_title="🔍 SERP Checker", layout="wide")
st.title("🔍 SERP Keyword Rank Checker with Alerts")

# Cache previous rank state
if "previous_ranks" not in st.session_state:
    st.session_state.previous_ranks = {}

def check_keyword_rank(keyword, domain):
    params = {
        "engine": "google",
        "q": keyword,
        "api_key": SERPAPI_API_KEY,
        "num": "100",
    }
    response = requests.get("https://serpapi.com/search", params=params)
    data = response.json()
    organic_results = data.get("organic_results", [])

    for result in organic_results:
        if domain in result.get("link", ""):
            return result.get("position", 0), result.get("link")
    return 0, "Not Found"

def send_email_alert(keyword, domain, current, previous, status, url):
    msg = EmailMessage()
    msg['Subject'] = f"Keyword '{keyword}' - Rank {status}"
    msg['From'] = EMAIL_SENDER
    msg['To'] = ALERT_EMAIL
    msg.set_content(f"""
Keyword: {keyword}
Domain: {domain}
Previous Rank: {previous}
Current Rank: {current}
Status: {status}
Ranking URL: {url}
    """)
    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(EMAIL_SENDER, EMAIL_PASSWORD)
            smtp.send_message(msg)
    except Exception as e:
        print(f"Email failed: {e}")

def process_keywords(keywords_list, domain):
    results = []
    for keyword in keywords_list:
        rank, url = check_keyword_rank(keyword, domain)
        previous = st.session_state.previous_ranks.get(keyword, None)
        change = "New" if previous is None else (
            "Improved" if rank < previous else (
                "Dropped" if rank > previous else "No Change"
            )
        )
        st.session_state.previous_ranks[keyword] = rank

        if previous is not None and rank != previous:
            send_email_alert(keyword, domain, rank, previous, change, url)

        results.append({
            "Keyword": keyword,
            "Rank": rank,
            "Ranking URL": url,
            "Previous": previous,
            "Change": change
        })
    return pd.DataFrame(results)

def plot_chart(df):
    df_sorted = df.sort_values("Rank", ascending=False)
    colors = df_sorted["Change"].map({
        "Improved": "green",
        "Dropped": "red",
        "No Change": "gray",
        "New": "blue"
    }).fillna("gray")

    fig, ax = plt.subplots(figsize=(10, len(df_sorted) * 0.6))
    bars = ax.barh(df_sorted["Keyword"], df_sorted["Rank"], color=colors)

    for bar, rank in zip(bars, df_sorted["Rank"]):
        ax.text(rank + 1, bar.get_y() + bar.get_height()/2, f'Rank {rank}', va='center', fontsize=9)

    ax.set_xlabel("Google Rank (lower is better)")
    ax.set_title("Keyword Ranking Overview")
    ax.invert_xaxis()
    ax.grid(axis='x', linestyle='--', alpha=0.6)
    return fig

# === UI ===
domain = st.text_input("Enter your domain (e.g., example.com):")

keyword_text = st.text_area("Enter keywords (comma-separated):")
uploaded_file = st.file_uploader("Or upload a CSV with keywords", type=["csv"])

run_button = st.button("Run SERP Check")

if run_button and domain:
    if uploaded_file:
        df_input = pd.read_csv(uploaded_file)
        keywords = df_input.iloc[:, 0].dropna().tolist()
    else:
        keywords = [kw.strip() for kw in keyword_text.split(",") if kw.strip()]

    if not keywords:
        st.warning("No keywords provided.")
    else:
        result_df = process_keywords(keywords, domain)
        st.dataframe(result_df)

        fig = plot_chart(result_df)
        buf = BytesIO()
        fig.savefig(buf, format="png")
        st.image(buf)

