"""
Nexiqo — Financial Intelligence Engine
Sample companies use real reported figures (screener.in / company filings).
Custom uploads use the standardized Excel template.
"""
import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
from io import BytesIO
from datetime import datetime

from sample_data import SAMPLE_COMPANIES, DEFAULT_PEERS
from parser import is_flexible_layout, build_standard_financials

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

st.set_page_config(page_title="Nexiqo | Financial Intelligence Engine", layout="wide", page_icon="📊")

# ---------------------------------------------------------------------------
# STYLING — match the Nexiqo dark/emerald brand
# ---------------------------------------------------------------------------
st.markdown("""
<style>
  .stApp { background-color: #05070E; color: #F0F4FA; }
  h1, h2, h3 { color: #ffffff !important; }
  [data-testid="stMetricValue"] { color: #12E19F; }
  [data-testid="stMetricLabel"] { color: #8C99B3; }
  .stAlert { background-color: rgba(18,225,159,0.08); }
</style>
""", unsafe_allow_html=True)

st.title("📊 Nexiqo — Financial Intelligence Engine")
st.caption("Select a sample company for an instant real-data demo, or upload your own standardized 3-statement Excel file.")

# ---------------------------------------------------------------------------
# DATA SOURCE SELECTION
# ---------------------------------------------------------------------------
mode = st.radio("Data source", ["📁 Sample Company (real reported data)", "⬆️ Upload my own Excel file"], horizontal=True)

def build_df_from_sample(data: dict) -> tuple:
    pnl = pd.DataFrame({
        "Year": data["years"], "Revenue": data["revenue"], "EBITDA": data["ebitda"],
        "Depreciation": data["depreciation"], "Interest": data["interest"], "NetProfit": data["net_profit"],
    })
    pnl["EBIT"] = pnl["EBITDA"] - pnl["Depreciation"]
    bs = pd.DataFrame({
        "Year": data["years"], "TotalAssets": data["total_assets"],
        "TotalEquity": data["total_equity"], "TotalDebt": data["total_debt"],
    })
    cf = pd.DataFrame({
        "Year": data["years"], "OperatingCF": data["cfo"], "InvestingCF": data["cfi"],
        "FinancingCF": data["cff"], "FCF": data["fcf"],
    })
    return pnl, bs, cf

company_name = None
main_ticker = None
peer_tickers_list = []

if mode.startswith("📁"):
    company_name = st.selectbox("Choose a company", list(SAMPLE_COMPANIES.keys()))
    data = SAMPLE_COMPANIES[company_name]
    main_ticker = data["ticker"]
    peer_tickers_list = DEFAULT_PEERS.get(company_name, [])
    pnl, bs, cf = build_df_from_sample(data)
    st.success(f"Loaded real reported financials for **{company_name}** (FY{data['years'][0]}–FY{data['years'][-1]}, consolidated, ₹ Crores). Source: company filings via screener.in.")
