import datetime
import logging
import os
import requests
import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)

from src.data.cache import get_cache
from src.data.models import (
    CompanyNews,
    FinancialMetrics,
    Price,
    LineItem,
    InsiderTrade,
    CompanyFacts,
    CompanyFactsResponse,
)

# Global cache instance
_cache = get_cache()

# ---------------------------------------------------------------------------
# yfinance field name mappings
# ---------------------------------------------------------------------------

_INCOME_STMT_FIELDS = {
    "revenue": "Total Revenue",
    "gross_profit": "Gross Profit",
    "operating_income": "Operating Income",
    "ebit": "EBIT",
    "ebitda": "EBITDA",
    "net_income": "Net Income",
    "interest_expense": "Interest Expense Non Operating",
    "earnings_per_share": "Diluted EPS",
    "depreciation_and_amortization": "Reconciled Depreciation",
    "research_and_development": "Research And Development",
    "operating_expense": "Operating Expense",
}

_BALANCE_SHEET_FIELDS = {
    "total_assets": "Total Assets",
    "total_liabilities": "Total Liabilities Net Minority Interest",
    "current_assets": "Current Assets",
    "current_liabilities": "Current Liabilities",
    "cash_and_equivalents": "Cash And Cash Equivalents",
    "shareholders_equity": "Stockholders Equity",
    "total_debt": "Total Debt",
    "outstanding_shares": "Ordinary Shares Number",
    "working_capital": "Working Capital",
    "goodwill_and_intangible_assets": "Goodwill And Other Intangible Assets",
}

_CASHFLOW_FIELDS = {
    "free_cash_flow": "Free Cash Flow",
    "capital_expenditure": "Capital Expenditure",
    "dividends_and_other_cash_distributions": "Cash Dividends Paid",
    "issuance_or_purchase_of_equity_shares": "Net Common Stock Issuance",
}


def _safe_get(df: pd.DataFrame, row: str, col) -> float | None:
    """Safely extract a numeric value from a DataFrame."""
    try:
        if row in df.index and col in df.columns:
            val = df.loc[row, col]
            if pd.notna(val):
                return float(val)
    except Exception:
        pass
    return None


def _filter_columns_by_date(df: pd.DataFrame, end_date: str) -> pd.DataFrame:
    """Keep only columns (dates) that are <= end_date."""
    if df is None or df.empty:
        return df
    end_dt = pd.Timestamp(end_date)
    valid_cols = [c for c in df.columns if pd.Timestamp(c).tz_localize(None) <= end_dt]
    return df[valid_cols] if valid_cols else df


# ---------------------------------------------------------------------------
# Public API functions (same signatures as before)
# ---------------------------------------------------------------------------

def get_prices(ticker: str, start_date: str, end_date: str, api_key: str = None) -> list[Price]:
    """Fetch price data from cache or yfinance."""
    cache_key = f"{ticker}_{start_date}_{end_date}"
    if cached_data := _cache.get_prices(cache_key):
        return [Price(**price) for price in cached_data]

    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(start=start_date, end=end_date, auto_adjust=True)
    except Exception as e:
        logger.warning("Failed to fetch prices for %s: %s", ticker, e)
        return []

    if hist.empty:
        return []

    prices = []
    for ts, row in hist.iterrows():
        prices.append(Price(
            open=float(row["Open"]),
            close=float(row["Close"]),
            high=float(row["High"]),
            low=float(row["Low"]),
            volume=int(row["Volume"]),
            time=ts.strftime("%Y-%m-%dT%H:%M:%S"),
        ))

    _cache.set_prices(cache_key, [p.model_dump() for p in prices])
    return prices


