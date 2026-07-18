from datetime import datetime

from config import MIN_PCT_DIFF
from market_data import get_daily_setup, get_current_price

# Estados possíveis para cada ticker:
#   waiting_setup  -> ainda não foi calculado nenhum setup
#   no_setup_today -> setup calculado, mas diferença % abaixo do mínimo -> sem entrada
#   no_data        -> não há dados suficientes para o ticker (símbolo errado?)
#   waiting_entry  -> setup válido, à espera que o preço bata na entrada
#   active         -> trade ativo, à espera do alvo (sem stop loss)


async def check_ticker(ticker: str, info: dict, send_message):
    today_str = datetime.now().date().isoformat()
    status = info.get("status", "waiting_setup")

    # --- Trade já ativo: só falta esperar pelo alvo (sem stop loss) ---
    if status == "active":
        price = get_current_price(ticker)
        if price is None:
            return info
        if price >= info["target_price"]:
            await send_message(
                f"🎯 *{ticker}* — ALVO ATINGIDO\n"
                f"Preço atual: {price:.4f}\n"
                f"Alvo: {info['target_price']:.4f}\n"
                f"Entrada tinha sido: {info['entry_price']:.4f}\n\n"
                f"Trade encerrado no bot (sinal informativo, a decisão de fechar é tua)."
            )
            return {"status": "waiting_setup"}
        return info

    # --- Sem trade ativo: (re)calcular setup se ainda não foi feito hoje ---
    if info.get("last_calc_date") != today_str:
        setup = get_daily_setup(ticker)
        if setup is None:
            return {"status": "no_data", "last_calc_date": today_str}

        if setup["pct_diff"] < MIN_PCT_DIFF:
            return {
                "status": "no_setup_today",
                "last_calc_date": today_str,
                "pct_diff": setup["pct_diff"],
            }

        info = {
            "status": "waiting_entry",
            "last_calc_date": today_str,
            "entry_price": setup["entry_price"],
            "target_price": setup["target_price"],
            "pct_diff": setup["pct_diff"],
        }

    # --- À espera do preço de entrada ---
    if info.get("status") == "waiting_entry":
        price = get_current_price(ticker)
        if price is None:
            return info
        if price <= info["entry_price"]:
            await send_message(
                f"🟢 *{ticker}* — SINAL DE ENTRADA\n"
                f"Preço atual: {price:.4f}\n"
                f"Entrada (mínima do último dia): {info['entry_price']:.4f}\n"
                f"Alvo (máxima dos últimos 2 dias): {info['target_price']:.4f}\n"
                f"Diferença: {info['pct_diff']:.2f}%\n"
                f"Sem stop loss definido."
            )
            info["status"] = "active"
            info["entry_time"] = datetime.now().isoformat()

    return info