else:
    with st.expander("ℹ️ Template format"):
        st.write("3 sheets named **P&L**, **Balance Sheet**, **Cash Flow**, each with a `Year` column and 5 years of data.")
    uploaded_file = st.file_uploader("Upload your Excel file", type=["xlsx"])
    company_name = st.text_input("Company name", value="My Company")
    if uploaded_file is not None:
        try:
            pnl_raw = pd.read_excel(uploaded_file, sheet_name="P&L")
            bs_raw = pd.read_excel(uploaded_file, sheet_name="Balance Sheet")
            cf_raw = pd.read_excel(uploaded_file, sheet_name="Cash Flow")

            if is_flexible_layout(pnl_raw):
                pnl, bs, cf, extraction_report = build_standard_financials(pnl_raw, bs_raw, cf_raw)
                pnl["EBIT"] = pnl["EBITDA"] - pnl["Depreciation"]

                with st.expander("🔍 Extraction Report — what was matched vs. computed", expanded=True):
                    st.caption(
                        "Your file used real-world line-item naming, not Nexiqo's exact template labels. "
                        "The parser matched what it could and computed the rest from related figures — "
                        "every field below is traceable, nothing is silently guessed."
                    )
                    rep_df = pd.DataFrame(extraction_report, columns=["Year", "Field", "Source"])
                    computed_mask = rep_df["Source"].str.contains("computed", case=False)
                    notfound_mask = rep_df["Source"].str.contains("NOT FOUND|COULD NOT", case=False)
                    c1, c2, c3 = st.columns(3)
                    c1.metric("Directly matched", int((~computed_mask & ~notfound_mask).sum()))
                    c2.metric("Computed from related lines", int(computed_mask.sum()))
                    c3.metric("Not found", int(notfound_mask.sum()))
                    st.dataframe(rep_df, width='stretch', hide_index=True)
            else:
                # Legacy Nexiqo template — Year as first column, metrics as headers
                pnl, bs, cf = pnl_raw, bs_raw, cf_raw
                if "EBIT" not in pnl.columns:
                    pnl["EBIT"] = pnl["EBITDA"] - pnl["Depreciation"]
                if "FCF" not in cf.columns:
                    cf["FCF"] = cf["OperatingCF"] + cf["InvestingCF"]

            main_ticker = st.text_input("Ticker (for live market data)", value="")
        except ValueError as e:
            st.error(f"⚠️ Extraction issue: {e}")
            st.info("This usually means the sheet uses very different line-item names than what the parser's synonym list covers. If this keeps happening, let us know which company/source so we can extend the parser.")
            st.stop()
        except Exception as e:
            st.error(f"Couldn't read the file — check your 3 sheets are named exactly 'P&L', 'Balance Sheet', 'Cash Flow'. Error: {e}")
            st.stop()
    else:
        st.info("👆 Upload a file, or switch to Sample Company above to see the engine in action.")
        st.stop()

# ---------------------------------------------------------------------------
# CORE CALCULATIONS
# ---------------------------------------------------------------------------
def compute_ratios(pnl, bs, cf):
    m = pnl.merge(bs, on="Year").merge(cf, on="Year")
    r = pd.DataFrame({"Year": m["Year"]})
    r["EBITDA Margin %"] = (m["EBITDA"] / m["Revenue"]) * 100
    r["Net Margin %"] = (m["NetProfit"] / m["Revenue"]) * 100
    r["ROE %"] = (m["NetProfit"] / m["TotalEquity"]) * 100
    r["ROA %"] = (m["NetProfit"] / m["TotalAssets"]) * 100
    r["Debt/Equity"] = m["TotalDebt"] / m["TotalEquity"]
    r["Interest Coverage"] = m["EBIT"] / m["Interest"]
    r["Asset Turnover"] = m["Revenue"] / m["TotalAssets"]
    r["Cash Conversion (CFO/EBITDA)"] = m["OperatingCF"] / m["EBITDA"]
    r["FCF Margin %"] = (m["FCF"] / m["Revenue"]) * 100
    r["Equity Multiplier"] = m["TotalAssets"] / m["TotalEquity"]
    return r.round(2), m

def dupont_breakdown(ratios):
    d = ratios[["Year"]].copy()
    d["Net Margin"] = ratios["Net Margin %"] / 100
    d["Asset Turnover"] = ratios["Asset Turnover"]
    d["Equity Multiplier"] = ratios["Equity Multiplier"]
    d["ROE (computed)"] = d["Net Margin"] * d["Asset Turnover"] * d["Equity Multiplier"] * 100
    return d.round(3)

def financial_health_score(ratios):
    latest = ratios.iloc[-1]
    prior = ratios.iloc[-2] if len(ratios) > 1 else latest
    scores = {}

    margin_score = min(25, max(0, (latest["EBITDA Margin %"] / 30) * 20))
    margin_trend_bonus = 5 if latest["EBITDA Margin %"] >= prior["EBITDA Margin %"] else 0
    scores["Profitability"] = round(min(25, margin_score + margin_trend_bonus), 1)

    scores["Growth"] = 0  # replaced after this function using real revenue CAGR

    de = latest["Debt/Equity"]
    lev_score = 20 if de < 0.3 else (14 if de < 0.7 else (8 if de < 1.5 else 2))
    scores["Leverage"] = lev_score

    ic = latest["Interest Coverage"]
    cov_score = 15 if ic > 8 else (11 if ic > 4 else (6 if ic > 2 else 1))
    scores["Coverage"] = cov_score

    cc = latest["Cash Conversion (CFO/EBITDA)"]
    cash_score = 15 if cc > 0.9 else (11 if cc > 0.6 else (6 if cc > 0.3 else 1))
    scores["Cash Quality"] = cash_score

    fcf_score = 10 if latest["FCF Margin %"] > 8 else (6 if latest["FCF Margin %"] > 0 else 0)
    scores["Free Cash Flow"] = fcf_score

    return scores, latest