def get_financial_metrics(
    ticker: str,
    end_date: str,
    period: str = "ttm",
    limit: int = 10,
    api_key: str = None,
) -> list[FinancialMetrics]:
    """Fetch financial metrics from cache or yfinance."""
    cache_key = f"{ticker}_{period}_{end_date}_{limit}"
    if cached_data := _cache.get_financial_metrics(cache_key):
        return [FinancialMetrics(**metric) for metric in cached_data]

    try:
        stock = yf.Ticker(ticker)
        info = stock.info or {}

        if period == "annual":
            inc = stock.financials
            bs = stock.balance_sheet
            cf = stock.cashflow
        else:
            inc = stock.quarterly_financials
            bs = stock.quarterly_balance_sheet
            cf = stock.quarterly_cashflow

        inc = _filter_columns_by_date(inc, end_date)
        bs = _filter_columns_by_date(bs, end_date)
        cf = _filter_columns_by_date(cf, end_date)

        # Collect unique sorted dates (newest first)
        all_dates: list[pd.Timestamp] = []
        for df in (bs, inc, cf):
            if df is not None and not df.empty:
                for col in df.columns:
                    ts = pd.Timestamp(col).tz_localize(None)
                    if ts not in all_dates:
                        all_dates.append(ts)
        all_dates = sorted(set(all_dates), reverse=True)[:limit]

    except Exception as e:
        logger.warning("Failed to fetch financial metrics for %s: %s", ticker, e)
        return []

    if not all_dates:
        # Fallback: return a single entry from .info for the current date
        all_dates = [pd.Timestamp(end_date)]

    metrics_list: list[FinancialMetrics] = []
    is_first = True

    for date in all_dates:
        # For the most recent period, use .info ratios directly (they're TTM/current)
        if is_first:
            revenue = _safe_get(inc, "Total Revenue", date) if inc is not None and not inc.empty else None
            gross_profit = _safe_get(inc, "Gross Profit", date) if inc is not None and not inc.empty else None
            op_income = _safe_get(inc, "Operating Income", date) if inc is not None and not inc.empty else None
            net_income = _safe_get(inc, "Net Income", date) if inc is not None and not inc.empty else None
            equity = _safe_get(bs, "Stockholders Equity", date) if bs is not None and not bs.empty else None
            total_assets = _safe_get(bs, "Total Assets", date) if bs is not None and not bs.empty else None
            total_debt = _safe_get(bs, "Total Debt", date) if bs is not None and not bs.empty else None

            def safe_ratio(a, b):
                try:
                    return float(a) / float(b) if a is not None and b is not None and float(b) != 0 else None
                except Exception:
                    return None

            metric = FinancialMetrics(
                ticker=ticker,
                report_period=str(date.date()),
                period=period,
                currency=info.get("currency", "USD") or "USD",
                market_cap=info.get("marketCap"),
                enterprise_value=info.get("enterpriseValue"),
                price_to_earnings_ratio=info.get("trailingPE"),
                price_to_book_ratio=info.get("priceToBook"),
                price_to_sales_ratio=info.get("priceToSalesTrailing12Months"),
                enterprise_value_to_ebitda_ratio=info.get("enterpriseToEbitda"),
                enterprise_value_to_revenue_ratio=info.get("enterpriseToRevenue"),
                free_cash_flow_yield=None,
                peg_ratio=info.get("pegRatio"),
                gross_margin=info.get("grossMargins") or safe_ratio(gross_profit, revenue),
                operating_margin=info.get("operatingMargins") or safe_ratio(op_income, revenue),
                net_margin=info.get("profitMargins") or safe_ratio(net_income, revenue),
                return_on_equity=info.get("returnOnEquity"),
                return_on_assets=info.get("returnOnAssets"),
                return_on_invested_capital=info.get("returnOnInvestedCapital"),
                asset_turnover=safe_ratio(revenue, total_assets),
                inventory_turnover=None,
                receivables_turnover=None,
                days_sales_outstanding=None,
                operating_cycle=None,
                working_capital_turnover=None,
                current_ratio=info.get("currentRatio"),
                quick_ratio=info.get("quickRatio"),
                cash_ratio=None,
                operating_cash_flow_ratio=None,
                debt_to_equity=safe_ratio(total_debt, equity) if total_debt and equity else info.get("debtToEquity"),
                debt_to_assets=safe_ratio(total_debt, total_assets),
                interest_coverage=None,
                revenue_growth=info.get("revenueGrowth"),
                earnings_growth=info.get("earningsGrowth"),
                book_value_growth=None,
                earnings_per_share_growth=None,
                free_cash_flow_growth=None,
                operating_income_growth=None,
                ebitda_growth=None,
                payout_ratio=info.get("payoutRatio"),
                earnings_per_share=info.get("trailingEps"),
                book_value_per_share=info.get("bookValue"),
                free_cash_flow_per_share=None,
            )
        else:
            # Older periods: compute what we can from financial statements
            revenue = _safe_get(inc, "Total Revenue", date) if inc is not None else None
            gross_profit = _safe_get(inc, "Gross Profit", date) if inc is not None else None
            op_income = _safe_get(inc, "Operating Income", date) if inc is not None else None
            net_income = _safe_get(inc, "Net Income", date) if inc is not None else None
            equity = _safe_get(bs, "Stockholders Equity", date) if bs is not None else None
            total_assets = _safe_get(bs, "Total Assets", date) if bs is not None else None
            total_debt = _safe_get(bs, "Total Debt", date) if bs is not None else None
            current_assets = _safe_get(bs, "Current Assets", date) if bs is not None else None
            current_liabilities = _safe_get(bs, "Current Liabilities", date) if bs is not None else None
            eps = _safe_get(inc, "Diluted EPS", date) if inc is not None else None

            def safe_ratio(a, b):
                try:
                    return float(a) / float(b) if a is not None and b is not None and float(b) != 0 else None
                except Exception:
                    return None

            metric = FinancialMetrics(
                ticker=ticker,
                report_period=str(date.date()),
                period=period,
                currency=info.get("currency", "USD") or "USD",
                market_cap=None,
                enterprise_value=None,
                price_to_earnings_ratio=None,
                price_to_book_ratio=None,
                price_to_sales_ratio=None,
                enterprise_value_to_ebitda_ratio=None,
                enterprise_value_to_revenue_ratio=None,
                free_cash_flow_yield=None,
                peg_ratio=None,
                gross_margin=safe_ratio(gross_profit, revenue),
                operating_margin=safe_ratio(op_income, revenue),
                net_margin=safe_ratio(net_income, revenue),
                return_on_equity=safe_ratio(net_income, equity),
                return_on_assets=safe_ratio(net_income, total_assets),
                return_on_invested_capital=None,
                asset_turnover=safe_ratio(revenue, total_assets),
                inventory_turnover=None,
                receivables_turnover=None,
                days_sales_outstanding=None,
                operating_cycle=None,
                working_capital_turnover=None,
                current_ratio=safe_ratio(current_assets, current_liabilities),
                quick_ratio=None,
                cash_ratio=None,
                operating_cash_flow_ratio=None,
                debt_to_equity=safe_ratio(total_debt, equity),
                debt_to_assets=safe_ratio(total_debt, total_assets),
                interest_coverage=None,
                revenue_growth=None,
                earnings_growth=None,
                book_value_growth=None,
                earnings_per_share_growth=None,
                free_cash_flow_growth=None,
                operating_income_growth=None,
                ebitda_growth=None,
                payout_ratio=None,
                earnings_per_share=eps,
                book_value_per_share=safe_ratio(equity, _safe_get(bs, "Ordinary Shares Number", date)) if bs is not None else None,
                free_cash_flow_per_share=None,
            )
        metrics_list.append(metric)
        is_first = False

    _cache.set_financial_metrics(cache_key, [m.model_dump() for m in metrics_list])
    return metrics_list


