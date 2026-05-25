"""
连板股数据采集脚本
每天收盘后运行一次，自动获取 2~6 连板股的晋级数据
"""
import akshare as ak
import pandas as pd
import os
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

# ==================== 设置 ====================
DATA_DIR = "./data"                # 数据存放文件夹
MAX_LIANBAN = 6                    # 最多统计到 6 连板
EXCLUDE_EXCHANGES = ["BJ"]         # 排除北交所
EXCLUDE_PREFIXES = ["300", "301", "688"]  # 排除创业板/科创板

os.makedirs(DATA_DIR, exist_ok=True)
# ============================================

def is_main_board(code, name):
    """只保留主板：排除 300/301/688 开头、北交所、ST"""
    for prefix in EXCLUDE_PREFIXES:
        if str(code).startswith(prefix):
            return False
    if str(code).startswith("8") or str(code).startswith("4"):
        return False
    if "ST" in str(name).upper():
        return False
    return True

def is_new_stock(code, trade_date):
    """排除上市不满 120 天的次新股"""
    cache_file = os.path.join(DATA_DIR, "list_dates.csv")
    cache = pd.DataFrame(columns=["code", "list_date"])
    if os.path.exists(cache_file):
        cache = pd.read_csv(cache_file, dtype={"code": str})

    code_str = str(code)
    if code_str in cache["code"].values:
        list_date_str = cache.loc[cache["code"] == code_str, "list_date"].values[0]
    else:
        try:
            info = ak.stock_individual_info_em(symbol=code_str)
            list_date_str = None
            for _, row in info.iterrows():
                if row["item"] == "上市时间":
                    list_date_str = str(row["value"])
                    break
            new_row = pd.DataFrame([{"code": code_str, "list_date": list_date_str}])
            cache = pd.concat([cache, new_row], ignore_index=True)
            cache.to_csv(cache_file, index=False)
        except:
            return False  # 拿不到上市日期就不排除

    if not list_date_str or list_date_str == "nan":
        return False
    try:
        list_date = pd.to_datetime(list_date_str)
        current = pd.to_datetime(trade_date)
        return (current - list_date).days < 120
    except:
        return False

def get_lianban_stocks(date, lianban_num):
    """获取某天某连板数的股票（主板、非ST、非次新）"""
    try:
        df = ak.stock_zt_pool_em(date=date)
        if df is None or len(df) == 0:
            return pd.DataFrame(columns=["ts_code", "name", "连板数"])
        # 筛选连板数
        df = df[df["连板数"] == lianban_num].copy()
        if len(df) == 0:
            return pd.DataFrame(columns=["ts_code", "name", "连板数"])
        # 主板过滤
        df["is_main"] = df.apply(lambda r: is_main_board(r["代码"], r["名称"]), axis=1)
        df = df[df["is_main"]]
        # 次新过滤
        df["is_new"] = df.apply(lambda r: is_new_stock(r["代码"], date), axis=1)
        df = df[~df["is_new"]]
        result = pd.DataFrame({
            "ts_code": df["代码"].astype(str),
            "name": df["名称"].astype(str),
            "连板数": lianban_num
        })
        return result
    except Exception as e:
        print(f"获取 {date} {lianban_num}连板失败: {e}")
        return pd.DataFrame(columns=["ts_code", "name", "连板数"])

def get_next_day_chg(code, base_date):
    """获取次日涨跌幅"""
    try:
        start = (pd.to_datetime(base_date) + timedelta(days=1)).strftime("%Y%m%d")
        end = (pd.to_datetime(base_date) + timedelta(days=5)).strftime("%Y%m%d")
        hist = ak.stock_zh_a_hist(symbol=code, period="daily", start_date=start, end_date=end, adjust="qfq")
        if hist is None or len(hist) == 0:
            return {"next_date": None, "pct_chg": None, "status": "无数据"}
        last = hist.iloc[-1]
        pct = float(last["涨跌幅"])
        if pct > 0:
            status = "上涨"
        elif pct < 0:
            status = "下跌"
        else:
            status = "平盘"
        return {"next_date": str(last["日期"]), "pct_chg": round(pct, 2), "status": status}
    except:
        return {"next_date": None, "pct_chg": None, "status": "获取失败"}

def calc_stats(date, lianban_num):
    """计算某天某连板的晋级统计"""
    stocks = get_lianban_stocks(date, lianban_num)
    if len(stocks) == 0:
        return {"日期": date, "连板数": lianban_num, "股票总数": 0, "上涨数": 0, "下跌数": 0,
                "平盘数": 0, "无数据数": 0, "上涨比例": 0, "上涨/下跌比": "N/A", "平均涨跌幅": 0}
    up = down = flat = nodata = 0
    total_pct = 0
    for _, row in stocks.iterrows():
        res = get_next_day_chg(row["ts_code"], date)
        if res["status"] == "上涨":
            up += 1
            total_pct += res["pct_chg"] or 0
        elif res["status"] == "下跌":
            down += 1
            total_pct += res["pct_chg"] or 0
        elif res["status"] == "平盘":
            flat += 1
        else:
            nodata += 1
    valid = up + down + flat
    up_ratio = round(up / valid * 100, 2) if valid > 0 else 0
    avg_pct = round(total_pct / valid, 2) if valid > 0 else 0
    up_down_ratio = f"1:{round(down/up,2)}" if up > 0 else ("全跌" if down > 0 else "N/A")
    return {"日期": date, "连板数": lianban_num, "股票总数": len(stocks), "上涨数": up,
            "下跌数": down, "平盘数": flat, "无数据数": nodata, "上涨比例": up_ratio,
            "上涨/下跌比": up_down_ratio, "平均涨跌幅": avg_pct}

def run_today():
    today = datetime.now().strftime("%Y%m%d")
    print(f"开始统计 {today} 及之前 5 个交易日的连板晋级情况...\n")
    # 获取最近 5 个交易日（不含今天，因为今天还没收盘）
    try:
        cal = ak.tool_trade_date_hist_sina()
        cal["trade_date"] = pd.to_datetime(cal["trade_date"])
        end_dt = pd.to_datetime(today)
        dates = cal[cal["trade_date"] <= end_dt]["trade_date"].unique()
        dates = sorted(dates, reverse=True)
        recent_dates = [d.strftime("%Y%m%d") for d in dates if d.strftime("%Y%m%d") != today][:5]
    except:
        # 降级：往前推 5 个工作日
        recent_dates = []
        d = pd.to_datetime(today) - timedelta(days=1)
        while len(recent_dates) < 5:
            if d.weekday() < 5:
                recent_dates.append(d.strftime("%Y%m%d"))
            d -= timedelta(days=1)

    rows = []
    for dt in recent_dates:
        print(f"正在处理 {dt}...")
        for num in range(2, MAX_LIANBAN + 1):
            stat = calc_stats(dt, num)
            rows.append(stat)
            if stat["股票总数"] > 0:
                print(f"  {num}连板: {stat['股票总数']}只, 上涨比例{stat['上涨比例']}%")

    df = pd.DataFrame(rows)
    csv_path = os.path.join(DATA_DIR, "summary.csv")
    if os.path.exists(csv_path):
        old = pd.read_csv(csv_path)
        df = pd.concat([old, df], ignore_index=True)
        df = df.drop_duplicates(subset=["日期", "连板数"], keep="last")
    df.to_csv(csv_path, index=False)
    print(f"\n数据已保存到 {csv_path}")
    print("✅ 完成！")

if __name__ == "__main__":
    run_today()