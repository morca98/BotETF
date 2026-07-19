import logging
from datetime import datetime
from telegram import Update, constants
from telegram.ext import Application, CommandHandler, ContextTypes

from config import TELEGRAM_BOT_TOKEN, CHECK_INTERVAL_SECONDS, validate_config
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

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log the error and send a telegram message to notify the developer."""
    logger.error("Exception while handling an update:", exc_info=context.error)
    if isinstance(update, Update) and update.effective_message:
        await update.effective_message.reply_text("❌ Ocorreu um erro interno no bot. Tenta novamente mais tarde.")

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"Comando /start recebido de {update.effective_chat.id}")
    state = load_state()
    state["chat_id"] = update.effective_chat.id
    save_state(state)
    
    welcome_text = (
        "🚀 *Bot de Sinais ETF/Stocks Ativo*\n\n"
        "Vou monitorizar os preços e enviar sinais baseados na estratégia:\n"
        "• *Entrada:* Mínima do dia anterior\n"
        "• *Alvo:* Máxima dos últimos 2 dias\n"
        "• *Filtro:* Mínimo 1% de diferença\n\n"
        "*Comandos:*\n"
        "➕ /add TICKER — Adicionar ticker\n"
        "❌ /remove TICKER — Remover ticker\n"
        "📋 /list — Ver estado atual\n"
        "📜 /history — Ver últimos sinais\n"
        "🧪 /test — Testar visualização de sinal\n"
        "🏓 /ping — Verificar se o bot está online\n"
        "❓ /help — Mostrar esta ajuda"
    )
    await update.message.reply_text(welcome_text, parse_mode=constants.ParseMode.MARKDOWN)

async def ping_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"Comando /ping recebido de {update.effective_chat.id}")
    now = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    await update.message.reply_text(f"🏓 *Pong!*\nBot online e a monitorizar.\n🕒 {now}", parse_mode=constants.ParseMode.MARKDOWN)

async def test_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"Comando /test recebido de {update.effective_chat.id}")
    test_ticker = "TEST"
    test_entry = 100.00
    test_target = 101.50
    test_diff = 1.50
    
    entry_msg = (
        f"🧪 *[TESTE]* 🟢 *{test_ticker}* — SINAL DE ENTRADA\n"
        f"💵 Preço Atual: {test_entry:.2f}\n"
        f"📥 Entrada (Mín. Ontem): {test_entry:.2f}\n"
        f"🎯 Alvo (Máx. 2 Dias): {test_target:.2f}\n"
        f"📊 Potencial: {test_diff:.2f}%\n\n"
        f"⚠️ Sem Stop Loss definido."
    )
    
    target_msg = (
        f"🧪 *[TESTE]* 🎯 *{test_ticker}* — ALVO ATINGIDO\n"
        f"💰 Preço de Venda: {test_target:.2f}\n"
        f"📥 Entrada foi em: {test_entry:.2f}\n"
        f"📈 Lucro Estimado: {test_diff:.2f}%\n\n"
        f"Trade concluído com sucesso! ✅"
    )
    
    await update.message.reply_text("Iniciando teste de visualização de sinais...", parse_mode=constants.ParseMode.MARKDOWN)
    await update.message.reply_text(entry_msg, parse_mode=constants.ParseMode.MARKDOWN)
    await update.message.reply_text("--- Simulação de Alvo Atingido (abaixo) ---", parse_mode=constants.ParseMode.MARKDOWN)
    await update.message.reply_text(target_msg, parse_mode=constants.ParseMode.MARKDOWN)

async def history_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"Comando /history recebido de {update.effective_chat.id}")
    state = load_state()
    history = state.get("history", [])
    if not history:
        await update.message.reply_text("📜 O histórico de sinais ainda está vazio.")
        return

    message = "📜 *Últimos Sinais Enviados:*\n\n"
    for entry in reversed(history[-10:]):
        message += f"{entry}\n"

    await update.message.reply_text(message, parse_mode=constants.ParseMode.MARKDOWN)

async def add_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"Comando /add recebido de {update.effective_chat.id} com args {context.args}")
    if not context.args:
        await update.message.reply_text("💡 Exemplo: `/add SPY`", parse_mode=constants.ParseMode.MARKDOWN)
        return

    state = load_state()
    state["chat_id"] = update.effective_chat.id
    
    added = []
    raw_args = " ".join(context.args).replace(",", " ").split()
    
    for raw in raw_args:
        ticker = raw.upper().strip().replace("$", "")
        if ticker and ticker not in state["tickers"]:
            state["tickers"][ticker] = {"status": "waiting_setup"}
            added.append(ticker)
    
    if added:
        save_state(state)
        await update.message.reply_text(f"✅ Adicionado com sucesso: {', '.join(added)}\nO bot começará a monitorizar em breve.")
        # Trigger imediato de verificação
        context.job_queue.run_once(check_all_tickers_job, when=1)
    else:
        await update.message.reply_text("ℹ️ Esses tickers já estão na lista ou o formato é inválido.")

async def remove_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"Comando /remove recebido de {update.effective_chat.id}")
    if not context.args:
        await update.message.reply_text("💡 Exemplo: `/remove SPY`", parse_mode=constants.ParseMode.MARKDOWN)
        return

    state = load_state()
    state["chat_id"] = update.effective_chat.id
    
    removed = []
    raw_args = " ".join(context.args).replace(",", " ").split()
    
    for raw in raw_args:
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
    logger.info(f"Comando /list recebido de {update.effective_chat.id}")
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

async def check_all_tickers_job(context: ContextTypes.DEFAULT_TYPE):
    """Job wrapper para a função de verificação."""
    await check_all_tickers(context)

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
    for ticker in list(state["tickers"].keys()):
        info = state["tickers"][ticker]
        try:
            new_info = await check_ticker(ticker, info, send_message, state)
            if new_info != info:
                state["tickers"][ticker] = new_info
                changed = True
        except Exception as e:
            logger.error(f"Erro ao processar {ticker}: {e}")

    if changed:
        save_state(state)

def main():
    try:
        validate_config()
    except RuntimeError as e:
        logger.error(str(e))
        return

    # Criar a aplicação com tratamento de erros global
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    application.add_error_handler(error_handler)

    # Handlers de comandos
    application.add_handler(CommandHandler("start", start_cmd))
    application.add_handler(CommandHandler("help", help_cmd))
    application.add_handler(CommandHandler("ping", ping_cmd))
    application.add_handler(CommandHandler("test", test_cmd))
    application.add_handler(CommandHandler("history", history_cmd))
    application.add_handler(CommandHandler("add", add_cmd))
    application.add_handler(CommandHandler("remove", remove_cmd))
    application.add_handler(CommandHandler("list", list_cmd))

    # Job Queue para verificações periódicas
    application.job_queue.run_repeating(
        check_all_tickers_job, 
        interval=CHECK_INTERVAL_SECONDS, 
        first=10,
        name="check_tickers_periodic"
    )

    logger.info(f"Bot iniciado com sucesso. Verificação a cada {CHECK_INTERVAL_SECONDS}s")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
