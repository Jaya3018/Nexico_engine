"""
Real financial data (FY2021-FY2025, i.e. years ended March 2021-2025), sourced
from consolidated financial statements as reported on screener.in (public data,
originally from company filings). All figures in Rs. Crores unless noted.

Fields:
  ebitda      = Operating Profit (Sales - Operating Expenses, before D&A & interest)
  ebit        = ebitda - depreciation
  total_equity= Equity Capital + Reserves
  total_debt  = Borrowings
  total_assets= Total Assets (= Total Liabilities, balance sheet identity)
  cfo/cfi/cff = Cash flow from Operating / Investing / Financing activities
  fcf         = Free Cash Flow (as reported)
"""

SAMPLE_COMPANIES = {
    "Infosys Ltd": {
        "ticker": "INFY.NS",
        "years": [2021, 2022, 2023, 2024, 2025],
        "revenue":      [100472, 121641, 146767, 153670, 162990],
        "ebitda":       [27889, 31491, 35130, 36425, 39236],
        "depreciation": [3267, 3476, 4225, 4678, 4812],
        "interest":     [195, 200, 284, 470, 416],
        "net_profit":   [19423, 22146, 24108, 26248, 26750],
        "total_equity": [76351, 75350, 75407, 88116, 95818],
        "total_debt":   [5325, 5474, 8299, 8359, 8227],
        "total_assets": [107511, 116729, 124596, 136020, 147795],
        "cfo":  [23224, 23885, 22467, 25210, 35694],
        "cfi":  [-7373, -6485, -1071, -5093, -1864],
        "cff":  [-9786, -24642, -26695, -17504, -24161],
        "fcf":  [21117, 21724, 19888, 23009, 33457],
    },
    "Tata Consultancy Services Ltd": {
        "ticker": "TCS.NS",
        "years": [2021, 2022, 2023, 2024, 2025],
        "revenue":      [164177, 191754, 225458, 240893, 255324],
        "ebitda":       [46546, 53057, 59259, 64296, 67407],
        "depreciation": [4065, 4604, 5022, 4985, 5242],
        "interest":     [637, 784, 779, 778, 796],
        "net_profit":   [32562, 38449, 42303, 46099, 48797],
        "total_equity": [86433, 89139, 90424, 90489, 94756],
        "total_debt":   [7795, 7818, 7688, 8021, 9392],
        "total_assets": [129992, 140924, 142859, 145472, 158649],
        "cfo":  [38802, 39949, 41965, 44338, 48908],
        "cfi":  [-7956, -738, 548, 6091, -2144],
        "cff":  [-32634, -33581, -47878, -48536, -47438],
        "fcf":  [35663, 36985, 38902, 41688, 44994],
    },
    "Reliance Industries Ltd": {
        "ticker": "RELIANCE.NS",
        "years": [2021, 2022, 2023, 2024, 2025],
        "revenue":      [466307, 694673, 876396, 899041, 962820],
        "ebitda":       [80790, 108581, 142318, 162498, 165598],
        "depreciation": [26572, 29782, 40303, 50832, 53136],
        "interest":     [21189, 14584, 19571, 23118, 24269],
        "net_profit":   [53739, 67845, 74088, 79020, 81309],
        "total_equity": [700172, 779485, 715872, 793481, 843200],
        "total_debt":   [278962, 319158, 451664, 350719, 374313],
        "total_assets": [1320065, 1498622, 1605882, 1755048, 1949713],
        "cfo":  [26958, 110654, 115032, 158788, 178703],
        "cfi":  [-142385, -109162, -93001, -113581, -137535],
        "cff":  [101904, 17289, 10455, -16646, -31891],
        "fcf":  [-76560, 13646, -16770, 21212, 41079],
    },
}

DEFAULT_PEERS = {
    "Infosys Ltd": ["TCS.NS", "WIPRO.NS", "HCLTECH.NS"],
    "Tata Consultancy Services Ltd": ["INFY.NS", "WIPRO.NS", "HCLTECH.NS"],
    "Reliance Industries Ltd": ["ONGC.NS", "IOC.NS", "BPCL.NS"],
}
