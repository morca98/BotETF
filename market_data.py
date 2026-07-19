import logging
from datetime import datetime, timedelta

import yfinance as yf

logger = logging.getLogger(__name__)

def get_daily_setup(ticker: str):
    """
    Calcula o setup do dia para um ticker.
    Entrada: Mínima do último dia completo.
    Alvo: Máxima dos últimos 2 dias completos.
    """
    try:
        # Pedimos 5 dias para garantir que temos 2 dias úteis completos, mesmo após fins de semana
        data = yf.Ticker(ticker).history(period="5d", interval="1d")
        if data is None or data.empty or len(data) < 2:
            logger.warning(f"Dados insuficientes para {ticker}")
            return None

        # Remover timezone para evitar conflitos de comparação
        if data.index.tz is not None:
            data.index = data.index.tz_localize(None)

        # Consideramos apenas dias anteriores ao dia atual (UTC/Local conforme o sandbox)
        today = datetime.now().date()
        complete = data[data.index.date < today]

        if len(complete) < 2:
            # Se não houver 2 dias anteriores a hoje (ex: mercado ainda não abriu ou feriado longo)
            # Tentamos incluir o último dia disponível mesmo que seja "hoje" se o mercado estiver fechado
            # Mas a regra diz "último dia", vamos manter o conservadorismo de dias fechados.
            if len(data) >= 2:
                complete = data.iloc[-3:-1] if len(data) > 2 else data.iloc[-2:]
            else:
                return None

        last_day = complete.iloc[-1]
        prev_day = complete.iloc[-2]

        entry_price = float(last_day["Low"])
        # Alvo é a máxima dos últimos 2 dias
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
    except Exception as e:
        logger.error(f"Erro ao obter setup para {ticker}: {e}")
        return None


def get_current_price(ticker: str):
    """Obtém o preço atual com múltiplos fallbacks."""
    # Tentativa 1: fast_info (mais rápido)
    try:
        t = yf.Ticker(ticker)
        price = t.fast_info.get("lastPrice") or t.fast_info.get("last_price")
        if price and price > 0:
            return float(price)
    except Exception:
        pass

    # Tentativa 2: history 1m (mais fiável para preço real)
    try:
        data = yf.Ticker(ticker).history(period="1d", interval="1m")
        if data is not None and not data.empty:
            return float(data["Close"].iloc[-1])
    except Exception:
        pass

    # Tentativa 3: info['regularMarketPrice'] (mais lento, mas por vezes disponível)
    try:
        info = yf.Ticker(ticker).info
        price = info.get("regularMarketPrice") or info.get("currentPrice")
        if price and price > 0:
            return float(price)
    except Exception:
        pass

    return None
