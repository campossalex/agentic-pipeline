"""Agent2Agent (A2A) interface.

Publishes an Agent Card whose skills mirror the installed Agent Skills, and
runs incoming A2A tasks through the same agent loop. Progress (skill
activations, MCP calls) is streamed back as task status updates; the final
answer is returned as a `response` artifact. Conversations are keyed by the
A2A context_id.
"""
import logging

from a2a.server.agent_execution.agent_executor import AgentExecutor
from a2a.server.agent_execution.context import RequestContext
from a2a.server.events.event_queue import EventQueue
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.routes import (
    add_a2a_routes_to_fastapi,
    create_agent_card_routes,
    create_jsonrpc_routes,
    create_rest_routes,
)
from a2a.server.tasks.inmemory_task_store import InMemoryTaskStore
from a2a.server.tasks.task_updater import TaskUpdater
from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentInterface,
    AgentProvider,
    AgentSkill,
    Part,
    Task,
    TaskState,
    TaskStatus,
)

from . import config, llm, loop, skills

log = logging.getLogger(__name__)

# A2A context_id -> conversation items
_contexts: dict[str, list[dict]] = {}


class AgentLoopExecutor(AgentExecutor):
    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        task_id, context_id = context.task_id, context.context_id
        if not context.message or not task_id or not context_id:
            return
        if not context.current_task:
            await event_queue.enqueue_event(Task(
                id=task_id,
                context_id=context_id,
                status=TaskStatus(state=TaskState.TASK_STATE_SUBMITTED),
                history=[context.message],
            ))
        updater = TaskUpdater(event_queue=event_queue, task_id=task_id, context_id=context_id)
        await updater.start_work(updater.new_agent_message(parts=[Part(text="Working on it...")]))

        async def emit(event: dict) -> None:
            if event["kind"] == "trace" and event["layer"] in ("skill", "action", "context") \
                    and event["title"].startswith(("Activated", "MCP call", "AGENTS.md")):
                await updater.update_status(
                    TaskState.TASK_STATE_WORKING,
                    message=updater.new_agent_message(parts=[Part(text=event["title"])]),
                )

        items = _contexts.get(context_id, []) + [llm.user_message(context.get_user_input())]
        try:
            output, _ = await loop.run(items, config.DEFAULT_MODEL, emit)
        except Exception as exc:
            log.exception("A2A task failed")
            await updater.failed(updater.new_agent_message(parts=[Part(text=f"Agent error: {exc}")]))
            return
        _contexts[context_id] = items + output
        answer = next((llm.message_text(i) for i in reversed(output) if i["type"] == "message"), "")
        await updater.add_artifact(parts=[Part(text=answer or "(no answer)")], name="response", last_chunk=True)
        await updater.complete()

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        updater = TaskUpdater(event_queue=event_queue, task_id=context.task_id or "",
                              context_id=context.context_id or "")
        await updater.cancel()


def agent_card() -> AgentCard:
    installed = skills.discover()
    return AgentCard(
        name="AAIF Reference Agent",
        description=(
            "Developer and knowledge assistant built on AAIF projects: Agent Skills, AGENTS.md, "
            "MCP via agentgateway, OpenSandbox code execution and Open Responses."
        ),
        provider=AgentProvider(organization="AAIF reference stack", url=config.PUBLIC_URL),
        version="1.0.0",
        capabilities=AgentCapabilities(streaming=True, push_notifications=False),
        default_input_modes=["text"],
        default_output_modes=["text"],
        skills=[
            AgentSkill(id=s.name, name=s.name, description=s.description,
                       tags=["agent-skill"], input_modes=["text"], output_modes=["text"])
            for s in installed.values()
        ],
        supported_interfaces=[
            AgentInterface(protocol_binding="JSONRPC", protocol_version="1.0",
                           url=f"{config.PUBLIC_URL}/a2a/jsonrpc"),
            AgentInterface(protocol_binding="HTTP+JSON", protocol_version="1.0",
                           url=f"{config.PUBLIC_URL}/a2a/rest"),
        ],
    )


def mount(app) -> None:
    card = agent_card()
    handler = DefaultRequestHandler(
        agent_executor=AgentLoopExecutor(),
        task_store=InMemoryTaskStore(),
        agent_card=card,
    )
    add_a2a_routes_to_fastapi(
        app,
        agent_card_routes=create_agent_card_routes(agent_card=card),
        jsonrpc_routes=create_jsonrpc_routes(request_handler=handler, rpc_url="/a2a/jsonrpc",
                                             enable_v0_3_compat=True),
        rest_routes=create_rest_routes(request_handler=handler, path_prefix="/a2a/rest",
                                       enable_v0_3_compat=True),
    )
