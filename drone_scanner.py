"""無人機戰略偵察系統 (ETF 航道導引 + 籌碼疊加 + 法人反攻 + 核心戰區升級版)"""

import os
import requests
import json
import time
import warnings
import pandas as pd
import yfinance as yf
from datetime import datetime

warnings.filterwarnings("ignore", category=FutureWarning)

# === 🛡️ 戰前準備一：掛載黃金兵器庫 (基本面白名單) ===
GOLDEN_WHITELIST_CODES = set()
try:
    if os.path.exists("golden_whitelist.csv"):
        df_wl = pd.read_csv("golden_whitelist.csv")
        GOLDEN_WHITELIST_CODES = set(df_wl['code'].astype(str))
        print(f"🛡️ 成功掛載【黃金兵器庫】：共 {len(GOLDEN_WHITELIST_CODES)} 檔護甲標的已上膛。")
except Exception as e:
    print(f"🚨 兵器庫讀取失敗：{e}")

# === 🛸 戰前準備二：掛載 ETF 星門陣列 (航道引導) ===
ETF_ARMORY = {}
try:
    if os.path.exists("etf_armory.json"):
        with open("etf_armory.json", "r", encoding="utf-8") as f:
            ETF_ARMORY = json.load(f)
        print(f"🌌 成功掛載【ETF 星門陣列】：鎖定 {len(ETF_ARMORY)} 檔法人護航標的。")
    else:
        print("⚠️ 尚未偵測到 etf_armory.json，請先執行 etf_armory.py 建立航道。")
except Exception as e:
    print(f"🚨 星門陣列讀取失敗：{e}")

def fetch_market_targets() -> tuple[dict, list]:
    mapping = {}
    valid_tickers = []
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    
    try:
        req_twse = requests.get("https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL", headers=headers, timeout=10)
        if req_twse.status_code == 200:
            for row in req_twse.json():
                c = row.get("Code", "").strip()
                n = row.get("Name", "").replace("　", "").replace(" ", "").replace("- KY", "-KY")
                if c and n and len(c) == 4 and c.isdigit(): mapping[c] = n
    except: pass

    try:
        req_tpex = requests.get("https://www.tpex.org.tw/openapi/v1/tpex_mainboard_quotes", headers=headers, timeout=10)
        if req_tpex.status_code == 200:
            for row in req_tpex.json():
                c = row.get("SecuritiesCompanyCode", "").strip()
                n = row.get("CompanyName", "").replace("　", "").replace(" ", "").replace("- KY", "-KY")
                if c and n and len(c) == 4 and c.isdigit(): mapping[c] = n
    except: pass

    # 🚀 擴大偵蒐：將 ETF 名單與黃金白名單聯集
    combined_targets = set(ETF_ARMORY.keys()).union(GOLDEN_WHITELIST_CODES)
    target_codes = combined_targets if combined_targets else mapping.keys()
    
    for code in target_codes:
        if code in mapping:
            valid_tickers.append(f"{code}.TW")
            valid_tickers.append(f"{code}.TWO")

    return mapping, valid_tickers

