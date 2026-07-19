import logging
from telegram import Update, constants
from telegram.ext import Application, CommandHandler, ContextTypes

from config import TELEGRAM_BOT_TOKEN, CHECK_INTERVAL_SECONDS
from state import load_state, save_state
from strategy import check_ticker

# Configuração de Logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

STATUS_LABELS = {
    "waiting_setup": "⏳ A calcular setup...",
    "waiting_entry": "👀 À espera de entrada",
    "active": "🟢 TRADE ATIVO",
    "no_setup_today": "🚫 Sem volatilidade ( < 1% )",
    "no_data": "⚠️ Erro de dados / Ticker inválido",
}

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    state = load_state()
    state["chat_id"] = update.effective_chat.id
    save_state(state)
    
    welcome_text = (
        "🚀 *Bot de Sinais ETF/Stocks Ativo*\n\n"
        "Vou monitorizar os preços e enviar sinais baseados na estratégia:\n"
        "• *Entrada:* Mínima do dia anterior\n"
        "• *Alvo:* Máxima dos últimos 2 dias\n"
        "• *Filtro:* Mínimo 1% de diferença\n"
        "• *Stop:* Não utiliza stop loss\n\n"
        "*Comandos:*\n"
        "➕ /add TICKER — Adicionar ticker\n"
        "❌ /remove TICKER — Remover ticker\n"
        "📋 /list — Ver estado atual\n"
        "❓ /help — Mostrar esta ajuda"
    )
    await update.message.reply_text(welcome_text, parse_mode=constants.ParseMode.MARKDOWN)

async def add_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("💡 Exemplo: `/add SPY` ou `/add QQQ AAPL`", parse_mode=constants.ParseMode.MARKDOWN)
        return

    state = load_state()
    state["chat_id"] = update.effective_chat.id
    added = []
    for raw in context.args:
        ticker = raw.upper().strip().replace("$", "")
        if ticker and ticker not in state["tickers"]:
            state["tickers"][ticker] = {"status": "waiting_setup"}
            added.append(ticker)
    
    if added:
        save_state(state)
        await update.message.reply_text(f"✅ Adicionado com sucesso: {', '.join(added)}")
    else:
        await update.message.reply_text("ℹ️ Esses tickers já estão na lista ou são inválidos.")

async def remove_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("💡 Exemplo: `/remove SPY`", parse_mode=constants.ParseMode.MARKDOWN)
        return

    state = load_state()
    removed = []
    for raw in context.args:
        ticker = raw.upper().strip().replace("$", "")
        if ticker in state["tickers"]:
            del state["tickers"][ticker]
            removed.append(ticker)
    
    if removed:
        save_state(state)
        await update.message.reply_text(f"🗑️ Removido: {', '.join(removed)}")
    else:
        await update.message.reply_text("ℹ️ Ticker não encontrado na lista.")

async def list_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    state = load_state()
    if not state["tickers"]:
        await update.message.reply_text("📭 A lista de monitorização está vazia. Usa /add.")
        return

    message = "📊 *Estado Atual da Carteira:*\n\n"
    for ticker, info in state["tickers"].items():
        status = info.get("status", "waiting_setup")
        label = STATUS_LABELS.get(status, status)
        
        message += f"*{ticker}*\n"
        message += f"└ Status: {label}\n"
        
        if status in ("waiting_entry", "active", "no_setup_today"):
            entry = info.get("entry_price", 0)
            target = info.get("target_price", 0)
            diff = info.get("pct_diff", 0)
            message += f"└ In: {entry:.2f} | Out: {target:.2f} | Diff: {diff:.2f}%\n"
        
        message += "\n"

    await update.message.reply_text(message, parse_mode=constants.ParseMode.MARKDOWN)

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start_cmd(update, context)

async def check_all_tickers(context: ContextTypes.DEFAULT_TYPE):
    state = load_state()
    chat_id = state.get("chat_id")
    if not chat_id or not state["tickers"]:
        return

    async def send_message(text):
        try:
            await context.bot.send_message(chat_id=chat_id, text=text, parse_mode=constants.ParseMode.MARKDOWN)
        except Exception as e:
            logger.error(f"Erro ao enviar mensagem para {chat_id}: {e}")

    changed = False
    # Usar list(keys) para evitar erro de mutação durante iteração
    for ticker in list(state["tickers"].keys()):
        info = state["tickers"][ticker]
        try:
            new_info = await check_ticker(ticker, info, send_message)
            if new_info != info:
                state["tickers"][ticker] = new_info
                changed = True
        except Exception as e:
            logger.error(f"Erro ao processar {ticker}: {e}")

    if changed:
        save_state(state)

def main():
    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN não configurado!")
        return

    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start_cmd))
    application.add_handler(CommandHandler("help", help_cmd))
    application.add_handler(CommandHandler("add", add_cmd))
    application.add_handler(CommandHandler("remove", remove_cmd))
    application.add_handler(CommandHandler("list", list_cmd))

    # Executar verificação periódica
    application.job_queue.run_repeating(
        check_all_tickers, 
        interval=CHECK_INTERVAL_SECONDS, 
        first=10,
        name="check_tickers_job"
    )

    logger.info(f"Bot iniciado. Intervalo de verificação: {CHECK_INTERVAL_SECONDS}s")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
