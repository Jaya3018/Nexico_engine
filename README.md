# Nexiqo — Financial Intelligence Engine

## What this is
A Streamlit web app that analyzes a company's financials: ratio analysis,
DuPont ROE decomposition, a rule-based Financial Health Score, an insight
engine that explains *why* the numbers moved, adjustable-assumption
forecasting, live market benchmarking (via Yahoo Finance), and a downloadable
PDF executive report.

Includes 3 pre-loaded sample companies (Infosys, TCS, Reliance Industries)
using real reported figures (FY2021-FY2025, sourced from screener.in / company
filings) for an instant demo — no file upload needed to try it.

## Files
- `app.py` — the main Streamlit app
- `sample_data.py` — real financial data for the 3 demo companies
- `generate_template.py` — run this once to create a blank Excel template for
  uploading your own company's data
- `requirements.txt` — Python dependencies

## Run locally
```
pip install -r requirements.txt
streamlit run app.py
```

## Deploy for free (so you get a public link for your resume/portfolio)
1. Create a free GitHub account if you don't have one.
2. Create a new repository, upload these 3 files (app.py, sample_data.py,
   requirements.txt) — no need to upload generate_template.py or the test
   files, those were just for local testing.
3. Go to https://share.streamlit.io, sign in with GitHub (free).
4. Click "New app", pick your repo, set the main file to `app.py`, click Deploy.
5. Wait ~2 minutes. You'll get a public URL like
   `https://yourname-nexiqo.streamlit.app` — this is the link to put on your
   resume / QR code / portfolio website.

## Data source note
Sample company figures are consolidated, in Rs. Crores, sourced from public
financial statements as reported on screener.in. For any custom company you
analyze, use the blank template from `generate_template.py` and fill it with
that company's actual reported figures.