def evaluate_local_data(ticker: str, df: pd.DataFrame, name: str) -> dict:
    try:
        df = df.dropna(subset=['Close'])
        if len(df) < 20: return None

        code = ticker.split(".")[0]
        has_armor = code in GOLDEN_WHITELIST_CODES
        etf_list = ETF_ARMORY.get(code, [])

        # === 💎 [新增] 動態辨識：核心戰區 ===
        # 條件：被 3 檔以上 ETF 納入，或擁有基本面白名單且至少有 1 檔 ETF 護航
        is_core_warzone = (len(etf_list) >= 3) or (has_armor and len(etf_list) >= 1)

        last_close = float(df['Close'].iloc[-1])
        vol_5d_avg = df['Volume'].tail(5).mean()
        
        if last_close < 10.0 or vol_5d_avg < 300_000: return None 

        seg20 = df.tail(20)
        hi20, lo20 = float(seg20['High'].max()), float(seg20['Low'].min())
        span = hi20 - lo20
        if span == 0: return None

        pullback_zone = lo20 + 0.382 * span
        defense_zone = lo20 + 0.236 * span
        
        today_low = float(df['Low'].iloc[-1])
        prev_close = float(df['Close'].iloc[-2])
        chg = (last_close - prev_close) / prev_close * 100 if prev_close else 0.0

        # 取得關鍵均線數據
        ma5 = float(df['Close'].rolling(5).mean().iloc[-1])
        ma20 = float(df['Close'].rolling(20).mean().iloc[-1])
        prev_ma20 = float(df['Close'].rolling(20).mean().iloc[-2])
        ma60 = float(df['Close'].rolling(60).mean().iloc[-1]) if len(df)>=60 else ma20

        # === 🎯 傳統 SOP 陣地 (黃金分割回測) ===
        is_primary = (today_low <= pullback_zone) and (last_close > defense_zone)
        is_standby = not is_primary and ((today_low - pullback_zone) / pullback_zone <= 0.03) and (last_close > defense_zone)

        # === 💻 [新增] 核心戰區免死金牌 (季線之上強制留存) ===
        # 無視 0.382 支撐條件，只要是核心戰區且站穩 60MA，強制保留在監控梯隊
        is_core_standby = not is_primary and is_core_warzone and (last_close > ma60)

        # === 🚀 換股預警：爆量攻擊偵測 ===
        vol_today = float(df['Volume'].iloc[-1])
        vol_20d_avg = float(df['Volume'].tail(20).mean())
        vol_ratio = vol_today / vol_20d_avg if vol_20d_avg > 0 else 1
        
        is_front_run = (vol_ratio >= 1.5) and (last_close > ma20) and (chg > 2.0)
        
        # === 🔥 法人反攻 (ETF 豁免權)：抓破底翻與穩健推升 ===
        is_break_bottom_up = (prev_close < prev_ma20) and (last_close > ma20) and (chg > 1.5)
        is_etf_push = (len(etf_list) > 0) and (last_close > ma5) and (last_close > ma20) and (chg > 1.5)
        is_rebound = is_break_bottom_up or is_etf_push

        # 只要符合任一條件，就納入雷達 (加入 is_core_standby)
        if not (is_primary or is_standby or is_core_standby or is_front_run or is_rebound): return None

        # === 🏆 戰術權重評分系統 ===
        score = 50
        dist_pct = abs(today_low - pullback_zone) / pullback_zone
        score += max(0, 20 - (dist_pct * 100 * 4))
        if ma20 > ma60: score += 10
        if last_close > ma20: score += 5
        if vol_today < vol_20d_avg: score += 10

        if has_armor: score += 15
        etf_multiplier = min(len(etf_list) * 5, 20)
        score += etf_multiplier
        
        # 核心重兵額外加權，確保排序靠前
        if is_core_warzone: score += 10

        score = min(99, int(score))
        
        # UI 標籤組裝與狀態分流
        tags_html = ""
        if is_core_warzone: tags_html += "<span style='color:#00d2d3; font-weight:bold;'>💻核心戰區</span> "
        if has_armor: tags_html += "<span style='color:#06d6a0'>🛡️體質護甲</span> "
        if etf_list: tags_html += f"<span style='color:#c8d4f0'>🛸ETF疊加x{len(etf_list)}</span> "
        
        if is_front_run:
            state_str = "🚀抬轎預警"
            css_class = "state-bull"
            category = "primary"
            tags_html += "<span style='color:#ff6b9d'>🚀抬轎</span> "
        elif is_rebound:
            state_str = "🔥法人反攻"
            css_class = "state-bull"
            category = "primary"
            tags_html += "<span style='color:#ff9f43'>🔥反攻</span> "
        elif is_primary:
            state_str = "🎯精準打擊"
            css_class = "state-layout"
            category = "primary"
        elif is_standby or is_core_standby:
            state_str = "👁️戰略監控"
            css_class = "state-wait"
            category = "standby"
        else:
            state_str = "👁️戰略監控"
            css_class = "state-wait"
            category = "standby"
        
        if has_armor and len(etf_list) >= 2: state_str += " 👑"

        etf_str = "、".join([e.split("】")[0].replace("【", "") for e in etf_list]) if etf_list else "無"
        tooltip = f"戰術評分: {score}分<br>量比: {vol_ratio:.1f}x<br>戰略佈局: {pullback_zone:.2f}<br>防禦: {defense_zone:.2f}<br><br><b>法人航道:</b><br>{etf_str}<br><br>{tags_html}"
        
        return {
            "code": code,
            "name": name,
            "price": last_close,
            "chg": chg,
            "score": score,
            "tooltip": tooltip,
            "state_label": state_str,
            "css_class": css_class,
            "category": category
        }

    except Exception:
        return None

def run_scan():
    t0 = time.time()
    print("🛸 [無人機戰略系統] 啟動 ETF 航道集束轟炸掃描 (法人反攻 + 核心戰區升級版)...")
    
    mapping, valid_tickers = fetch_market_targets()
    print(f"📡 鎖定戰略兵力總數：{len(valid_tickers)//2} 檔。")
    
    if not valid_tickers: return

    try:
        df_bulk = yf.download(valid_tickers, period="3mo", group_by='ticker', threads=True, progress=False, auto_adjust=True)
    except Exception as e:
        print(f"🚨 集束下載遭受阻擊：{e}")
        return
    
    results = []
    
    if isinstance(df_bulk.columns, pd.MultiIndex):
        available_tickers = df_bulk.columns.get_level_values(0).unique()
        for ticker in available_tickers:
            if ticker not in valid_tickers: continue
            df_single = df_bulk[ticker].copy()
            code = ticker.split(".")[0]
            name = mapping.get(code, f"未知({code})")
            
            res = evaluate_local_data(ticker, df_single, name)
            if res:
                if not any(r['code'] == res['code'] for r in results):
                    results.append(res)

    t1 = time.time()
    print(f"✅ 戰術鑑賞完畢！極速耗時 {t1-t0:.1f} 秒。共鎖定 {len(results)} 檔潛力目標。")

    if results:
        df_all = pd.DataFrame(results)
        df_all = df_all.sort_values(by="score", ascending=False)
        df_primary = df_all[df_all['category'] == 'primary']
        df_standby = df_all[df_all['category'] == 'standby']
        df_primary.to_csv("tactical_targets.csv", index=False)
        df_standby.to_csv("tactical_standby.csv", index=False)
        print(f"📁 情報箱已加密封裝：第一梯隊(打擊/反攻/預警) {len(df_primary)} 檔，第二梯隊(監控) {len(df_standby)} 檔。")
    else:
        pd.DataFrame().to_csv("tactical_targets.csv", index=False)
        pd.DataFrame().to_csv("tactical_standby.csv", index=False)
        print("📁 掃描結束。今日航道內無符合戰略條件之目標。")

if __name__ == "__main__":
    run_scan()