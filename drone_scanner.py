"""無人機戰略偵察系統 (ETF 航道導引 + 籌碼疊加版)"""

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

    # 🚀 航道過濾：只鎖定 ETF 星門陣列中存在的標的，大幅減少請求數量！
    target_codes = ETF_ARMORY.keys() if ETF_ARMORY else mapping.keys()
    
    for code in target_codes:
        if code in mapping:
            # 這裡簡化處理：為了極速，雙軌代號都加入集束轟炸，yfinance 會自動忽略無效的
            valid_tickers.append(f"{code}.TW")
            valid_tickers.append(f"{code}.TWO")

    return mapping, valid_tickers

def evaluate_local_data(ticker: str, df: pd.DataFrame, name: str) -> dict:
    try:
        df = df.dropna(subset=['Close'])
        if len(df) < 20: return None

        last_close = float(df['Close'].iloc[-1])
        vol_5d_avg = df['Volume'].tail(5).mean()
        
        # 由於已經有 ETF 護航，放寬流動性限制至 300 張
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

        is_primary = (today_low <= pullback_zone) and (last_close > defense_zone)
        is_standby = not is_primary and ((today_low - pullback_zone) / pullback_zone <= 0.03) and (last_close > defense_zone)

        # === 🚀 換股預警：爆量攻擊偵測 ===
        vol_today = float(df['Volume'].iloc[-1])
        vol_20d_avg = float(df['Volume'].tail(20).mean())
        vol_ratio = vol_today / vol_20d_avg if vol_20d_avg > 0 else 1
        
        is_front_run = vol_ratio >= 1.5 and last_close > float(df['Close'].rolling(20).mean().iloc[-1])
        
        # 只要符合 SOP 或是出現爆量預警，就納入雷達
        if not (is_primary or is_standby or is_front_run): return None

        code = ticker.split(".")[0]
        has_armor = code in GOLDEN_WHITELIST_CODES
        etf_list = ETF_ARMORY.get(code, [])

        # === 🏆 戰術權重評分系統 (含法人籌碼疊加) ===
        ma20 = float(df['Close'].rolling(20).mean().iloc[-1])
        ma60 = float(df['Close'].rolling(60).mean().iloc[-1]) if len(df)>=60 else ma20
        
        score = 50
        dist_pct = abs(today_low - pullback_zone) / pullback_zone
        score += max(0, 20 - (dist_pct * 100 * 4))
        if ma20 > ma60: score += 10
        if last_close > ma20: score += 5
        if vol_today < vol_20d_avg: score += 10 # 量縮洗盤

        # 🛡️ 護甲加分
        if has_armor: score += 15
        
        # 🧬 ETF 籌碼疊加加分 (每被一檔 ETF 納入 +5 分，上限 20 分)
        etf_multiplier = min(len(etf_list) * 5, 20)
        score += etf_multiplier

        score = min(99, int(score))
        
        # UI 標籤組裝
        tags_html = ""
        if has_armor: tags_html += "<span style='color:#06d6a0'>🛡️體質護甲</span> "
        if etf_list: tags_html += f"<span style='color:#c8d4f0'>🛸ETF疊加x{len(etf_list)}</span> "
        if is_front_run: tags_html += "<span style='color:#ff6b9d'>🚀抬轎預警</span> "
        
        etf_str = "、".join([e.split("】")[0].replace("【", "") for e in etf_list]) if etf_list else "無"
        tooltip = f"戰術評分: {score}分<br>量比: {vol_ratio:.1f}x<br>戰略佈局: {pullback_zone:.2f}<br>防禦: {defense_zone:.2f}<br><br><b>法人航道:</b><br>{etf_str}<br><br>{tags_html}"
        
        if is_front_run: state_str = "🚀抬轎預警"
        elif is_primary: state_str = "🎯精準打擊"
        else: state_str = "👁️戰略監控"
        
        # 標示出最強護甲
        if has_armor and len(etf_list) >= 2: state_str += " 👑"

        return {
            "code": code,
            "name": name,
            "price": last_close,
            "chg": chg,
            "score": score,
            "tooltip": tooltip,
            "state_label": state_str,
            "css_class": "state-bull" if is_front_run else ("state-layout" if is_primary else "state-wait"),
            "category": "primary" if (is_primary or is_front_run) else "standby"
        }

    except Exception:
        return None

def run_scan():
    t0 = time.time()
    print("🛸 [無人機戰略系統] 啟動 ETF 航道集束轟炸掃描...")
    
    mapping, valid_tickers = fetch_market_targets()
    print(f"📡 鎖定 ETF 航道兵力總數：{len(valid_tickers)//2} 檔。")
    
    if not valid_tickers: return

    try:
        df_bulk = yf.download(valid_tickers, period="3mo", group_by='ticker', threads=True, progress=False, auto_adjust=False)
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
                # 避免 .TW 與 .TWO 重複加入
                if not any(r['code'] == res['code'] for r in results):
                    results.append(res)

    t1 = time.time()
    print(f"✅ ETF 航道戰術鑑賞完畢！極速耗時 {t1-t0:.1f} 秒。共鎖定 {len(results)} 檔伏兵。")

    if results:
        df_all = pd.DataFrame(results)
        df_all = df_all.sort_values(by="score", ascending=False)
        df_primary = df_all[df_all['category'] == 'primary']
        df_standby = df_all[df_all['category'] == 'standby']
        df_primary.to_csv("tactical_targets.csv", index=False)
        df_standby.to_csv("tactical_standby.csv", index=False)
        print(f"📁 情報箱已加密封裝：精準打擊區 {len(df_primary)} 檔，戰略監控區 {len(df_standby)} 檔。")
    else:
        pd.DataFrame().to_csv("tactical_targets.csv", index=False)
        pd.DataFrame().to_csv("tactical_standby.csv", index=False)
        print("📁 掃描結束。今日 ETF 航道內無符合 SOP 條件之潛力伏兵。")

if __name__ == "__main__":
    run_scan()