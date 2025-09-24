# semaforo_Tatico.py
# Requisitos: streamlit, yfinance, pandas, numpy
# Local:      streamlit run semaforo_Tatico.py
# Cloud:      streamlit run semaforo_Tatico.py --server.address=0.0.0.0 --server.port=$PORT
import os
import pandas as pd
import yfinance as yf
import streamlit as st

# Pegar porta de ambiente (usado por paineis online)
PORT = int(os.environ.get("PORT", "8501"))
st.set_page_config(page_title="Semáforo Tático - ES, DXY, US10Y", page_icon="🚦", layout="wide")

# ----------------------------------
# Configurações
# ----------------------------------
TICKERS = {
    "S&P 500 Futuro (ES)": "ES=F",   # se falhar, pode usar ^GSPC como proxy
    "DXY Futuro (DX)": "DX=F",       # se falhar, pode usar UUP (ETF do dólar)
    "US10Y Yield (^TNX)": "^TNX",    # ^TNX vem em décimos (41.50 => 4.15%)
}
REFRESH_SEC = 30

st.title("🚦 Semáforo Tático: ES (S&P Fut), DXY (DX=F) e US10Y (^TNX)")
st.caption("Green = ES↑, DXY↓, US10Y↓ | Yellow = misto | Red = ES↓, DXY↑, US10Y↑ | Orange = todos ↑")

# ----------------------------------
# Helpers robustos
# ----------------------------------
def safe_dict(x):
    return x if isinstance(x, dict) else {}

def tnx_to_pct(x):
    try:
        return float(x) / 10.0 if x is not None else None
    except Exception:
        return None

@st.cache_data(ttl=20)
def get_intraday(ticker: str):
    """Puxa 1d/1m do Yahoo. Retorna dict {last, prev, pct, series} ou {}."""
    try:
        data = yf.Ticker(ticker).history(period="1d", interval="1m", auto_adjust=False)
        if data is None or data.empty:
            return {}
        close = data["Close"].dropna()
        if close.empty:
            return {}
        last = float(close.iloc[-1])
        prev = float(close.iloc[0])
        pct = (last/prev - 1.0) * 100.0 if prev != 0 else 0.0
        return {"last": last, "prev": prev, "pct": pct, "series": close}
    except Exception:
        return {}

@st.cache_data(ttl=60)
def get_hist(ticker: str, days: int = 3):
    try:
        h = yf.Ticker(ticker).history(period=f"{days}d", interval="30m", auto_adjust=False)
        return h["Close"] if h is not None and not h.empty else None
    except Exception:
        return None

def semaphore_state(es_pct, dx_pct, tnx_pct):
    """Retorna (label, msg, win_hint, wdo_hint, key)"""
    if es_pct is None or dx_pct is None or tnx_pct is None:
        return "⚪ Neutro", "Dados incompletos — aguardando cotações.", "—", "—", "neutral"

    # Estados principais
    green  = (es_pct > 0 and dx_pct < 0 and tnx_pct < 0)
    red    = (es_pct < 0 and dx_pct > 0 and tnx_pct > 0)
    orange = (es_pct > 0 and dx_pct > 0 and tnx_pct >= 0)  # todos ↑ (US10Y >=0 para pegar +0,00%)
    purple = (es_pct < 0 and dx_pct < 0 and tnx_pct <= 0)  # todos ↓ (raro; útil para leitura)

    if green:
        return ("🟢 Green",
                "ES↑, DX↓, US10Y↓ → risco on clássico.",
                "WIN↑ (compras favorecidas; rompimentos com VWAP/EMA9 alinhados)",
                "WDO↓ (vendas favorecidas; perda de suportes com EMA9<VWAP)",
                "green")
    if red:
        return ("🔴 Red",
                "ES↓, DX↑, US10Y↑ → aversão a risco.",
                "WIN↓ (vendas favorecidas; repiques até VWAP)",
                "WDO↑ (compras favorecidas; rompimento de resistências)",
                "red")
    if orange:
        return ("🟠 Orange",
                "ES↑, DX↑, US10Y↑ → dólar/yields fortes anulam parte do S&P↑.",
                "WIN neutro/limitado (prefira confirmações; falhas em topo são comuns)",
                "WDO↑ (tendência de alta mais consistente)",
                "orange")
    if purple:
        return ("🟣 Purple",
                "ES↓, DX↓, US10Y↓ → sinais cruzados (bolsa cai, mas dólar/juros cedem).",
                "WIN precisa confirmação (queda pode perder tração se DXY/UST cedem)",
                "WDO↓ (pressão baixista pode dominar)",
                "purple")

    # Demais combinações → misto
    return ("🟡 Yellow",
            "Sinais mistos — priorize trades de faixa; deixe VWAP/EMA9 decidirem.",
            "WIN: operar range/mean reversion próximos ao VWAP",
            "WDO: idem; use DXY/US10Y como filtro",
            "yellow")

