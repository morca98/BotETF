import logging
from datetime import datetime

from config import MIN_PCT_DIFF
from market_data import get_daily_setup, get_current_price

logger = logging.getLogger(__name__)

async def check_ticker(ticker: str, info: dict, send_message):
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
            await send_message(
                f"🎯 *{ticker}* — ALVO ATINGIDO\n"
                f"💰 Preço de Venda: {price:.4f}\n"
                f"📥 Entrada foi em: {info['entry_price']:.4f}\n"
                f"📈 Lucro Estimado: {info['pct_diff']:.2f}%\n\n"
                f"Trade concluído com sucesso! ✅"
            )
            # Após fechar, volta a procurar setup para o dia seguinte
            return {"status": "waiting_setup", "last_calc_date": today_str}
        return info

    # 2. Se não houver trade ativo, verificar se já calculamos o setup hoje
    if info.get("last_calc_date") != today_str or status == "waiting_setup":
        setup = get_daily_setup(ticker)
        if setup is None:
            # Mantemos o estado anterior mas marcamos a tentativa se for erro de dados
            if status == "no_data":
                return info
            return {"status": "no_data", "last_calc_date": today_str}

        # Regra: A diferença percentual tem de ser >= 1% (MIN_PCT_DIFF)
        if setup["pct_diff"] < MIN_PCT_DIFF:
            return {
                "status": "no_setup_today",
                "last_calc_date": today_str,
                "pct_diff": setup["pct_diff"],
                "entry_price": setup["entry_price"],
                "target_price": setup["target_price"]
            }

        # Setup válido encontrado
        info = {
            "status": "waiting_entry",
            "last_calc_date": today_str,
            "entry_price": setup["entry_price"],
            "target_price": setup["target_price"],
            "pct_diff": setup["pct_diff"],
        }
        # Opcional: Avisar que um setup foi detectado e estamos à espera da entrada
        # await send_message(f"👀 *{ticker}* — Setup detectado! À espera de entrada em {info['entry_price']:.4f}")

    # 3. Se estivermos à espera de entrada, verificar preço atual
    if info.get("status") == "waiting_entry":
        price = get_current_price(ticker)
        if price is None:
            return info
            
        # Regra: Entra na mínima do último dia
        if price <= info["entry_price"]:
            await send_message(
                f"🟢 *{ticker}* — SINAL DE ENTRADA\n"
                f"💵 Preço Atual: {price:.4f}\n"
                f"📥 Entrada (Mín. Ontem): {info['entry_price']:.4f}\n"
                f"🎯 Alvo (Máx. 2 Dias): {info['target_price']:.4f}\n"
                f"📊 Potencial: {info['pct_diff']:.2f}%\n\n"
                f"⚠️ Sem Stop Loss definido."
            )
            info["status"] = "active"
            info["entry_time"] = datetime.now().isoformat()
            info["actual_entry_price"] = price

    return info
