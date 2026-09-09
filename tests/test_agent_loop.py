
from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from emporio import store
from emporio.agent import Agent

def _msg(content=None, tool_calls=None):
    return SimpleNamespace(content=content, tool_calls=tool_calls)

def _call(call_id, name, arguments):
    return SimpleNamespace(
        id=call_id,
        function=SimpleNamespace(name=name, arguments=arguments),
    )

class ScriptedClient:

    def __init__(self, turns):
        self.turns = list(turns)
        self.seen: list[dict] = []

    def chat(self):
        client = self

        class _Completions:
            def create(self, *, model, messages, tools, temperature):
                client.seen.append(messages)
                return SimpleNamespace(choices=[SimpleNamespace(message=client.turns.pop(0))])

        class _Chat:
            completions = _Completions()

        return SimpleNamespace(chat=_Chat())

def test_tool_roundtrip_and_persistence(tmp_path):
    db = tmp_path / "test.db"
    con = store.connect(db)
    store.load_operational_data(con)

    client = ScriptedClient([
        _msg(tool_calls=[_call("c1", "search_store", json.dumps({"query": "Takamine GD20"}))]),
        _msg(content="O Takamine GD20 custa R$ 2.199,00 e tem 5 unidades em estoque."),
    ])
    agent = Agent(db_path=db, client=client.chat())
    reply = agent.chat("s-test", "quanto custa o Takamine GD20?")

    assert "2.199" in reply
    tool_msg = client.seen[1][-1]
    assert tool_msg["role"] == "tool"
    payload = json.loads(tool_msg["content"])
    product = payload["produtos"][0]
    assert product["name"].startswith("Takamine GD20")
    assert product["price_brl"] == 2199.0
    history = [m["role"] for m in store.connect(db).execute(
        "SELECT role FROM messages WHERE session_id='s-test' ORDER BY message_id"
    ).fetchall()]
    assert history == ["user", "assistant"]

def test_history_is_replayed_and_reset_clears(tmp_path):
    db = tmp_path / "test.db"
    store.load_operational_data(store.connect(db))

    client = ScriptedClient([
        _msg(content="Oi! Em que posso ajudar?"),
        _msg(content="De nada! 🎵"),
    ])
    agent = Agent(db_path=db, client=client.chat())
    agent.chat("s2", "oi")
    agent.chat("s2", "valeu")

    second_call_messages = client.seen[1]
    assert [m["content"] for m in second_call_messages[1:3]] == ["oi", "Oi! Em que posso ajudar?"]

    agent.reset("s2")
    assert session_rows(db, "s2") == []

def session_rows(db, session_id):
    con = store.connect(db)
    return con.execute(
        "SELECT * FROM messages WHERE session_id = ?", (session_id,)).fetchall()
