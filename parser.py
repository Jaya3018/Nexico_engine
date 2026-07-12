"""
Nexiqo Flexible Financial Statement Parser
============================================
Real annual-report exports (screener.in, moneycontrol, company filings) vary
in layout and line-item naming, but the underlying structure is consistent:
a set of recognizable line items across a run of years. This module handles
two layouts:

  LEGACY (Nexiqo's own blank template):
      Year | Revenue | EBITDA | Depreciation | Interest | NetProfit  (years as rows)

  FLEXIBLE (real-world exports, e.g. screener.in):
      Indicator | Mar 26 | Mar 25 | Mar 24 | ...                     (years as columns)
      Revenue From Operations [Net]  |  2.49  |  3  | ...

For the flexible layout, canonical fields are matched against a synonym list
covering common naming variants. Fields not directly present (most commonly
EBITDA and Free Cash Flow) are computed from related line items, and every
computation is logged so the app can show the user exactly what was matched
vs. derived — nothing is silently guessed without disclosure.
"""
import re
import pandas as pd
import numpy as np

# ---------------------------------------------------------------------------
# Synonym dictionary — ordered by preference (first match wins)
# ---------------------------------------------------------------------------
SYNONYMS = {
    "revenue": [
        "total operating revenues", "net sales", "total revenue from operations",
        "revenue from operations [net]", "total income from operations",
        "net revenue", "sales", "total operating income",
    ],
    "revenue_incl_other_income_fallback": ["total revenue", "total income"],
    "ebitda_direct": [
        "operating profit", "ebitda", "pbidt",
        "profit before interest depreciation and tax", "operating profit before other income",
    ],
    "depreciation": [
        "depreciation and amortisation expenses", "depreciation & amortisation expenses",
        "depreciation and amortization expenses", "depreciation & amortisation", "depreciation",
    ],
    "interest": [
        "finance costs", "interest expense", "interest and finance charges", "interest",
    ],
    "net_profit": [
        "profit/loss for the period", "profit after tax", "net profit",
        "profit/loss from continuing operations", "profit for the year",
        "profit/loss for the year", "net profit/(loss) for the period",
    ],
    "total_expenses": ["total expenses", "total expenditure"],
    "total_assets": [
        "total capital and liabilities", "total assets", "total assets/liabilities",
    ],
    "total_equity": [
        "total shareholders funds", "total shareholder's funds", "total equity",
        "shareholders funds", "total shareholders' funds",
    ],
    "share_capital": ["total share capital", "equity share capital"],
    "reserves": ["total reserves and surplus", "reserves and surplus"],
    "lt_borrowings": ["long term borrowings"],
    "st_borrowings": ["short term borrowings"],
    "total_debt_direct": ["total debt", "total borrowings"],
    "cfo": [
        "net cashflow from operating activities", "net cash flow from operating activities",
        "cash from operating activities", "net cash generated from operating activities",
    ],
    "cfi": [
        "net cash used in investing activities", "net cash from investing activities",
        "cash flow from investing activities", "net cash used in/generated from investing activities",
    ],
    "cff": [
        "net cash used from financing activities", "net cash from financing activities",
        "cash flow from financing activities", "net cash used in/generated from financing activities",
    ],
    "capex": [
        "purchase of fixed assets", "capital expenditure", "purchase of property plant and equipment",
    ],
}


def _norm(s):
    return re.sub(r"\s+", " ", str(s).strip().lower())


def parse_year_label(label):
    """Extract a calendar year from labels like 'Mar 26', 'FY2026', '2026', 'Mar-24'."""
    if label is None:
        return None
    s = str(label).strip()
    m4 = re.search(r"(20\d{2}|19\d{2})", s)
    if m4:
        return int(m4.group(1))
    m2 = re.search(r"(\d{2})\s*$", s)
    if m2:
        yy = int(m2.group(1))
        return 2000 + yy if yy < 50 else 1900 + yy
    return None


