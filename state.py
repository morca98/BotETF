import json
import os
import threading

from config import STATE_FILE

_lock = threading.Lock()

DEFAULT_STATE = {
    "chat_id": None,
    "tickers": {},
}


def load_state():
    with _lock:
        if not os.path.exists(STATE_FILE):
            return json.loads(json.dumps(DEFAULT_STATE))
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                data.setdefault("chat_id", None)
                data.setdefault("tickers", {})
                return data
        except (json.JSONDecodeError, FileNotFoundError):
            return json.loads(json.dumps(DEFAULT_STATE))


def save_state(state):
    with _lock:
        tmp_file = STATE_FILE + ".tmp"
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2, ensure_ascii=False)
        os.replace(tmp_file, STATE_FILE)
