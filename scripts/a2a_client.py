"""Delegate a task to the AAIF agent over A2A, the way another agent would.

    docker compose exec agent python /scripts/a2a_client.py "Onboard /workspace/sample-app"

Resolves the Agent Card, sends one message, and prints streamed status updates
and the final artifact.
"""
import asyncio
import sys
import uuid

import httpx
from a2a.client import A2ACardResolver, ClientConfig, create_client
from a2a.helpers import get_artifact_text, get_message_text
from a2a.types import Message, Part, Role, SendMessageRequest, TaskState

AGENT_URL = "http://localhost:8080"


async def main(prompt: str) -> None:
    async with httpx.AsyncClient(timeout=30) as http:
        card = await A2ACardResolver(http, AGENT_URL).get_agent_card()
    print(f"Agent: {card.name} — skills: {', '.join(s.id for s in card.skills)}")

    client = await create_client(card, client_config=ClientConfig(
        supported_protocol_bindings=["JSONRPC"],
        httpx_client=httpx.AsyncClient(timeout=900),
    ))
    message = Message(
        role=Role.ROLE_USER,
        message_id=str(uuid.uuid4()),
        context_id=str(uuid.uuid4()),
        parts=[Part(text=prompt)],
    )
    async for event in client.send_message(SendMessageRequest(message=message)):
        if event.HasField("status_update"):
            status = event.status_update.status
            text = get_message_text(status.message) if status.HasField("message") else ""
            print(f"[{TaskState.Name(status.state)}] {text}")
        elif event.HasField("artifact_update"):
            print("\n--- artifact:", event.artifact_update.artifact.name, "---")
            print(get_artifact_text(event.artifact_update.artifact))
        elif event.HasField("task"):
            print(f"[task {event.task.id}] {TaskState.Name(event.task.status.state)}")
        elif event.HasField("message"):
            print(get_message_text(event.message))
    await client.close()


if __name__ == "__main__":
    asyncio.run(main(" ".join(sys.argv[1:]) or "What skills do you have?"))
