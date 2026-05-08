"""行動作戰指揮中心：雙棲極速版 (個股快搜 + 伏兵雷達)"""

import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import urllib3
import os
import json
import re
import subprocess

st.set_page_config(page_title="行動指揮中心", layout="centered", initial_sidebar_state="collapsed")
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

st.markdown("""
    <style>
    .stApp { background-color: #050505; color: #E0E0E0; }
    .mobile-card { background: rgba(20, 20, 25, 0.85); border: 1px solid rgba(255,191,0,0.3); border-radius: 12px; padding: 15px; margin-bottom: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.5); }
    .radar-card { background: rgba(255, 255, 255, 0.05); border-left: 4px solid #FFBF00; border-radius: 8px; padding: 12px; margin-bottom: 10px; display: flex; flex-direction: column; }
    .m-title { font-size: 1.1rem; font-weight: bold; color: #FFBF00; margin-bottom: 10px; border-bottom: 1px solid rgba(255,191,0,0.2); padding-bottom: 5px; }
    .m-price-box { display: flex; justify-content: space-between; align-items: flex-end; margin-bottom: 10px; }
    .glow-text { color: #FFBF00; font-size: 1.6rem; font-weight: 900; text-shadow: 0 0 8px rgba(255, 191, 0, 0.5); }
    .m-tag { display: inline-block; padding: 2px 6px; border-radius: 4px; font-size: 0.75rem; font-weight: bold; margin-right: 5px; margin-bottom: 5px; }
    .tag-armor { background: rgba(6, 214, 160, 0.2); color: #06d6a0; border: 1px solid #06d6a0; }
    .tag-etf { background: rgba(124, 92, 255, 0.2); color: #c8d4f0; border: 1px solid #7c5cff; }
    .level-row { display: flex; justify-content: space-between; margin-bottom: 8px; font-size: 0.9rem; }
    .level-chase { color: #ff6b9d; font-weight: bold; }
    .level-pull { color: #ffd166; font-weight: bold; }
    .level-perfect { color: #06d6a0; font-weight: bold; }
    </style>
""", unsafe_allow_html=True)

@st.cache_data(ttl=120)
def load_ohlc(symbol: str, period: str) -> pd.DataFrame | None:
    try:
        df = yf.download(symbol, period=period, interval="1d", progress=False, auto_adjust=False)
        if df is None or df.empty: return None
        if isinstance(df.columns, pd.MultiIndex): df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
        return df.dropna(subset=['Close'])
    except: return None

def resolve_ticker(code: str) -> str | None:
    for m in ["TW", "TWO"]:
        sym = f"{code}.{m}"
        df = load_ohlc(sym, "5d")
        if df is not None and not df.empty: return sym
    return None

def load_armory_data():
    has_armor = set()
    etf_map = {}
    if os.path.exists("golden_whitelist.csv"):
        has_armor = set(pd.read_csv("golden_whitelist.csv")['code'].astype(str))
    if os.path.exists("etf_armory.json"):
        with open("etf_armory.json", "r", encoding="utf-8") as f:
            etf_map = json.load(f)
    return has_armor, etf_map

def tactical_levels(df: pd.DataFrame) -> dict:
    seg20 = df.tail(min(20, len(df)))
    hi20, lo20 = float(seg20["High"].max()), float(seg20["Low"].min())
    span = max(hi20 - lo20, abs(float(df["Close"].iloc[-1]) * 0.02), 1e-6)
    ma20 = float(df["Close"].rolling(20, min_periods=3).mean().iloc[-1]) if len(df)>=20 else None
    ma60 = float(df["Close"].rolling(60, min_periods=10).mean().iloc[-1]) if len(df)>=60 else None
    return {
        "多頭突擊位": hi20, "戰略佈局帶": lo20 + 0.382 * span, 
        "關鍵防禦區": lo20 + 0.236 * span, "收盤": float(df["Close"].iloc[-1]),
        "MA20": ma20, "MA60": ma60
    }

def normalize_stock_input(raw: str) -> str | None:
    s = re.sub(r"\s+", "", raw.strip())
    m = re.match(r"^(\d{4})", s)
    return m.group(1) if m else (s if re.match(r"^\d{4}$", s) else None)

st.markdown("<h3 style='text-align: center; color: #E0E0E0;'>📱 行動作戰指揮中心</h3>", unsafe_allow_html=True)

tab1, tab2 = st.tabs(["🎯 單兵快搜", "🛸 伏兵雷達"])

