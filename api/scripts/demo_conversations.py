
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from emporio import session
from emporio.agent import Agent
from emporio.config import OPENAI_MODEL

OUT_DIR = Path(__file__).resolve().parents[2] / "conversations"

SCENARIOS: list[tuple[str, list[str]]] = [
    (
        "01-catalogo-e-orcamento.md",
        [
            "Oi! Quais opções de violões vocês têm custando até R$1000?",
            "E o mais barato desses, qual é? É bom pra quem tá começando?",
        ],
    ),
    (
        "02-informacoes-da-loja.md",
        [
            "Qual o endereço de vocês?",
            "Vocês abrem no sábado? Que horas?",
        ],
    ),
    (
        "03-preco-e-pagamento.md",
        [
            "Quanto custa o Takamine GD20?",
            "Se eu pagar no PIX tem desconto? E em quantas vezes posso parcelar?",
        ],
    ),
    (
        "04-devolucao-arrependimento.md",
        [
            "Me arrependi da minha compra, posso devolver meu pedido?",
            "Claro! Meu telefone é (67) 99812-3456",
        ],
    ),
    (
        "05-fora-do-escopo.md",
        [
            "Vocês têm cabo de guitarra e palheta?",
            "Entendi. E aí, o que você acha do jogo do Brasil ontem?",
            "Certo! Vocês têm algum violão da Fender?",
        ],
    ),
]


def run_scenario(agent: Agent, slug: str, messages: list[str]) -> str:
    session_id = f"demo-{slug}"
    agent.reset(session_id)
    for message in messages:
        agent.chat(session_id, message)
    return session_id


def dump(con, session_id: str, model: str) -> str:
    lines = [f"model: {model}", ""]
    for m in session.history(con, session_id):
        who = "Cliente" if m["role"] == "user" else "Agente"
        lines.append(f"**{who}:** {m['content']}")
        lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default=OPENAI_MODEL)
    args = parser.parse_args()

    agent = Agent(model=args.model)
    OUT_DIR.mkdir(exist_ok=True)
    for filename, messages in SCENARIOS:
        slug = filename.split("-", 1)[0]
        session_id = run_scenario(agent, slug, messages)
        text = dump(agent.con, session_id, args.model)
        (OUT_DIR / filename).write_text(text, encoding="utf-8")
        print(f"written: conversations/{filename}")


if __name__ == "__main__":
    main()
