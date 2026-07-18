import logging

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from config import TELEGRAM_BOT_TOKEN, CHECK_INTERVAL_SECONDS
from state import load_state, save_state
from strategy import check_ticker

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

STATUS_LABELS = {
    "waiting_setup": "⏳ a calcular setup",
    "waiting_entry": "👀 à espera do preço de entrada",
    "active": "🟢 trade ativo",
    "no_setup_today": "🚫 sem setup hoje (diferença abaixo do mínimo)",
    "no_data": "⚠️ sem dados suficientes (confirma o símbolo)",
}


async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    state = load_state()
    state["chat_id"] = update.effective_chat.id
    save_state(state)
    await update.message.reply_text(
        "Bot de sinais ativo ✅\n\n"
        "Comandos disponíveis:\n"
        "/add TICKER [TICKER2 ...] — adicionar ticker(s) a monitorizar\n"
        "/remove TICKER — remover ticker\n"
        "/list — ver estado de todos os tickers\n"
        "/help — ver esta mensagem"
    )


async def add_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usa: /add TICKER [TICKER2 ...]\nEx: /add SPY QQQ VOO")
        return

    state = load_state()
    state["chat_id"] = update.effective_chat.id
    added = []
    for raw in context.args:
        ticker = raw.upper().strip()
        if ticker and ticker not in state["tickers"]:
            state["tickers"][ticker] = {"status": "waiting_setup"}
            added.append(ticker)
    save_state(state)

    if added:
        await update.message.reply_text(f"Adicionado(s): {', '.join(added)}")
    else:
        await update.message.reply_text("Esses tickers já estavam a ser monitorizados.")


async def remove_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usa: /remove TICKER")
        return

    state = load_state()
    removed = []
    for raw in context.args:
        ticker = raw.upper().strip()
        if ticker in state["tickers"]:
            del state["tickers"][ticker]
            removed.append(ticker)
    save_state(state)

    if removed:
        await update.message.reply_text(f"Removido(s): {', '.join(removed)}")
    else:
        await update.message.reply_text("Nenhum desses tickers estava a ser monitorizado.")


async def list_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    state = load_state()
    if not state["tickers"]:
        await update.message.reply_text("Ainda não tens tickers. Usa /add TICKER.")
        return

    lines = []
    for ticker, info in state["tickers"].items():
        label = STATUS_LABELS.get(info.get("status"), info.get("status"))
        line = f"*{ticker}* — {label}"
        if info.get("status") in ("waiting_entry", "active"):
            line += (
                f"\n   entrada: {info['entry_price']:.4f} | "
                f"alvo: {info['target_price']:.4f} | "
                f"diff: {info['pct_diff']:.2f}%"
            )
        lines.append(line)

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start_cmd(update, context)


async def check_all_tickers(context: ContextTypes.DEFAULT_TYPE):
    state = load_state()
    chat_id = state.get("chat_id")
    if not chat_id or not state["tickers"]:
        return

    async def send_message(text):
        await context.bot.send_message(chat_id=chat_id, text=text, parse_mode="Markdown")

    changed = False
    for ticker, info in list(state["tickers"].items()):
        try:
            new_info = await check_ticker(ticker, info, send_message)
        except Exception:
            logger.exception(f"Erro ao verificar {ticker}")
            continue
        if new_info != info:
            state["tickers"][ticker] = new_info
            changed = True

    if changed:
        save_state(state)


def main():
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start_cmd))
    application.add_handler(CommandHandler("help", help_cmd))
    application.add_handler(CommandHandler("add", add_cmd))
    application.add_handler(CommandHandler("remove", remove_cmd))
    application.add_handler(CommandHandler("list", list_cmd))

    application.job_queue.run_repeating(
        check_all_tickers, interval=CHECK_INTERVAL_SECONDS, first=10
    )

    logger.info("Bot a arrancar...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