def search_line_items(
    ticker: str,
    line_items: list[str],
    end_date: str,
    period: str = "ttm",
    limit: int = 10,
    api_key: str = None,
) -> list[LineItem]:
    """Fetch financial statement line items from yfinance."""
    try:
        stock = yf.Ticker(ticker)
        info = stock.info or {}

        if period == "annual":
            inc = stock.financials
            bs = stock.balance_sheet
            cf = stock.cashflow
        else:
            inc = stock.quarterly_financials
            bs = stock.quarterly_balance_sheet
            cf = stock.quarterly_cashflow

        inc = _filter_columns_by_date(inc, end_date)
        bs = _filter_columns_by_date(bs, end_date)
        cf = _filter_columns_by_date(cf, end_date)

        # Build union of all dates
        all_dates: list[pd.Timestamp] = []
        for df in (bs, inc, cf):
            if df is not None and not df.empty:
                for col in df.columns:
                    ts = pd.Timestamp(col).tz_localize(None)
                    if ts not in all_dates:
                        all_dates.append(ts)
        all_dates = sorted(set(all_dates), reverse=True)[:limit]
    except Exception as e:
        logger.warning("Failed to fetch line items for %s: %s", ticker, e)
        return []

    if not all_dates:
        return []

    results: list[LineItem] = []

    for date in all_dates:
        extra: dict = {}

        for item_name in line_items:
            value = None

            if item_name in _INCOME_STMT_FIELDS and inc is not None and not inc.empty:
                value = _safe_get(inc, _INCOME_STMT_FIELDS[item_name], date)

            elif item_name in _BALANCE_SHEET_FIELDS and bs is not None and not bs.empty:
                value = _safe_get(bs, _BALANCE_SHEET_FIELDS[item_name], date)

            elif item_name in _CASHFLOW_FIELDS and cf is not None and not cf.empty:
                value = _safe_get(cf, _CASHFLOW_FIELDS[item_name], date)

            # Computed fields
            elif item_name == "book_value_per_share":
                equity = _safe_get(bs, "Stockholders Equity", date) if bs is not None else None
                shares = _safe_get(bs, "Ordinary Shares Number", date) if bs is not None else None
                if equity and shares and float(shares) != 0:
                    value = float(equity) / float(shares)

            elif item_name == "gross_margin":
                revenue = _safe_get(inc, "Total Revenue", date) if inc is not None else None
                gp = _safe_get(inc, "Gross Profit", date) if inc is not None else None
                if revenue and gp and float(revenue) != 0:
                    value = float(gp) / float(revenue)

            elif item_name == "operating_margin":
                revenue = _safe_get(inc, "Total Revenue", date) if inc is not None else None
                oi = _safe_get(inc, "Operating Income", date) if inc is not None else None
                if revenue and oi and float(revenue) != 0:
                    value = float(oi) / float(revenue)

            elif item_name == "debt_to_equity":
                total_debt = _safe_get(bs, "Total Debt", date) if bs is not None else None
                equity = _safe_get(bs, "Stockholders Equity", date) if bs is not None else None
                if total_debt and equity and float(equity) != 0:
                    value = float(total_debt) / float(equity)

            elif item_name == "return_on_invested_capital":
                # NOPAT / Invested Capital approximation
                ebit = _safe_get(inc, "EBIT", date) if inc is not None else None
                total_debt = _safe_get(bs, "Total Debt", date) if bs is not None else None
                equity = _safe_get(bs, "Stockholders Equity", date) if bs is not None else None
                tax_rate = info.get("effectiveTaxRate", 0.21)
                if ebit and total_debt is not None and equity is not None:
                    invested_capital = float(total_debt) + float(equity)
                    if invested_capital != 0:
                        value = float(ebit) * (1 - float(tax_rate)) / invested_capital

            extra[item_name] = value  # Always set (None if unavailable) so attribute access works

        results.append(LineItem(
            ticker=ticker,
            report_period=str(date.date()),
            period=period,
            currency=info.get("currency", "USD") or "USD",
            **extra,
        ))

    return results[:limit]