with tab1:
    target_raw = st.text_input("鎖定目標代號", placeholder="例如: 2330", label_visibility="collapsed")
    target_code = normalize_stock_input(target_raw) if target_raw else None

    if target_code:
        with st.spinner("📡 衛星連線中..."):
            sym = resolve_ticker(target_code)
            if not sym: st.error(f"🚨 無法鎖定座標 {target_code}。")
            else:
                df = load_ohlc(sym, "1y")
                if df is None or len(df) < 60: st.warning("⚠️ 歷史資料不足。")
                else:
                    levels = tactical_levels(df)
                    last_price = levels["收盤"]
                    prev_price = float(df["Close"].iloc[-2])
                    chg_pct = (last_price - prev_price) / prev_price * 100
                    vol_today = int(df['Volume'].iloc[-1]) // 1000
                    
                    armor_set, etf_data = load_armory_data()
                    is_armored = target_code in armor_set
                    etf_list = etf_data.get(target_code, [])

                    c_color = "#ff4d4d" if chg_pct < 0 else "#06d6a0"
                    c_sign = "" if chg_pct < 0 else "+"
                    
                    tags_html = ""
                    if is_armored: tags_html += '<span class="m-tag tag-armor">💎 體質護甲</span>'
                    if etf_list: tags_html += f'<span class="m-tag tag-etf">🛸 {len(etf_list)}檔 ETF 護航</span>'

                    st.markdown(f"""
                    <div class="mobile-card">
                        <div class="m-title">{target_code} 戰情總覽</div>
                        <div class="m-price-box">
                            <div><div class="glow-text">{last_price:.2f}</div></div>
                            <div style="text-align:right;">
                                <div style="color:{c_color}; font-size:1.2rem; font-weight:bold;">{c_sign}{chg_pct:.2f}%</div>
                                <div style="font-size:0.8rem; color:#8b9bb4;">量: {vol_today:,} 張</div>
                            </div>
                        </div>
                        <div>{tags_html}</div>
                    </div>
                    """, unsafe_allow_html=True)

                    st.markdown(f"""
                    <div class="mobile-card">
                        <div class="m-title">SOP 戰略點位</div>
                        <div class="level-row"><span>多頭衝擊</span> <span class="level-chase">{levels['多頭突擊位']:.2f}</span></div>
                        <div class="level-row"><span>戰略佈局</span> <span class="level-pull">{levels['戰略佈局帶']:.2f}</span></div>
                        <div class="level-row"><span>關鍵防禦</span> <span class="level-perfect">{levels['關鍵防禦區']:.2f}</span></div>
                    </div>
                    """, unsafe_allow_html=True)

                    st.markdown('<div class="mobile-card"><div class="m-title">戰力透視</div>', unsafe_allow_html=True)
                    recent_chg = (last_price - df['Close'].iloc[-20]) / df['Close'].iloc[-20] * 100
                    score_momentum = min(max(50 + recent_chg * 2, 0), 100)
                    ma20, ma60 = levels['MA20'], levels['MA60']
                    score_trend = 100 if last_price > ma20 > ma60 else (70 if last_price > ma60 else 30)
                    dist = (last_price - levels['關鍵防禦區']) / levels['關鍵防禦區'] * 100
                    score_defense = min(max(100 - abs(dist)*4, 0), 100)
                    
                    categories = ['動能', '趨勢', '防禦', '動能']
                    values = [score_momentum, score_trend, score_defense, score_momentum]
                    
                    fig_radar = go.Figure(data=go.Scatterpolar(r=values, theta=categories, fill='toself', fillcolor='rgba(255, 191, 0, 0.4)', line=dict(color='#FFBF00', width=2)))
                    fig_radar.update_layout(polar=dict(radialaxis=dict(visible=False, range=[0, 100]), angularaxis=dict(color='white')), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', margin=dict(l=20, r=20, t=10, b=10), height=220)
                    st.plotly_chart(fig_radar, use_container_width=True, config={'displayModeBar': False})
                    st.markdown('</div>', unsafe_allow_html=True)

with tab2:
    if st.button("🚀 啟動無人機全域掃描", type="primary", use_container_width=True):
        with st.spinner("🛸 無人機升空中... (約需 5~10 秒)"):
            try:
                import sys
                subprocess.run([sys.executable, "drone_scanner.py"], check=True)
                st.success("✅ 偵察任務完成！情報已更新。")
            except Exception as e: st.error(f"🚨 無人機升空失敗：{e}")
                
    st.markdown("---")

    def render_radar_list(csv_file, title, empty_msg):
        if not os.path.exists(csv_file) or os.path.getsize(csv_file) == 0:
            st.info(empty_msg)
            return
        try:
            df_radar = pd.read_csv(csv_file)
            if df_radar.empty: st.info(empty_msg); return
            st.markdown(f"#### {title}")
            for _, row in df_radar.iterrows():
                c_color = "#ff4d4d" if row.get('chg', 0) < 0 else "#06d6a0"
                c_sign = "" if row.get('chg', 0) < 0 else "+"
                st.markdown(f"""
                <div class="radar-card">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <span style="font-size:1.1rem; font-weight:bold; color:#fff;">{row.get('code')} {row.get('name')}</span>
                        <span style="color:{c_color}; font-weight:bold; font-size:1.1rem;">{c_sign}{row.get('chg', 0):.2f}%</span>
                    </div>
                    <div style="display:flex; justify-content:space-between; margin-top:5px;">
                        <span style="color:#FFBF00; font-size:1rem; font-family:monospace;">{row.get('price', 0):.2f}</span>
                        <span style="font-size:0.8rem; background:rgba(255,255,255,0.1); padding:2px 6px; border-radius:4px;">{row.get('state_label')} | 評分:{int(row.get('score', 0))}</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)
        except Exception as e: st.error(f"解析 {csv_file} 失敗")

    render_radar_list("tactical_targets.csv", "🔥 第一梯隊 (精準打擊)", "🟢 目前無達標伏兵。")
    render_radar_list("tactical_standby.csv", "👁️ 第二梯隊 (戰略備選)", "🟢 目前無備選伏兵。")
