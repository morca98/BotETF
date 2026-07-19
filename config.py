import os

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CHECK_INTERVAL_SECONDS = int(os.environ.get("CHECK_INTERVAL_SECONDS", "60"))
MIN_PCT_DIFF = float(os.environ.get("MIN_PCT_DIFF", "1.0"))

# Se estivermos no Railway com volume montado em /data, usamos isso.
# Caso contrário, usamos o diretório local.
STATE_FILE = os.environ.get("STATE_FILE", "state.json")

def validate_config():
    if not TELEGRAM_BOT_TOKEN:
        raise RuntimeError(
            "Falta definir a variável de ambiente TELEGRAM_BOT_TOKEN "
            "(token do bot obtido através do @BotFather no Telegram)."
        )