def is_flexible_layout(raw_df) -> bool:
    """True if this looks like a real-world 'Indicator + year columns' export
    rather than Nexiqo's own 'Year' + metric-columns template."""
    first_col = str(raw_df.columns[0]).strip().lower()
    if first_col == "year":
        return False
    # flexible layout: 2+ of the remaining column headers should look like years
    year_like = sum(1 for c in raw_df.columns[1:] if parse_year_label(c) is not None)
    return year_like >= 2


def parse_indicator_sheet(raw_df):
    """Parse a flexible-layout sheet into (years, indicator_map).
    indicator_map: {normalized_label: {year: value}}"""
    cols = list(raw_df.columns)
    year_cols = cols[1:]
    years = [parse_year_label(c) for c in year_cols]
    indicator_map = {}
    for _, row in raw_df.iterrows():
        label = row[cols[0]]
        if label is None or str(label).strip() == "":
            continue
        norm = _norm(label)
        vals = {}
        for yc, y in zip(year_cols, years):
            if y is None:
                continue
            v = row[yc]
            if isinstance(v, (int, float)) and not pd.isna(v):
                vals[y] = float(v)
        if vals:
            # if duplicate normalized labels occur, keep the first (usually the subtotal)
            if norm not in indicator_map:
                indicator_map[norm] = vals
    valid_years = sorted(set(y for y in years if y is not None))
    return valid_years, indicator_map


def _lookup(indicator_map, keys, year):
    for k in keys:
        if k in indicator_map and year in indicator_map[k]:
            return indicator_map[k][year], k
    return None, None