def get_insider_trades(
    ticker: str,
    end_date: str,
    start_date: str | None = None,
    limit: int = 1000,
    api_key: str = None,
) -> list[InsiderTrade]:
    """Fetch insider trades from cache or yfinance."""
    cache_key = f"{ticker}_{start_date or 'none'}_{end_date}_{limit}"
    if cached_data := _cache.get_insider_trades(cache_key):
        return [InsiderTrade(**trade) for trade in cached_data]

    try:
        stock = yf.Ticker(ticker)
        transactions = stock.insider_transactions
    except Exception as e:
        logger.warning("Failed to fetch insider trades for %s: %s", ticker, e)
        return []

    if transactions is None or transactions.empty:
        return []

    end_dt = pd.Timestamp(end_date)
    start_dt = pd.Timestamp(start_date) if start_date else None

    trades: list[InsiderTrade] = []
    for _, row in transactions.iterrows():
        try:
            trade_date_raw = row.get("Start Date")
            if trade_date_raw is None:
                continue
            trade_date = pd.Timestamp(str(trade_date_raw))
            if trade_date > end_dt:
                continue
            if start_dt and trade_date < start_dt:
                continue

            shares = row.get("Shares")
            value = row.get("Value")
            price_per_share = None
            if shares and value and float(shares) != 0:
                try:
                    price_per_share = float(value) / float(shares)
                except Exception:
                    pass

            trades.append(InsiderTrade(
                ticker=ticker,
                issuer=None,
                name=str(row.get("Insider", "")) or None,
                title=str(row.get("Position", "")) or None,
                is_board_director=None,
                transaction_date=trade_date.strftime("%Y-%m-%d"),
                transaction_shares=float(shares) if shares is not None and pd.notna(shares) else None,
                transaction_price_per_share=price_per_share,
                transaction_value=float(value) if value is not None and pd.notna(value) else None,
                shares_owned_before_transaction=None,
                shares_owned_after_transaction=None,
                security_title=None,
                filing_date=trade_date.strftime("%Y-%m-%d"),
            ))
        except Exception as e:
            logger.debug("Skipping insider trade row: %s", e)
            continue

    trades = trades[:limit]
    _cache.set_insider_trades(cache_key, [t.model_dump() for t in trades])
    return trades


