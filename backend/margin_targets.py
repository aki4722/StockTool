"""Fixed target symbols for margin position tracking."""

MARGIN_TARGETS = (
    {"symbol": "9107.T", "company_name": "川崎汽船"},
    {"symbol": "6178.T", "company_name": "日本郵政"},
    {"symbol": "2914.T", "company_name": "日本たばこ産業 / JT"},
    {"symbol": "4180.T", "company_name": "Appier Group"},
    {"symbol": "8869.T", "company_name": "明和地所"},
    {"symbol": "3817.T", "company_name": "SRAホールディングス"},
)

MARGIN_TARGET_SYMBOLS = tuple(item["symbol"] for item in MARGIN_TARGETS)