def build_standard_financials(pnl_raw, bs_raw, cf_raw):
    """
    Takes 3 raw DataFrames (as read from Excel, flexible layout) and returns
    (pnl_df, bs_df, cf_df) in Nexiqo's canonical schema, plus a report list
    describing what was directly matched vs computed.
    """
    report = []

    pnl_years, pnl_map = parse_indicator_sheet(pnl_raw)
    bs_years, bs_map = parse_indicator_sheet(bs_raw)
    cf_years, cf_map = parse_indicator_sheet(cf_raw)

    years = sorted(set(pnl_years) & set(bs_years) & set(cf_years))
    if len(years) < 2:
        raise ValueError(
            f"Could not find at least 2 matching years across all 3 sheets. "
            f"P&L years: {pnl_years}, Balance Sheet years: {bs_years}, Cash Flow years: {cf_years}"
        )

    pnl_rows, bs_rows, cf_rows = [], [], []

    for y in years:
        # --- Revenue ---
        revenue, src = _lookup(pnl_map, SYNONYMS["revenue"], y)
        if revenue is None:
            revenue, src = _lookup(pnl_map, SYNONYMS["revenue_incl_other_income_fallback"], y)
            if revenue is not None:
                report.append((y, "Revenue", f"used '{src}' (includes other income — no cleaner operating revenue line found)"))
        else:
            report.append((y, "Revenue", f"matched '{src}'"))

        # --- Depreciation & Interest (needed either way) ---
        dep, dep_src = _lookup(pnl_map, SYNONYMS["depreciation"], y)
        interest, int_src = _lookup(pnl_map, SYNONYMS["interest"], y)
        dep = dep or 0.0
        interest = interest or 0.0
        report.append((y, "Depreciation", f"matched '{dep_src}'" if dep_src else "not found — assumed 0"))
        report.append((y, "Interest", f"matched '{int_src}'" if int_src else "not found — assumed 0"))

        # --- EBITDA: direct match, else computed ---
        ebitda, ebitda_src = _lookup(pnl_map, SYNONYMS["ebitda_direct"], y)
        if ebitda is not None:
            report.append((y, "EBITDA", f"matched '{ebitda_src}'"))
        else:
            total_rev, _ = _lookup(pnl_map, SYNONYMS["revenue_incl_other_income_fallback"], y)
            total_exp, _ = _lookup(pnl_map, SYNONYMS["total_expenses"], y)
            if total_rev is not None and total_exp is not None:
                pbt = total_rev - total_exp
                ebitda = pbt + interest + dep
                report.append((y, "EBITDA", "computed as (Total Revenue - Total Expenses) + Interest + Depreciation"))
            else:
                ebitda = None
                report.append((y, "EBITDA", "COULD NOT COMPUTE — missing Total Revenue/Total Expenses"))

        # --- Net Profit ---
        net_profit, np_src = _lookup(pnl_map, SYNONYMS["net_profit"], y)
        report.append((y, "Net Profit", f"matched '{np_src}'" if np_src else "NOT FOUND"))

        pnl_rows.append({
            "Year": y, "Revenue": revenue, "EBITDA": ebitda,
            "Depreciation": dep, "Interest": interest, "NetProfit": net_profit,
        })

        # --- Balance Sheet ---
        total_assets, ta_src = _lookup(bs_map, SYNONYMS["total_assets"], y)
        report.append((y, "Total Assets", f"matched '{ta_src}'" if ta_src else "NOT FOUND"))

        total_equity, te_src = _lookup(bs_map, SYNONYMS["total_equity"], y)
        if total_equity is None:
            cap, _ = _lookup(bs_map, SYNONYMS["share_capital"], y)
            res, _ = _lookup(bs_map, SYNONYMS["reserves"], y)
            if cap is not None and res is not None:
                total_equity = cap + res
                report.append((y, "Total Equity", "computed as Share Capital + Reserves and Surplus"))
            else:
                report.append((y, "Total Equity", "NOT FOUND"))
        else:
            report.append((y, "Total Equity", f"matched '{te_src}'"))

        total_debt, td_src = _lookup(bs_map, SYNONYMS["total_debt_direct"], y)
        if total_debt is None:
            lt, _ = _lookup(bs_map, SYNONYMS["lt_borrowings"], y)
            st, _ = _lookup(bs_map, SYNONYMS["st_borrowings"], y)
            total_debt = (lt or 0.0) + (st or 0.0)
            report.append((y, "Total Debt", "computed as Long Term + Short Term Borrowings"))
        else:
            report.append((y, "Total Debt", f"matched '{td_src}'"))

        bs_rows.append({
            "Year": y, "TotalAssets": total_assets, "TotalEquity": total_equity, "TotalDebt": total_debt,
        })

        # --- Cash Flow ---
        cfo, cfo_src = _lookup(cf_map, SYNONYMS["cfo"], y)
        cfi, cfi_src = _lookup(cf_map, SYNONYMS["cfi"], y)
        cff, cff_src = _lookup(cf_map, SYNONYMS["cff"], y)
        report.append((y, "Operating CF", f"matched '{cfo_src}'" if cfo_src else "NOT FOUND"))
        report.append((y, "Investing CF", f"matched '{cfi_src}'" if cfi_src else "NOT FOUND"))
        report.append((y, "Financing CF", f"matched '{cff_src}'" if cff_src else "NOT FOUND"))

        capex, capex_src = _lookup(cf_map, SYNONYMS["capex"], y)
        if capex is not None:
            fcf = (cfo or 0.0) - abs(capex)
            report.append((y, "Free Cash Flow", f"computed as Operating CF - Capex (matched '{capex_src}')"))
        else:
            fcf = (cfo or 0.0) + (cfi or 0.0)
            report.append((y, "Free Cash Flow", "computed as Operating CF + Investing CF (no explicit Capex line found — approximation)"))

        cf_rows.append({
            "Year": y, "OperatingCF": cfo, "InvestingCF": cfi, "FinancingCF": cff, "FCF": fcf,
        })

    pnl_df = pd.DataFrame(pnl_rows)
    bs_df = pd.DataFrame(bs_rows)
    cf_df = pd.DataFrame(cf_rows)

    # Drop years with any critical missing field (Revenue, EBITDA, NetProfit, TotalAssets, TotalEquity)
    critical = ["Revenue", "EBITDA", "NetProfit"]
    valid_mask = pnl_df[critical].notna().all(axis=1)
    pnl_df, bs_df, cf_df = pnl_df[valid_mask].reset_index(drop=True), bs_df[valid_mask].reset_index(drop=True), cf_df[valid_mask].reset_index(drop=True)

    if len(pnl_df) < 2:
        raise ValueError(
            "After matching, fewer than 2 years had complete Revenue/EBITDA/Net Profit data. "
            "Check the Extraction Report to see what was found."
        )

    return pnl_df, bs_df, cf_df, report