def risk_label(pct):
    if pct >= 75: return ("Low Risk", "🟢")
    if pct >= 50: return ("Moderate Risk", "🟡")
    return ("High Risk", "🔴")

def detect_insights(ratios, pnl):
    flags = []
    latest, prior = ratios.iloc[-1], ratios.iloc[-2]
    rev_latest, rev_prior = pnl["Revenue"].iloc[-1], pnl["Revenue"].iloc[-2]
    rev_growth = (rev_latest - rev_prior) / rev_prior * 100

    if rev_growth > 5:
        flags.append(f"✅ Revenue grew {rev_growth:.1f}% YoY.")
    elif rev_growth < 0:
        flags.append(f"⚠️ Revenue declined {abs(rev_growth):.1f}% YoY.")
    else:
        flags.append(f"➖ Revenue grew modestly at {rev_growth:.1f}% YoY.")

    margin_delta = latest["EBITDA Margin %"] - prior["EBITDA Margin %"]
    if margin_delta < -1:
        flags.append(f"⚠️ EBITDA margin compressed {abs(margin_delta):.1f}pp — revenue growth is outpacing cost efficiency.")
    elif margin_delta > 1:
        flags.append(f"✅ EBITDA margin expanded {margin_delta:.1f}pp — improving operating efficiency.")

    if latest["Debt/Equity"] > 1.0:
        flags.append(f"⚠️ Debt/Equity at {latest['Debt/Equity']:.2f} is elevated — balance sheet carries meaningful leverage.")

    if latest["Interest Coverage"] < 3:
        flags.append(f"⚠️ Interest coverage of {latest['Interest Coverage']:.1f}x is thin — earnings cushion over debt cost is limited.")
    elif latest["Interest Coverage"] > 10:
        flags.append(f"✅ Interest coverage of {latest['Interest Coverage']:.1f}x indicates strong debt-servicing capacity.")

    if latest["Cash Conversion (CFO/EBITDA)"] < 0.5:
        flags.append(f"⚠️ Only {latest['Cash Conversion (CFO/EBITDA)']*100:.0f}% of EBITDA is converting to operating cash flow — earnings quality warrants scrutiny.")

    if latest["FCF Margin %"] < 0:
        flags.append("⚠️ Free cash flow was negative in the latest year — the business consumed cash after capex.")

    roe_delta = latest["ROE %"] - prior["ROE %"]
    if abs(roe_delta) > 3:
        direction = "improved" if roe_delta > 0 else "declined"
        flags.append(f"{'✅' if roe_delta>0 else '⚠️'} ROE {direction} {abs(roe_delta):.1f}pp YoY.")

    return flags

def forecast_metric(pnl, column, growth_override, years_ahead=2):
    years = pnl["Year"].values
    values = pnl[column].values
    n_periods = len(values) - 1
    has_negative = (values <= 0).any()

    if has_negative:
        # Compound % growth is meaningless on negative numbers (e.g. a loss
        # "growing" 10% would get worse, not better). Use additive trend instead.
        avg_change = (values[-1] - values[0]) / n_periods if n_periods > 0 else 0
        cagr = None  # not applicable — flagged to the UI
        change_rate = growth_override if growth_override is not None else avg_change
        future_years = [years[-1] + i for i in range(1, years_ahead + 1)]
        future_values, last_val = [], values[-1]
        for _ in range(years_ahead):
            last_val = last_val + change_rate
            future_values.append(last_val)
        hist = pd.DataFrame({"Year": years, column: values, "Type": "Actual"})
        fcst = pd.DataFrame({"Year": future_years, column: future_values, "Type": "Forecast"})
        return pd.concat([hist, fcst], ignore_index=True), avg_change, True  # True = additive mode

    cagr = (values[-1] / values[0]) ** (1 / n_periods) - 1 if n_periods > 0 and values[0] > 0 else 0
    growth_rate = growth_override if growth_override is not None else cagr
    future_years = [years[-1] + i for i in range(1, years_ahead + 1)]
    future_values, last_val = [], values[-1]
    for _ in range(years_ahead):
        last_val = last_val * (1 + growth_rate)
        future_values.append(last_val)
    hist = pd.DataFrame({"Year": years, column: values, "Type": "Actual"})
    fcst = pd.DataFrame({"Year": future_years, column: future_values, "Type": "Forecast"})
    return pd.concat([hist, fcst], ignore_index=True), cagr, False  # False = compound % mode

