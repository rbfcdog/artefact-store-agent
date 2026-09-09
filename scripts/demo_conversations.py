
from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from emporio import session, store
from emporio.agent import Agent
from emporio.config import OPENAI_MODEL, STORE_TZ
from emporio.prompts import PERSONA_NAME

OUT_DIR = Path(__file__).resolve().parent.parent / "conversations"

SCENARIOS: list[tuple[str, str, list[str]]] = [
    (
        "01-catalogo-e-orcamento.md",
        "Catálogo com orçamento - consulta em tempo real",
        [
            "Oi! Quais opções de violões vocês têm custando até R$1000?",
            "E o mais barato dele, qual é? Ele é bom pra quem tá começando?",
        ],
    ),
    (
        "02-informacoes-da-loja.md",
        "Informações gerais da loja - políticas",
        [
            "Oi, qual o endereço de vocês?",
            "E vocês abrem no sábado?",
        ],
    ),
    (
        "03-preco-e-pagamento.md",
        "Preço de produto específico + condições de pagamento",
        [
            "Quanto custa o Takamine GD20?",
            "Se eu pagar no PIX tem desconto? E em quantas vezes posso parcelar?",
        ],
    ),
    (
        "04-devolucao-arrependimento.md",
        "Não trivial: devolução - dados do pedido + política aplicada",
        [
            "Me arrependi da minha compra, posso devolver meu pedido?",
            "Claro! Meu telefone é (67) 99812-3456",
        ],
    ),
    (
        "05-fora-do-escopo.md",
        "Fora do escopo: acessórios e assunto não relacionado",
        [
            "Vocês têm corda de violão e palheta?",
            "E aí, o que você acha do jogo do Brasil ontem?",
        ],
    ),
]

def run_scenario(agent: Agent, con, slug: str, messages: list[str]) -> str:
    session_id = f"demo-{slug}"
    agent.reset(session_id)
    for message in messages:
        print(f"  você > {message}")
        reply = agent.chat(session_id, message)
        print(f"  {PERSONA_NAME} > {reply[:80]}...")
    return session_id

def dump(con, session_id: str, title: str, model: str) -> str:
    lines = [
        f"# {title}",
        "",
        f"- session: `{session_id}` · model: `{model}` · "
        f"generated: {datetime.now().strftime('%Y-%m-%d')}",
        "- transcript dumped verbatim from the persisted session",
        "",
    ]
    for m in session.history(con, session_id):
        who = "Cliente" if m["role"] == "user" else PERSONA_NAME
        lines.append(f"**{who}:** {m['content']}")
        lines.append("")
    return "\n".join(lines)

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default=OPENAI_MODEL)
    args = parser.parse_args()

    agent = Agent(model=args.model)
    OUT_DIR.mkdir(exist_ok=True)
    for filename, title, messages in SCENARIOS:
        slug = filename.split("-", 1)[0]
        print(f"\n=== {title}")
        session_id = run_scenario(agent, agent.con, slug, messages)
        text = dump(agent.con, session_id, title, args.model)
        (OUT_DIR / filename).write_text(text, encoding="utf-8")
        print(f"  written: conversations/{filename}")
    _ = STORE_TZ

if __name__ == "__main__":
    main()
