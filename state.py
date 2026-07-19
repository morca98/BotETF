import json
import os
import threading

from config import STATE_FILE

_lock = threading.Lock()

DEFAULT_STATE = {
    "chat_id": None,
    "tickers": {},
    "history": [],
}

def ensure_dir():
    """Garante que a pasta onde o ficheiro de estado reside existe."""
    directory = os.path.dirname(STATE_FILE)
    if directory and not os.path.exists(directory):
        try:
            os.makedirs(directory, exist_ok=True)
        except Exception as e:
            print(f"Erro ao criar diretório {directory}: {e}")

def load_state():
    with _lock:
        ensure_dir()
        if not os.path.exists(STATE_FILE):
            return json.loads(json.dumps(DEFAULT_STATE))
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                data.setdefault("chat_id", None)
                data.setdefault("tickers", {})
                data.setdefault("history", [])
                return data
        except (json.JSONDecodeError, FileNotFoundError):
            return json.loads(json.dumps(DEFAULT_STATE))

def save_state(state):
    with _lock:
        ensure_dir()
        # Limitar histórico
        if "history" in state and len(state["history"]) > 20:
            state["history"] = state["history"][-20:]
            
        tmp_file = STATE_FILE + ".tmp"
        try:
            with open(tmp_file, "w", encoding="utf-8") as f:
                json.dump(state, f, indent=2, ensure_ascii=False)
            os.replace(tmp_file, STATE_FILE)
        except Exception as e:
            # Fallback se falhar a escrita atómica (ex: permissões no diretório)
            with open(STATE_FILE, "w", encoding="utf-8") as f:
                json.dump(state, f, indent=2, ensure_ascii=False)
            if os.path.exists(tmp_file):
                os.remove(tmp_file)
            raise e