def _fetch_news_alphavantage(
    ticker: str,
    end_date: str,
    start_date: str | None,
    limit: int,
    av_api_key: str,
) -> list[CompanyNews]:
    """Fetch news from Alpha Vantage NEWS_SENTIMENT endpoint."""
    # Alpha Vantage time format: YYYYMMDDTHHMM
    time_to = pd.Timestamp(end_date).strftime("%Y%m%dT2359")
    params = {
        "function": "NEWS_SENTIMENT",
        "tickers": ticker,
        "limit": min(limit, 1000),
        "sort": "LATEST",
        "time_to": time_to,
        "apikey": av_api_key,
    }
    if start_date:
        params["time_from"] = pd.Timestamp(start_date).strftime("%Y%m%dT0000")

    try:
        response = requests.get("https://www.alphavantage.co/query", params=params, timeout=30)
        if response.status_code != 200:
            logger.warning("Alpha Vantage news returned %s for %s", response.status_code, ticker)
            return []
        data = response.json()
    except Exception as e:
        logger.warning("Alpha Vantage news request failed for %s: %s", ticker, e)
        return []

    if "Information" in data or "Note" in data:
        msg = data.get("Information") or data.get("Note", "")
        logger.warning("Alpha Vantage API message: %s", msg[:120])
        return []

    articles = data.get("feed", [])
    news_list: list[CompanyNews] = []

    for article in articles:
        try:
            # time_published format: YYYYMMDDTHHMMSS
            raw_ts = article.get("time_published", "")
            pub_date = datetime.datetime.strptime(raw_ts, "%Y%m%dT%H%M%S")

            authors = article.get("authors", [])
            author = authors[0] if authors else None

            # Prefer ticker-specific sentiment if available
            sentiment = article.get("overall_sentiment_label")
            for ts in article.get("ticker_sentiment", []):
                if ts.get("ticker", "").upper() == ticker.upper():
                    sentiment = ts.get("ticker_sentiment_label", sentiment)
                    break

            news_list.append(CompanyNews(
                ticker=ticker,
                title=article.get("title", ""),
                author=author,
                source=article.get("source", ""),
                date=pub_date.strftime("%Y-%m-%dT%H:%M:%SZ"),
                url=article.get("url", ""),
                sentiment=sentiment,
            ))
        except Exception as e:
            logger.debug("Skipping Alpha Vantage article: %s", e)
            continue

    return news_list


