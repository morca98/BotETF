from datetime import datetime

import yfinance as yf


def get_daily_setup(ticker: str):
    """
    Calcula o setup do dia para um ticker com base nas sessões diárias
    COMPLETAS mais recentes (exclui a sessão de hoje, mesmo que já tenha
    dados parciais, para não usar uma máxima/mínima ainda a formar-se).

    Devolve um dict com entry_price (mínima do último dia completo),
    target_price (máxima entre os últimos 2 dias completos) e pct_diff,
    ou None se não houver dados suficientes.
    """
    data = yf.Ticker(ticker).history(period="15d", interval="1d")
    if data is None or data.empty:
        return None

    if data.index.tz is not None:
        data.index = data.index.tz_localize(None)

    today = datetime.now().date()
    complete = data[data.index.date < today]

    if len(complete) < 2:
        return None

    last_day = complete.iloc[-1]
    prev_day = complete.iloc[-2]

    entry_price = float(last_day["Low"])
    target_price = float(max(last_day["High"], prev_day["High"]))

    if entry_price <= 0:
        return None

    pct_diff = (target_price - entry_price) / entry_price * 100
    last_day_date = complete.index[-1].date().isoformat()

    return {
        "entry_price": round(entry_price, 4),
        "target_price": round(target_price, 4),
        "pct_diff": round(pct_diff, 4),
        "last_day_date": last_day_date,
    }


def get_current_price(ticker: str):
    """Preço mais recente disponível para o ticker (near real-time)."""
    try:
        fast = yf.Ticker(ticker).fast_info
        price = fast.get("lastPrice") or fast.get("last_price")
        if price:
            return float(price)
    except Exception:
        pass

    try:
        data = yf.Ticker(ticker).history(period="1d", interval="1m")
        if data is not None and not data.empty:
            return float(data["Close"].iloc[-1])
    except Exception:
        pass

    return None
