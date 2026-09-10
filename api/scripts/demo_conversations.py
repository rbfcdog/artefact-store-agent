
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
            "Entendi. O Tagima Memphis e o Giannini têm muita diferença? Qual você indicaria pra quem quer tocar rock?",
            "Legal, vou ficar com o Giannini! Se eu quiser comprar ele junto com uma bateria acústica, tem desconto comprando os dois?",
            "Perfeito. E quanto tempo costuma demorar pra chegar aqui no centro de Campo Grande?",
        ],
    ),
    (
        "02-informacoes-da-loja.md",
        [
            "Oi! Vocês têm loja física ou vendem só online?",
            "Legal, e vocês abrem no sábado? Eu queria passar aí pra testar uns teclados.",
            "Maravilha. Tem estacionamento perto ou é muito ruim de parar aí na rua da loja?",
            "Entendi. Se eu for de manhã, consigo sair com o instrumento na hora ou tem que esperar vir do estoque?",
        ],
    ),
    (
        "03-preco-e-pagamento.md",
        [
            "Olá! Quanto custa o Takamine GD20 e o teclado Yamaha P-45?",
            "Se eu pagar no PIX, tem desconto no Takamine?",
            "E se eu quiser parcelar o teclado, qual é o máximo de vezes que dá pra fazer sem juros? Aceitam Elo?",
            "Ótimo! E tem alguma promoção rolando para quem compra na primeira vez pelo site?",
        ],
    ),
    (
        "04-devolucao-arrependimento.md",
        [
            "Me arrependi da minha compra, posso devolver meu pedido?",
            "Meu telefone é (67) 99812-3456",
            "Poxa, que pena que já passou do prazo. Mas então, como eu faço pra comprar uma palheta e um cabo de guitarra com vocês?",
            "Entendi, vocês só trabalham com os instrumentos mesmo. Tem algum modelo da Fender chegando?",
        ],
    ),
    (
        "05-fora-do-escopo.md",
        [
            "Vocês têm bateria da marca Pearl?",
            "Ah, uma pena. Mas me diz uma coisa, o que você achou do jogo do Brasil ontem?",
            "Hahaha tudo bem. Queria saber também como faço pra consertar o braço do meu violão, vocês têm luthier?",
            "Beleza. E aquele meu pedido 14, como tá o status dele?",
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
