"""
连板晋级率手机看板 (Streamlit)
运行: streamlit run app.py
"""
import streamlit as st
import pandas as pd
import os

st.set_page_config(page_title="连板晋级率", page_icon="📈", layout="wide")
st.title("📈 连板股晋级率统计")
st.caption("仅统计主板 | 排除 ST / *ST / 次新股 | 数据每日更新")

DATA_FILE = os.path.join("data", "summary.csv")
if not os.path.exists(DATA_FILE):
    st.error("还没有数据，请先运行 collect_data.py 采集数据！")
    st.stop()

df = pd.read_csv(DATA_FILE)
df["日期"] = df["日期"].astype(str)

# 侧边栏筛选
st.sidebar.header("筛选")
dates = sorted(df["日期"].unique(), reverse=True)
sel_dates = st.sidebar.multiselect("日期", dates, default=dates[:10])
nums = sorted(df["连板数"].unique())
sel_nums = st.sidebar.multiselect("连板数", nums, default=nums)

filtered = df[(df["日期"].isin(sel_dates)) & (df["连板数"].isin(sel_nums))]

# KPI
c1, c2, c3, c4 = st.columns(4)
c1.metric("统计天数", len(filtered["日期"].unique()))
c2.metric("总样本数", int(filtered["股票总数"].sum()))
if filtered["股票总数"].sum() > 0:
    up_sum = filtered["上涨数"].sum()
    total_sum = filtered["股票总数"].sum()
    c3.metric("整体上涨比例", f"{round(up_sum/total_sum*100,2)}%")
    c4.metric("平均涨跌幅", f"{round(filtered['平均涨跌幅'].mean(),2)}%")

st.subheader("📊 数据表格")
st.dataframe(
    filtered.sort_values(["日期", "连板数"], ascending=[False, True]),
    use_container_width=True, hide_index=True,
    column_config={
        "日期": "日期", "连板数": st.column_config.NumberColumn("连板数"),
        "股票总数": "总数", "上涨数": "上涨", "下跌数": "下跌",
        "上涨比例": st.column_config.NumberColumn("上涨比例", format="%.1f%%"),
        "上涨/下跌比": "涨跌比", "平均涨跌幅": st.column_config.NumberColumn("均涨跌幅", format="%.2f%%"),
    }
)

st.subheader("📈 上涨比例趋势")
pivot = filtered.pivot_table(values="上涨比例", index="日期", columns="连板数", aggfunc="mean")
st.line_chart(pivot)