# ---------------------------------------------------------------------------
# RUN CALCULATIONS
# ---------------------------------------------------------------------------
ratios, merged = compute_ratios(pnl, bs, cf)
dupont = dupont_breakdown(ratios)
scores, latest_ratios = financial_health_score(ratios)

rev_cagr = (pnl["Revenue"].iloc[-1] / pnl["Revenue"].iloc[0]) ** (1 / (len(pnl) - 1)) - 1
scores["Growth"] = round(min(15, max(0, (rev_cagr * 100 / 20) * 15)), 1)

total_score = round(sum(scores.values()))
insights = detect_insights(ratios, pnl)

# ---------------------------------------------------------------------------
# UI — HEADLINE
# ---------------------------------------------------------------------------
st.header(f"{company_name}")
latest = pnl.iloc[-1]
c1, c2, c3, c4 = st.columns(4)
c1.metric("Revenue", f"₹{latest['Revenue']:,.0f} Cr")
c2.metric("EBITDA", f"₹{latest['EBITDA']:,.0f} Cr")
c3.metric("Net Profit", f"₹{latest['NetProfit']:,.0f} Cr")
c4.metric("Revenue CAGR", f"{rev_cagr*100:.1f}%")

# ---------------------------------------------------------------------------
# FINANCIAL HEALTH SCORE
# ---------------------------------------------------------------------------
st.subheader("🎯 Financial Health Score")
label, emoji = risk_label(total_score)
sc1, sc2 = st.columns([1, 2])
with sc1:
    st.markdown(f"<div style='text-align:center'><span style='font-size:64px;font-weight:800;color:#12E19F'>{total_score}</span><span style='font-size:24px;color:#8C99B3'>/100</span><br><span style='font-size:20px'>{emoji} {label}</span></div>", unsafe_allow_html=True)
with sc2:
    score_df = pd.DataFrame({"Component": list(scores.keys()), "Score": list(scores.values())})
    max_map = {"Profitability": 25, "Growth": 15, "Leverage": 20, "Coverage": 15, "Cash Quality": 15, "Free Cash Flow": 10}
    score_df["Max"] = score_df["Component"].map(max_map)
    score_df["% of Max"] = (score_df["Score"] / score_df["Max"] * 100).round(0)
    st.dataframe(score_df, width='stretch', hide_index=True)
st.caption("Nexiqo Health Score methodology: weighted composite of profitability, growth, leverage, interest coverage, cash conversion quality, and free cash flow — computed entirely from the statements above.")

# ---------------------------------------------------------------------------
# TRUSTED FRAMEWORKS — DuPont
# ---------------------------------------------------------------------------
st.subheader("📐 DuPont ROE Decomposition")
st.caption("ROE = Net Margin × Asset Turnover × Equity Multiplier — shows *why* returns moved, not just that they did.")
st.dataframe(dupont, width='stretch', hide_index=True)
st.line_chart(dupont.set_index("Year")[["Net Margin", "Asset Turnover", "Equity Multiplier"]])

# ---------------------------------------------------------------------------
# RATIO TABLE + TRENDS
# ---------------------------------------------------------------------------
st.subheader("📊 Full Ratio Analysis")
st.dataframe(ratios, width='stretch', hide_index=True)
colA, colB = st.columns(2)
with colA:
    st.write("**Profitability trend**")
    st.line_chart(ratios.set_index("Year")[["EBITDA Margin %", "Net Margin %", "ROE %"]])
with colB:
    st.write("**Leverage & coverage trend**")
    st.line_chart(ratios.set_index("Year")[["Debt/Equity", "Interest Coverage"]])

# ---------------------------------------------------------------------------
# INSIGHT ENGINE
# ---------------------------------------------------------------------------
st.subheader("🧠 Insight Engine — What the Numbers Say")
for f in insights:
    st.write(f)

