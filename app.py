import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px

st.set_page_config(page_title="Dublin Property Tracker", layout="wide")

st.title("☘️ Dublin Residential Property Insights (2026)")

# Connect to the database
conn = sqlite3.connect('dublin_properties.db')

# --- 1. Top Level Metrics ---
col1, col2, col3 = st.columns(3)

# Average Asking Price
avg_price = pd.read_sql("SELECT AVG(asking_price) FROM properties WHERE status='active'", conn).iloc[0,0]
col1.metric("Avg. Asking Price", f"€{avg_price:,.0f}" if avg_price else "N/A")

# Total Volume
total_listings = pd.read_sql("SELECT COUNT(*) FROM properties WHERE status='active'", conn).iloc[0,0]
col2.metric("Properties on Market", total_listings)

# Avg Days on Market
avg_dom = pd.read_sql("SELECT AVG(days_on_market) FROM properties WHERE status='off-market'", conn).iloc[0,0]
col3.metric("Avg. Days to Sell", f"{avg_dom:.1f} Days" if avg_dom else "Collecting Data...")

# --- 2. Price Distribution Chart ---
st.subheader("Price Distribution")
df_active = pd.read_sql("SELECT asking_price FROM properties WHERE status='active'", conn)
if not df_active.empty:
    fig = px.histogram(df_active, x="asking_price", nbins=20, 
                       title="Range of Asking Prices in Dublin",
                       labels={'asking_price': 'Price (€)'},
                       color_discrete_sequence=['#2ecc71'])
    st.plotly_chart(fig, use_container_width=True)

# --- 3. Data Table ---
st.subheader("Recent Listings")
df_all = pd.read_sql("SELECT address, asking_price, first_seen, status FROM properties ORDER BY first_seen DESC LIMIT 50", conn)
st.dataframe(df_all, use_container_width=True)

conn.close()
