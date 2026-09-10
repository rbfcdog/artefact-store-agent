
from __future__ import annotations

import sqlite3

HISTORY_LIMIT = 24

def append_message(
    con: sqlite3.Connection, session_id: str, role: str, content: str
) -> None:
    con.execute(
        "INSERT OR IGNORE INTO sessions (session_id) VALUES (?)", (session_id,))
    con.execute(
        "INSERT INTO messages (session_id, role, content) VALUES (?, ?, ?)",
        (session_id, role, content))
    con.commit()

def history(
    con: sqlite3.Connection, session_id: str, limit: int = HISTORY_LIMIT
) -> list[dict[str, str]]:
    rows = con.execute(
        """SELECT role, content FROM (
               SELECT message_id, role, content FROM messages
               WHERE session_id = ? ORDER BY message_id DESC LIMIT ?
           ) ORDER BY message_id ASC""",
        (session_id, limit)).fetchall()
    return [{"role": r["role"], "content": r["content"]} for r in rows]

def clear_session(con: sqlite3.Connection, session_id: str) -> None:
    con.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
    con.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
    con.commit()