# ---------------------------------------------------------------------------
# FORECAST
# ---------------------------------------------------------------------------
st.subheader("🔮 Forecast")
metric_choice = st.selectbox("Metric to forecast", ["Revenue", "EBITDA", "NetProfit"])
_, hist_rate, is_additive = forecast_metric(pnl, metric_choice, None)

if is_additive:
    st.caption(f"⚠️ {metric_choice} includes negative/loss years — using an additive trend (₹ Cr change per year) instead of a % growth rate, since compounding a percentage on a loss is misleading.")
    change_input = st.slider(f"Assumed change per year (₹ Cr)", -300.0, 300.0, round(hist_rate, 1), 5.0)
    combined, _, _ = forecast_metric(pnl, metric_choice, change_input)
else:
    growth_input = st.slider("Assumed forward growth rate (%)", -20.0, 40.0, round(hist_rate * 100, 1), 0.5)
    combined, _, _ = forecast_metric(pnl, metric_choice, growth_input / 100)

st.line_chart(combined.pivot(index="Year", columns="Type", values=metric_choice))

# ---------------------------------------------------------------------------
# LIVE MARKET DATA
# ---------------------------------------------------------------------------
st.subheader("🌐 Live Market Benchmarking")
st.caption("For NSE-listed companies, use the ticker + '.NS' (e.g. OLAELEC.NS, RELIANCE.NS, TCS.NS). For BSE-only stocks, try '.BO' instead.")
col1, col2 = st.columns(2)
with col1:
    t_main = st.text_input("Company ticker", value=main_ticker or "", placeholder="e.g. OLAELEC.NS")
with col2:
    t_peers = st.text_input("Peer tickers (comma-separated)", value=", ".join(peer_tickers_list), placeholder="e.g. TVSMOTOR.NS, HEROMOTOCO.NS")

fetch_clicked = st.button("Fetch live market data")
if fetch_clicked:
    if not t_main.strip():
        st.warning("⚠️ Enter a company ticker above first (e.g. OLAELEC.NS) — the field was empty.")
    else:
        import time
        tickers = [t_main.strip()] + [t.strip() for t in t_peers.split(",") if t.strip()]
        rows = []
        any_success = False
        any_rate_limited = False
        for t in tickers:
            info = None
            last_err = None
            for attempt in range(2):  # one retry, since transient rate limits sometimes clear in a second
                try:
                    info = yf.Ticker(t).info
                    break
                except Exception as e:
                    last_err = e
                    if attempt == 0:
                        time.sleep(1.5)
            if info is None:
                err_str = str(last_err)
                if "rate limit" in err_str.lower() or "too many requests" in err_str.lower():
                    any_rate_limited = True
                    rows.append({"Ticker": t, "Price": "Rate-limited", "Market Cap (Cr)": "-", "P/E Ratio": "-"})
                else:
                    rows.append({"Ticker": t, "Price": f"Error: {err_str[:40]}", "Market Cap (Cr)": "-", "P/E Ratio": "-"})
                continue
            price = info.get("currentPrice") or info.get("regularMarketPrice")
            if price is None:
                rows.append({"Ticker": t, "Price": "No data found", "Market Cap (Cr)": "-", "P/E Ratio": "-"})
            else:
                any_success = True
                rows.append({
                    "Ticker": t, "Price": price,
                    "Market Cap (Cr)": round(info.get("marketCap", 0) / 1e7, 0) if info.get("marketCap") else "N/A",
                    "P/E Ratio": info.get("trailingPE", "N/A"),
                })
        market_df = pd.DataFrame(rows)
        st.dataframe(market_df, width='stretch', hide_index=True)
        if any_success:
            st.caption("Live data pulled from Yahoo Finance at time of click.")
        if any_rate_limited:
            st.info("⏳ Yahoo Finance is temporarily rate-limiting requests from this server (a known limitation of free-tier cloud hosting shared across many apps — not specific to your data). Wait a minute and click Fetch again.")
        elif not any_success:
            st.error("⚠️ No data came back for any ticker. Double-check the ticker format (NSE stocks need '.NS', e.g. OLAELEC.NS) — or the company may not be publicly listed.")

