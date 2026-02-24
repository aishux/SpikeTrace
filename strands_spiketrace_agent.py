"""
Minimal A2A client that calls your SpikeTrace Elastic agent using the official A2A client library.

Usage (example):
  python strands_spiketrace_agent.py \"Why did emissions spike in us-central1 yesterday?\"

This will:
  - GET the agent card from {SPIKETRACE_A2A_BASE}/{SPIKETRACE_AGENT_ID}.json
  - POST an A2A message to the same base for that agent
  - Stream and print the agent's response text
"""

import asyncio
import os
from uuid import uuid4

import httpx
from a2a.client import A2ACardResolver, ClientConfig, ClientFactory
from a2a.types import Message, Part, Role, Task, TextPart
from dotenv import load_dotenv

DEFAULT_TIMEOUT = 60  # seconds


def create_message(*, role: Role = Role.user, text: str, context_id=None) -> Message:
    return Message(
        kind="message",
        role=role.value,
        parts=[Part(TextPart(kind="text", text=text))],
        message_id=uuid4().hex,
        context_id=context_id,
    )


def _text_from_message(msg: Message) -> str:
    """Extract plain text from a Message's parts."""
    parts = []
    for part in msg.parts:
        if isinstance(part.root, TextPart):
            parts.append(part.root.text)
    return "".join(parts)


async def query_spiketrace_agent(question: str, context_id: str | None = None) -> tuple[str, str | None]:
    """
    Send a question to the SpikeTrace A2A agent and return (response_text, context_id).
    Pass context_id from a previous response to continue the same conversation so the
    agent can use tools (e.g. create_incident_ticket) when you say "yes".
    Uses env: SPIKETRACE_A2A_BASE, ELASTICSEARCH_API_KEY, SPIKETRACE_AGENT_ID.
    """
    load_dotenv()
    a2a_base = os.getenv("SPIKETRACE_A2A_BASE")
    api_key = os.getenv("ELASTICSEARCH_API_KEY")
    agent_id = os.getenv("SPIKETRACE_AGENT_ID", "spiketrace")

    if not a2a_base:
        return "Error: SPIKETRACE_A2A_BASE is not set. Set it to your Kibana A2A base URL.", None
    if not api_key:
        return "Error: ELASTICSEARCH_API_KEY is not set.", None

    custom_headers = {"Authorization": f"ApiKey {api_key}"}

    async with httpx.AsyncClient(
        timeout=DEFAULT_TIMEOUT, headers=custom_headers
    ) as httpx_client:
        resolver = A2ACardResolver(httpx_client=httpx_client, base_url=a2a_base.rstrip("/"))
        agent_card = await resolver.get_agent_card(
            relative_card_path=f"/{agent_id}.json"
        )
        config = ClientConfig(
            httpx_client=httpx_client,
            streaming=True,
        )
        factory = ClientFactory(config)
        client = factory.create(agent_card)
        msg = create_message(role=Role.user, text=question, context_id=context_id)
        full_response = []
        out_context_id: str | None = context_id
        last_task: Task | None = None
        async for event in client.send_message(msg):
            if isinstance(event, Message):
                out_context_id = getattr(event, "context_id", None) or out_context_id
                full_response.append(_text_from_message(event))
            elif isinstance(event, tuple) and len(event) >= 1:
                task = event[0]
                if isinstance(task, Task):
                    last_task = task
                    out_context_id = task.context_id
        if full_response:
            text = "".join(full_response)
        elif last_task and last_task.history:
            assistant_text = [
                _text_from_message(m)
                for m in last_task.history
                if getattr(m, "role", None) in ("agent", "assistant")
            ]
            text = "".join(assistant_text) if assistant_text else "No response from agent."
        else:
            text = "No response from agent."
        return text, out_context_id


async def main() -> None:
    load_dotenv()

    a2a_base = os.getenv("SPIKETRACE_A2A_BASE")
    api_key = os.getenv("ELASTICSEARCH_API_KEY")
    agent_id = os.getenv("SPIKETRACE_AGENT_ID", "spiketrace")

    if not a2a_base:
        raise SystemExit(
            "SPIKETRACE_A2A_BASE is not set.\n"
            "Example:\n"
            "  export SPIKETRACE_A2A_BASE="
            "\"https://<your-kibana>/api/agent_builder/a2a\""
        )
    if not api_key:
        raise SystemExit("ELASTICSEARCH_API_KEY is not set.")

    custom_headers = {"Authorization": f"ApiKey {api_key}"}

    # Question from CLI args, or a default
    import sys

    if len(sys.argv) > 1:
        question = " ".join(sys.argv[1:]).strip()
    else:
        question = "Why did emissions spike in us-central1 yesterday?"

    async with httpx.AsyncClient(
        timeout=DEFAULT_TIMEOUT, headers=custom_headers
    ) as httpx_client:
        # 1) Get agent card
        resolver = A2ACardResolver(httpx_client=httpx_client, base_url=a2a_base.rstrip("/"))
        agent_card = await resolver.get_agent_card(
            relative_card_path=f"/{agent_id}.json"
        )

        # 2) Create A2A client from agent card
        config = ClientConfig(
            httpx_client=httpx_client,
            streaming=True,
        )
        factory = ClientFactory(config)
        client = factory.create(agent_card)

        # 3) Send the question as a single A2A message and stream the reply
        print(f"\nSending question to SpikeTrace A2A agent '{agent_id}':\n{question}\n")
        msg = create_message(role=Role.user, text=question)

        full_response = []
        async for event in client.send_message(msg):
            if isinstance(event, Message):
                # Concatenate all text parts
                for part in event.parts:
                    if isinstance(part.root, TextPart):
                        text = part.root.text
                        full_response.append(text)
                        print(text)

if __name__ == "__main__":
    asyncio.run(main())

# To test:
# python strands_spiketrace_agent.py "Why did emissions spike in us-central1 in last 48 hours?"