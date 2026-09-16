"""Bounded text-to-draft graph; persistence and authorization stay outside the LLM."""

from typing import Protocol, TypedDict
from uuid import UUID

from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, ConfigDict, Field


PROMPT_VERSION = "text-draft-v1"


class DraftStep(BaseModel):
    model_config = ConfigDict(extra="forbid")
    instruction: str = Field(min_length=1, max_length=4000)
    expected_result: str = Field(min_length=1, max_length=2000)
    source_event_ids: list[UUID] = Field(min_length=1, max_length=30)


class GeneratedDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=200)
    summary: str = Field(min_length=1, max_length=4000)
    steps: list[DraftStep] = Field(min_length=1, max_length=50)


class DraftProvider(Protocol):
    model_name: str

    def generate(self, source: dict) -> GeneratedDraft: ...


class DraftState(TypedDict, total=False):
    source: dict
    draft: GeneratedDraft


def build_draft_graph(provider: DraftProvider):
    def generate(state: DraftState):
        return {"draft": provider.generate(state["source"])}

    def validate(state: DraftState):
        draft = GeneratedDraft.model_validate(state["draft"])
        allowed = {UUID(event["id"]) for event in state["source"]["events"]}
        for step in draft.steps:
            if not set(step.source_event_ids).issubset(allowed):
                raise ValueError("Unknown source event")
        return {"draft": draft}

    graph = StateGraph(DraftState)
    graph.add_node("generate", generate)
    graph.add_node("validate_sources", validate)
    graph.add_edge(START, "generate")
    graph.add_edge("generate", "validate_sources")
    graph.add_edge("validate_sources", END)
    return graph.compile()