# ---------------------------------------------------------------------------
# PDF REPORT EXPORT
# ---------------------------------------------------------------------------
def generate_pdf(company_name, pnl, ratios, dupont, scores, total_score, label, insights):
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=18*mm, bottomMargin=18*mm, leftMargin=18*mm, rightMargin=18*mm)
    styles = getSampleStyleSheet()
    navy = colors.HexColor("#0B1F3A")
    emerald = colors.HexColor("#0F9D6E")
    title_style = ParagraphStyle("title", parent=styles["Title"], textColor=navy, fontSize=20)
    h2_style = ParagraphStyle("h2", parent=styles["Heading2"], textColor=navy, fontSize=13, spaceBefore=14)
    body_style = ParagraphStyle("body", parent=styles["BodyText"], fontSize=9.5, leading=13)
    caption = ParagraphStyle("caption", parent=styles["BodyText"], fontSize=8, textColor=colors.grey)

    elems = []
    elems.append(Paragraph("NEXIQO", ParagraphStyle("brand", parent=styles["Title"], textColor=emerald, fontSize=14)))
    elems.append(Paragraph(f"Financial Intelligence Report — {company_name}", title_style))
    elems.append(Paragraph(f"Generated {datetime.now().strftime('%d %b %Y')} · Consolidated figures, Rs. Crores", caption))
    elems.append(Spacer(1, 10))

    elems.append(Paragraph("Financial Health Score", h2_style))
    elems.append(Paragraph(f"<b>{total_score}/100 — {label}</b>", body_style))
    max_map = {"Profitability":25,"Growth":15,"Leverage":20,"Coverage":15,"Cash Quality":15,"Free Cash Flow":10}
    score_table_data = [["Component", "Score", "Max"]] + [[k, str(v), str(max_map[k])] for k, v in scores.items()]
    t = Table(score_table_data, hAlign="LEFT", colWidths=[70*mm, 25*mm, 25*mm])
    t.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),navy),("TEXTCOLOR",(0,0),(-1,0),colors.white),
                           ("FONTSIZE",(0,0),(-1,-1),9),("GRID",(0,0),(-1,-1),0.4,colors.lightgrey),
                           ("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.whitesmoke, colors.white])]))
    elems.append(t)
    elems.append(Spacer(1, 10))

    elems.append(Paragraph("Key Ratios (Latest Year)", h2_style))
    lr = ratios.iloc[-1]
    ratio_rows = [["Metric", "Value"]] + [[k, f"{lr[k]:.2f}"] for k in ratios.columns if k != "Year"]
    rt = Table(ratio_rows, hAlign="LEFT", colWidths=[70*mm, 40*mm])
    rt.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),navy),("TEXTCOLOR",(0,0),(-1,0),colors.white),
                            ("FONTSIZE",(0,0),(-1,-1),9),("GRID",(0,0),(-1,-1),0.4,colors.lightgrey),
                            ("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.whitesmoke, colors.white])]))
    elems.append(rt)
    elems.append(Spacer(1, 10))

    elems.append(Paragraph("DuPont ROE Decomposition (Latest Year)", h2_style))
    ld = dupont.iloc[-1]
    elems.append(Paragraph(
        f"ROE = Net Margin ({ld['Net Margin']:.2f}) x Asset Turnover ({ld['Asset Turnover']:.2f}) x "
        f"Equity Multiplier ({ld['Equity Multiplier']:.2f}) = <b>{ld['ROE (computed)']:.1f}%</b>", body_style))
    elems.append(Spacer(1, 10))

    elems.append(Paragraph("Insight Engine - Key Observations", h2_style))
    for f in insights:
        clean = f.replace("✅", "").replace("⚠️", "").replace("➖", "").strip()
        elems.append(Paragraph(f"- {clean}", body_style))

    elems.append(Spacer(1, 16))
    elems.append(Paragraph("Generated by Nexiqo - Enterprise Financial Intelligence Platform. For illustrative/educational use.", caption))

    doc.build(elems)
    buf.seek(0)
    return buf

st.subheader("📄 Executive Report")
pdf_buf = generate_pdf(company_name, pnl, ratios, dupont, scores, total_score, label, insights)
st.download_button(
    label="⬇️ Download PDF Report",
    data=pdf_buf,
    file_name=f"Nexiqo_{company_name.replace(' ','_')}_Report.pdf",
    mime="application/pdf",
)