def get_company_news(
    ticker: str,
    end_date: str,
    start_date: str | None = None,
    limit: int = 1000,
    api_key: str = None,
) -> list[CompanyNews]:
    """Fetch company news — uses Alpha Vantage if ALPHA_VANTAGE_API_KEY is set, otherwise yfinance."""
    cache_key = f"{ticker}_{start_date or 'none'}_{end_date}_{limit}"
    if cached_data := _cache.get_company_news(cache_key):
        return [CompanyNews(**news) for news in cached_data]

    av_api_key = os.environ.get("ALPHA_VANTAGE_API_KEY")

    if av_api_key:
        news_list = _fetch_news_alphavantage(ticker, end_date, start_date, limit, av_api_key)
        if news_list:
            _cache.set_company_news(cache_key, [n.model_dump() for n in news_list])
            return news_list
        logger.info("Alpha Vantage returned no news for %s, falling back to yfinance", ticker)

    # Fallback: yfinance (no date filtering, ~10 current headlines only)
    try:
        stock = yf.Ticker(ticker)
        raw_news = stock.news or []
    except Exception as e:
        logger.warning("Failed to fetch news for %s: %s", ticker, e)
        return []

    if not raw_news:
        return []

    end_dt = pd.Timestamp(end_date)
    start_dt = pd.Timestamp(start_date) if start_date else None

    news_list = []
    for item in raw_news:
        try:
            content = item.get("content", {})
            if not content:
                continue
            pub_date_str = content.get("pubDate", "")
            if not pub_date_str:
                continue
            pub_date = pd.Timestamp(pub_date_str)
            if pub_date.tz is not None:
                pub_date = pub_date.tz_localize(None)
            if pub_date > end_dt:
                continue
            if start_dt and pub_date < start_dt:
                continue
            provider = content.get("provider", {})
            canonical = content.get("canonicalUrl", {})
            news_list.append(CompanyNews(
                ticker=ticker,
                title=content.get("title", ""),
                author=None,
                source=provider.get("displayName", "Yahoo Finance"),
                date=pub_date.strftime("%Y-%m-%dT%H:%M:%SZ"),
                url=canonical.get("url", ""),
                sentiment=None,
            ))
        except Exception as e:
            logger.debug("Skipping news item: %s", e)
            continue

    news_list = news_list[:limit]
    _cache.set_company_news(cache_key, [n.model_dump() for n in news_list])
    return news_list


def get_market_cap(
    ticker: str,
    end_date: str,
    api_key: str = None,
) -> float | None:
    """Fetch market cap from yfinance."""
    try:
        stock = yf.Ticker(ticker)
        info = stock.info or {}
        market_cap = info.get("marketCap")
        if market_cap:
            return float(market_cap)
    except Exception as e:
        logger.warning("Failed to fetch market cap for %s: %s", ticker, e)

    # Fallback: try financial metrics
    metrics = get_financial_metrics(ticker, end_date, api_key=api_key)
    if metrics and metrics[0].market_cap:
        return metrics[0].market_cap
    return None


def prices_to_df(prices: list[Price]) -> pd.DataFrame:
    """Convert prices to a DataFrame."""
    df = pd.DataFrame([p.model_dump() for p in prices])
    df["Date"] = pd.to_datetime(df["time"])
    df.set_index("Date", inplace=True)
    numeric_cols = ["open", "close", "high", "low", "volume"]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df.sort_index(inplace=True)
    return df


def get_price_data(ticker: str, start_date: str, end_date: str, api_key: str = None) -> pd.DataFrame:
    prices = get_prices(ticker, start_date, end_date, api_key=api_key)
    return prices_to_df(prices)
