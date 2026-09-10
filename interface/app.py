from __future__ import annotations

import os
import uuid

import httpx
import streamlit as st

API_URL = os.environ.get("API_URL", "http://localhost:8080")
GREETING = (
    "Olá! Sou o agente de atendimento da Empório da Música. "
    "Pergunte sobre instrumentos, preços, promoções ou sobre o seu pedido."
)


def new_conversation() -> None:
    try:
        httpx.post(
            f"{API_URL}/api/reset",
            json={"session_id": st.session_state.session_id},
            timeout=10,
        )
    except httpx.HTTPError:
        pass
    st.session_state.session_id = uuid.uuid4().hex[:8]
    st.session_state.messages = [{"role": "assistant", "content": GREETING}]


st.set_page_config(page_title="Empório da Música - atendimento", layout="centered")

if "session_id" not in st.session_state:
    st.session_state.session_id = uuid.uuid4().hex[:8]
if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "content": GREETING}]

st.title("Empório da Música")
st.caption("Atendimento virtual - instrumentos musicais em Campo Grande/MS")
st.button("Nova conversa", on_click=new_conversation)

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

prompt = st.chat_input("Escreva sua mensagem")

if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    try:
        response = httpx.post(
            f"{API_URL}/api/chat",
            json={
                "session_id": st.session_state.session_id,
                "message": prompt,
            },
            timeout=60,
        )
        response.raise_for_status()
        reply = response.json()["reply"]
    except httpx.HTTPError:
        reply = (
            "Não consegui falar com o servidor de atendimento. "
            "Confira se a API está rodando e tente de novo."
        )
    st.session_state.messages.append({"role": "assistant", "content": reply})
    with st.chat_message("assistant"):
        st.markdown(reply)
