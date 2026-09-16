"""Deterministic contracts for the simplified Step 8 graph."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from langgraph.checkpoint.memory import InMemorySaver

from app.services.chat import AnswerDraft, ChatService, QueryRewrite


DOCUMENT = {
    "chunk_id": "c1",
    "document_id": "d1",
    "title": "Scholarship",
    "text": "Eligible doctoral students receive funding for three years.",
    "page_numbers": [2, 3],
    "source_url": "https://example.org/source.pdf",
}
WEB_SOURCE = {
    "source_id": "web:0",
    "document_id": None,
    "title": "YZU scholarship information",
    "text": "The official YZU page describes current scholarship requirements.",
    "page_numbers": [],
    "source_url": "https://gao.yzu.edu.tw/index.php/en/scholarships",
    "source_type": "web",
}
CONTACT_SOURCE = {
    "source_id": "office:global_affairs",
    "document_id": None,
    "title": "YZU Office of Global Affairs",
    "text": "Email iadept@saturn.yzu.edu.tw or call +886-3-463-8800 ext. 3281-3289.",
    "page_numbers": [],
    "source_url": "https://gao.yzu.edu.tw/index.php/en/",
    "source_type": "office_contact",
}


def make_service(*, passages=None, history=None, saver=None, tools=None):
    sessions = SimpleNamespace(
        history=AsyncMock(return_value=history or []),
        save=AsyncMock(),
        reset=AsyncMock(),
    )
    evidence = [SimpleNamespace(chunk_id="c1", model_dump=lambda: DOCUMENT)]
    retrieval = SimpleNamespace(search=AsyncMock(return_value=SimpleNamespace(
        evidence=evidence if passages is None else passages,
        neighbors=[],
    )))
    if tools is None:
        tools = SimpleNamespace(
            get_web_search=AsyncMock(return_value=[]),
            get_office_contact=AsyncMock(return_value=[]),
        )
    service = ChatService(
        None, retrieval, sessions, saver or InMemorySaver(), fallback_tools=tools)

    async def structured(schema, instruction, data):
        if schema is QueryRewrite:
            return schema(query="Doctoral scholarship duration")
        source_ids = [source["source_id"] for source in data["sources"]]
        return AnswerDraft(
            answer="The supplied sources describe the scholarship requirements.",
            source_ids=source_ids,
        )

    service.structured = AsyncMock(side_effect=structured)
    return service


def test_graph_contains_only_the_three_approved_application_nodes():
    service = make_service()
    node_names = set(service.graph.get_graph().nodes) - {"__start__", "__end__"}
    assert node_names == {"rewrite_query", "retrieve", "answer"}


def test_structured_output_disables_streaming_with_supported_call_argument():
    async def scenario():
        bound = SimpleNamespace(ainvoke=AsyncMock(return_value=SimpleNamespace(
            content=(
                '{"answer":"Grounded answer","source_ids":["c1"],'
                '"action_required":false}'
            ))))
        model = SimpleNamespace(bind=Mock(return_value=bound))
        service = make_service()
        service.model = model
        service.structured = ChatService.structured.__get__(service)

        result = await service.structured(
            AnswerDraft, "Use the source.", {"sources": []})

        assert result.answer == "Grounded answer"
        assert "streaming" not in model.bind.call_args.kwargs
        assert bound.ainvoke.await_args.kwargs["stream"] is False

    asyncio.run(scenario())


def test_document_answer_bypasses_fallback_and_keeps_page_provenance():
    async def scenario():
        service = make_service()
        result = await service.ask(str(uuid4()), "What is the funding duration?")

        assert result["status"] == "answered"
        assert result["references"][0]["page_numbers"] == [2, 3]
        assert result["references"][0]["source_url"] == DOCUMENT["source_url"]
        assert result["tools_used"] == []
        service.fallback_tools.get_web_search.assert_not_awaited()
        service.fallback_tools.get_office_contact.assert_not_awaited()
        service.sessions.save.assert_awaited_once()

    asyncio.run(scenario())


def test_empty_retrieval_uses_web_and_relevant_office_contact_tools():
    async def scenario():
        tools = SimpleNamespace(
            get_web_search=AsyncMock(return_value=[WEB_SOURCE]),
            get_office_contact=AsyncMock(return_value=[CONTACT_SOURCE]),
        )
        service = make_service(passages=[], tools=tools)
        question = "Who can help with an international scholarship?"

        result = await service.ask(str(uuid4()), question)

        assert result["status"] == "answered"
        assert result["tools_used"] == ["get_web_search", "get_office_contact"]
        assert {item["source_type"] for item in result["references"]} == {
            "web", "office_contact"}
        tools.get_web_search.assert_awaited_once_with(question)
        tools.get_office_contact.assert_awaited_once_with(question)

    asyncio.run(scenario())


def test_fallback_failures_return_an_evidence_limitation_and_save_the_turn():
    async def scenario():
        tools = SimpleNamespace(
            get_web_search=AsyncMock(side_effect=RuntimeError("provider secret")),
            get_office_contact=AsyncMock(side_effect=RuntimeError("contact failure")),
        )
        service = make_service(passages=[], tools=tools)

        result = await service.ask(str(uuid4()), "What is the absent policy?")

        assert result["status"] == "insufficient_evidence"
        assert result["references"] == []
        assert result["tools_used"] == []
        assert "could not find enough information" in result["answer"].lower()
        service.sessions.save.assert_awaited_once()

    asyncio.run(scenario())


def test_history_rewrites_a_contextual_follow_up():
    async def scenario():
        service = make_service(history=[{
            "question": "What doctoral funding is available?",
            "answer": "A scholarship is available under stated conditions.",
        }])

        await service.ask(str(uuid4()), "How long does it last?")

        assert service.structured.await_args_list[0].args[0] is QueryRewrite
        assert service.retrieval.search.await_args.args[0].query == (
            "Doctoral scholarship duration")

    asyncio.run(scenario())


def test_new_checkpoint_namespace_ignores_superseded_graph_state():
    async def scenario():
        saver = InMemorySaver()
        service = make_service(saver=saver)
        session_id = str(uuid4())

        await service.ask(session_id, "Duration?")

        current = await service.graph.aget_state(service.graph_config(session_id))
        superseded = await service.graph.aget_state({
            "configurable": {"thread_id": session_id, "checkpoint_ns": ""}})
        assert current.values["question"] == "Duration?"
        assert not superseded.values

    asyncio.run(scenario())


def test_unknown_or_duplicate_source_ids_are_rejected():
    with pytest.raises(ValueError, match="invalid source"):
        ChatService.validate_ids(["invented"], [WEB_SOURCE])
    with pytest.raises(ValueError, match="invalid source"):
        ChatService.validate_ids(["web:0", "web:0"], [WEB_SOURCE])


def test_actions_remain_deferred():
    async def scenario():
        service = make_service()

        async def structured(schema, instruction, data):
            if schema is QueryRewrite:
                return schema(query="Submit doctoral scholarship application")
            return AnswerDraft(
                answer="Here are the application requirements.",
                source_ids=["c1"],
                action_required=True,
            )

        service.structured.side_effect = structured
        result = await service.ask(str(uuid4()), "Submit my application")

        assert result["action_status"] == "deferred"
        assert "action execution is not available" in result["answer"]

    asyncio.run(scenario())


def test_sessions_have_separate_checkpoint_states():
    async def scenario():
        service = make_service()
        one, two = str(uuid4()), str(uuid4())

        await service.ask(one, "Duration?")

        snapshot = await service.graph.aget_state(service.graph_config(two))
        assert not snapshot.values

    asyncio.run(scenario())


def test_pending_stage_reports_the_next_node_without_state_contents():
    async def scenario():
        service = make_service()
        assert await service.pending_stage(str(uuid4())) == "workflow"

    asyncio.run(scenario())
