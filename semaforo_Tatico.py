# semaforo_tatico_app.py
# Requisitos: streamlit, yfinance, pandas, numpy
# Execute com: streamlit run semaforo_tatico_app.py
import os
import yfinance as yf
import streamlit as st

# Pegar porta de ambiente (usado por paineis online)
PORT = int(os.environ.get("PORT", "8501"))
st.set_page_config(page_title="Semáforo Tático - ES, DXY, US10Y", page_icon="🚦", layout="wide")

# ----------------------------------
# Configurações
# ----------------------------------
TICKERS = {
    "S&P 500 Futuro (ES)": "ES=F",      # E-mini S&P 500 (CME)
    "DXY Futuro (DX)": "DX=F",          # ICE Dollar Index futures (proxy pro DXY)
    "US10Y Yield (^TNX)": "^TNX",       # 10-year Treasury yield * 100
}

st.title("🚦 Semáforo Tático: ES (S&P Fut), DXY (DX=F) e US10Y (^TNX)")
st.caption("Green = ES↑, DXY↓, US10Y↓ | Yellow = misto | Red = ES↓, DXY↑, US10Y↑")

def get_quote(ticker: str):
    try:
        data = yf.Ticker(ticker).history(period="1d", interval="1m")
        if data.empty:
            return None
        last = data["Close"].iloc[-1]
        prev = data["Close"].iloc[0]
        chg = (last/prev - 1.0) * 100.0
        return {
            "last": float(last),
            "prev": float(prev),
            "pct": float(chg),
            "series": data["Close"]
        }
    except Exception as e:
        return {"error": str(e)}

def tnx_to_pct(x):
    return x / 10.0  # ^TNX vem multiplicado por 10

# ----------------------------------
# Coleta
# ----------------------------------
quotes = {name: get_quote(tk) for name, tk in TICKERS.items()}

# Converter ^TNX para %
if quotes.get("US10Y Yield (^TNX)") and quotes["US10Y Yield (^TNX)"]:
    if "last" in quotes["US10Y Yield (^TNX)"]:
        quotes["US10Y Yield (^TNX)"]["last_pct"] = tnx_to_pct(quotes["US10Y Yield (^TNX)"]["last"])
    else:
        quotes["US10Y Yield (^TNX)"]["last_pct"] = None

# ----------------------------------
# Semáforo
# ----------------------------------
def semaphore_state(es_pct, dx_pct, tnx_pct):
    if es_pct is None or dx_pct is None or tnx_pct is None:
        return "⚪ Neutro", "Dados incompletos"

    if es_pct > 0 and dx_pct < 0 and tnx_pct < 0:
        return "🟢 Green", "ES↑, DX↓, US10Y↓ → WIN↑ / WDO↓"
    elif es_pct < 0 and dx_pct > 0 and tnx_pct > 0:
        return "🔴 Red", "ES↓, DX↑, US10Y↑ → WIN↓ / WDO↑"
    else:
        return "🟡 Yellow", "Sinais mistos — use VWAP/EMA9 para decidir"

# Usar .get() para não dar erro
es_pct = quotes["S&P 500 Futuro (ES)"].get("pct") if quotes.get("S&P 500 Futuro (ES)") else None
dx_pct = quotes["DXY Futuro (DX)"].get("pct") if quotes.get("DXY Futuro (DX)") else None
tnx_pct = quotes["US10Y Yield (^TNX)"].get("pct") if quotes.get("US10Y Yield (^TNX)") else None

state, msg = semaphore_state(es_pct, dx_pct, tnx_pct)

st.subheader(f"Status: {state}")
st.write(msg)

# ----------------------------------
# Painel de cotações
# ----------------------------------
def fmt(x):
    return "—" if x is None else f"{x:,.4f}"

col1, col2, col3 = st.columns(3)

with col1:
    q = quotes.get("S&P 500 Futuro (ES)", {})
    st.metric("ES=F (S&P Fut)", value=fmt(q.get("last")), delta=f"{q.get('pct', 0):+.2f}%")

with col2:
    q = quotes.get("DXY Futuro (DX)", {})
    st.metric("DX=F (Dólar Fut.)", value=fmt(q.get("last")), delta=f"{q.get('pct', 0):+.2f}%")

with col3:
    q = quotes.get("US10Y Yield (^TNX)", {})
    last = q.get("last_pct")
    st.metric("US10Y Yield", value=("—" if last is None else f"{last:.2f}%"), delta=f"{q.get('pct', 0):+.2f}%")

st.divider()

# ----------------------------------
# Gráficos intraday
# ----------------------------------
c1, c2, c3 = st.columns(3)
with c1:
    s = quotes.get("S&P 500 Futuro (ES)", {}).get("series")
    if s is not None:
        st.line_chart(s, height=200)
with c2:
    s = quotes.get("DXY Futuro (DX)", {}).get("series")
    if s is not None:
        st.line_chart(s, height=200)
with c3:
    s = quotes.get("US10Y Yield (^TNX)", {}).get("series")
    if s is not None:
        s = s.apply(lambda v: v/10.0)
        st.line_chart(s, height=200)