# ----------------------------------
# Coleta
# ----------------------------------
quotes = {name: safe_dict(get_intraday(tk)) for name, tk in TICKERS.items()}

es_pct  = safe_dict(quotes.get("S&P 500 Futuro (ES)")).get("pct")
dx_pct  = safe_dict(quotes.get("DXY Futuro (DX)")).get("pct")
tnx_q   = safe_dict(quotes.get("US10Y Yield (^TNX)"))
tnx_pct = tnx_q.get("pct")  # var intradiária (em pontos de ^TNX, suficiente para direção)
tnx_last_pct = tnx_to_pct(tnx_q.get("last"))

label, msg, win_hint, wdo_hint, key = semaphore_state(es_pct, dx_pct, tnx_pct)

# ----------------------------------
# Header: status
# ----------------------------------
st.subheader(f"Status: {label}")
st.write(msg)

# ----------------------------------
# Painel de cotações
# ----------------------------------
def fmt_num(x, nd=4):
    try:
        return f"{float(x):,.{nd}f}"
    except Exception:
        return "—"

col1, col2, col3 = st.columns(3)
with col1:
    q = safe_dict(quotes.get("S&P 500 Futuro (ES)"))
    st.metric("ES=F (S&P Fut)", value=fmt_num(q.get("last")), delta=f"{q.get('pct', 0):+.2f}%")
with col2:
    q = safe_dict(quotes.get("DXY Futuro (DX)"))
    st.metric("DX=F (Dólar Fut.)", value=fmt_num(q.get("last")), delta=f"{q.get('pct', 0):+.2f}%")
with col3:
    st.metric("US10Y Yield", value=("—" if tnx_last_pct is None else f"{tnx_last_pct:.2f}%"),
              delta=f"{tnx_pct or 0:+.2f}%")

st.divider()

# ----------------------------------
# Guia rápido (legenda): efeito no WIN/WDO
# ----------------------------------
with st.expander("📖 Legenda — Como cada leitura afeta WIN e WDO"):
    st.markdown("""
- **🟢 Green (ES↑, DXY↓, US10Y↓)** → **WIN↑** (compras), **WDO↓** (vendas).
- **🟠 Orange (todos ↑: ES↑, DXY↑, US10Y↑)** → **WIN neutro/limitado**, **WDO↑** (dólar favorecido).
- **🟡 Yellow (misto)** → operar **faixas**; use **VWAP/EMA9** e a faixa do **overnight** como filtro.
- **🔴 Red (ES↓, DXY↑, US10Y↑)** → **WIN↓** (vendas), **WDO↑** (compras).
- **🟣 Purple (todos ↓: ES↓, DXY↓, US10Y↓)** → quadro cruzado: **WDO↓** tende a prevalecer; **WIN** requer confirmação.
    """)

# ----------------------------------
# Gráficos intraday (opcionais)
# ----------------------------------
c1, c2, c3 = st.columns(3)
with c1:
    s = safe_dict(quotes.get("S&P 500 Futuro (ES)")).get("series")
    if s is not None:
        st.line_chart(s, height=180, use_container_width=True)
with c2:
    s = safe_dict(quotes.get("DXY Futuro (DX)")).get("series")
    if s is not None:
        st.line_chart(s, height=180, use_container_width=True)
with c3:
    s = tnx_q.get("series")
    if s is not None:
        st.line_chart(s.apply(lambda v: v/10.0), height=180, use_container_width=True)

st.caption("Dica: espere 10–15 min para o VWAP 'assentar' e valide rompimentos com volume acima da média.")

