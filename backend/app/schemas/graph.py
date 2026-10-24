"""Interaction graph schemas (B4). Nodes and edges always carry source IDs so
every element can be traced back to a real recorded source."""

from __future__ import annotations

from pydantic import BaseModel, Field

NodeType = str  # agent | tool | model | invocation | external_resource
EdgeType = str  # message | invocation | result


class GraphNode(BaseModel):
    id: str = Field(min_length=1)
    type: NodeType
    label: str
    risk: str = "low"
    timestamp: str | None = None
    source_id: str = Field(min_length=1)
    metadata: dict = Field(default_factory=dict)


class GraphEdge(BaseModel):
    id: str = Field(min_length=1)
    source: str = Field(min_length=1)
    target: str = Field(min_length=1)
    type: EdgeType
    message_id: str | None = None
    risk: str = "low"
    timestamp: str | None = None
    source_id: str = Field(min_length=1)
    metadata: dict = Field(default_factory=dict)


class CandidatePath(BaseModel):
    id: str = Field(min_length=1)
    label: str
    node_ids: list[str]
    edge_ids: list[str]
    evidence_refs: list[str] = Field(default_factory=list)
    risk: str = "low"
