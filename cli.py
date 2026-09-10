
from __future__ import annotations

import argparse
import uuid

from emporio import Agent
from emporio.prompts import PERSONA_NAME

BANNER = f"""
Empório da Música - atendimento com {PERSONA_NAME}
Comandos: /sair encerra · /nova inicia nova conversa
"""

def main() -> None:
    parser = argparse.ArgumentParser(description="Chat com a assistente da Empório da Música")
    parser.add_argument("--session", default=uuid.uuid4().hex[:8], help="id da sessão (histórico persistido)")
    parser.add_argument("--reset", action="store_true", help="limpa o histórico da sessão antes de começar")
    args = parser.parse_args()

    agent = Agent()
    if args.reset:
        agent.reset(args.session)

    print(BANNER)
    session_id = args.session
    while True:
        try:
            message = input("você > ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not message:
            continue
        if message.lower() in ("/sair", "/quit", "sair"):
            break
        if message.lower() in ("/nova", "/novo"):
            agent.reset(session_id)
            session_id = uuid.uuid4().hex[:8]
            print(f"{PERSONA_NAME} > (nova conversa) Oi! Como posso ajudar?")
            continue
        reply = agent.chat(session_id, message)
        print(f"\n{PERSONA_NAME} > {reply}\n")

    print(f"\nAté a próxima! (sessão {session_id})")

if __name__ == "__main__":
    main()
