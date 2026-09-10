
from __future__ import annotations
import datetime as _dt
import json
import sqlite3
import threading
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from emporio import session, store, tools
from emporio.config import DB_PATH, OPENAI_MODEL, STORE_TZ
from emporio.prompts import build_system_prompt

MAX_TOOL_ROUNDS = 6

_CHAT_LOCK = threading.Lock()

class Agent:
    def __init__(
        self,
        db_path: Path | str = DB_PATH,
        model: str = OPENAI_MODEL,
        client: Any = None,
    ) -> None:
        self.con: sqlite3.Connection = store.connect(db_path)
        self.model = model
        if client is None:
            from openai import OpenAI
            try:
                client = OpenAI()
            except Exception as exc:
                raise RuntimeError(
                    "OPENAI_API_KEY não configurada. Copie .env.example para "
                    ".env e informe sua chave (veja o README)."
                ) from exc
        self.client = client

    def chat(self, session_id: str, message: str) -> str:
        with _CHAT_LOCK:
            session.append_message(self.con, session_id, "user", message)

            today = _dt.datetime.now(ZoneInfo(STORE_TZ)).date()
            messages = [
                {"role": "system", "content": build_system_prompt(today)},
                *session.history(self.con, session_id),
            ]

            for _ in range(MAX_TOOL_ROUNDS):
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    tools=tools.TOOL_SCHEMAS,
                    temperature=0.3,
                )
                choice = response.choices[0].message

                if not choice.tool_calls:
                    reply = choice.content or ""
                    session.append_message(self.con, session_id, "assistant", reply)
                    return reply

                messages.append(choice)
                for call in choice.tool_calls:
                    result = tools.run_tool(self.con, call.function.name, call.function.arguments)
                    messages.append({
                        "role": "tool",
                        "tool_call_id": call.id,
                        "content": json.dumps(result, ensure_ascii=False, default=str),
                    })

            reply = ("Desculpa, tive um problema pra consultar nossos sistemas agora. "
                     "Pode tentar de novo em instantes?")
            session.append_message(self.con, session_id, "assistant", reply)
            return reply

    def reset(self, session_id: str) -> None:
        with _CHAT_LOCK:
            session.clear_session(self.con, session_id)
