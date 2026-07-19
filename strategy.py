import logging
from datetime import datetime

from config import MIN_PCT_DIFF
from market_data import get_daily_setup, get_current_price

logger = logging.getLogger(__name__)

async def check_ticker(ticker: str, info: dict, send_message, state):
    """
    Lógica central de monitorização e sinais.
    """
    today_str = datetime.now().date().isoformat()
    status = info.get("status", "waiting_setup")

    # 1. Verificar se existe trade ativo
    if status == "active":
        price = get_current_price(ticker)
        if price is None:
            return info
        
        target = info.get("target_price")
        if price >= target:
            msg = (
                f"🎯 *{ticker}* — ALVO ATINGIDO\n"
                f"💰 Preço de Venda: {price:.4f}\n"
                f"📥 Entrada foi em: {info['entry_price']:.4f}\n"
                f"📈 Lucro Estimado: {info['pct_diff']:.2f}%\n\n"
                f"Trade concluído com sucesso! ✅"
            )
            await send_message(msg)
            # Registar no histórico
            timestamp = datetime.now().strftime("%d/%m %H:%M")
            state["history"].append(f"[{timestamp}] ✅ {ticker}: Alvo atingido ({info['pct_diff']:.2f}%)")
            
            # Após fechar, volta a procurar setup para o dia seguinte
            return {"status": "waiting_setup", "last_calc_date": today_str}
        return info

    # 2. Se não houver trade ativo, verificar se já calculamos o setup hoje
    if info.get("last_calc_date") != today_str or status == "waiting_setup":
        setup = get_daily_setup(ticker)
        if setup is None:
            if status == "no_data":
                return info
            return {"status": "no_data", "last_calc_date": today_str}

        if setup["pct_diff"] < MIN_PCT_DIFF:
            return {
                "status": "no_setup_today",
                "last_calc_date": today_str,
                "pct_diff": setup["pct_diff"],
                "entry_price": setup["entry_price"],
                "target_price": setup["target_price"]
            }

        info = {
            "status": "waiting_entry",
            "last_calc_date": today_str,
            "entry_price": setup["entry_price"],
            "target_price": setup["target_price"],
            "pct_diff": setup["pct_diff"],
        }

    # 3. Se estivermos à espera de entrada, verificar preço atual
    if info.get("status") == "waiting_entry":
        price = get_current_price(ticker)
        if price is None:
            return info
            
        if price <= info["entry_price"]:
            msg = (
                f"🟢 *{ticker}* — SINAL DE ENTRADA\n"
                f"💵 Preço Atual: {price:.4f}\n"
                f"📥 Entrada (Mín. Ontem): {info['entry_price']:.4f}\n"
                f"🎯 Alvo (Máx. 2 Dias): {info['target_price']:.4f}\n"
                f"📊 Potencial: {info['pct_diff']:.2f}%\n\n"
                f"⚠️ Sem Stop Loss definido."
            )
            await send_message(msg)
            # Registar no histórico
            timestamp = datetime.now().strftime("%d/%m %H:%M")
            state["history"].append(f"[{timestamp}] 🟢 {ticker}: Entrada em {price:.4f}")
            
            info["status"] = "active"
            info["entry_time"] = datetime.now().isoformat()
            info["actual_entry_price"] = price

    return info
