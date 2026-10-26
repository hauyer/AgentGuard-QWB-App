"""Strict pagination for the pinned AgentGuard Loop registry contract."""

from __future__ import annotations

from typing import Any

from app.integrations.agentguard_client import AgentGuardClient


class LoopListContractError(RuntimeError):
    def __init__(self, status_code: int, code: str, message: str) -> None:
        self.status_code = status_code
        self.code = code
        super().__init__(message)


def read_all_investigation_loops(
    client: AgentGuardClient,
    request_id: str,
    *,
    page_size: int = 100,
    max_pages: int = 21,
) -> list[dict[str, Any]]:
    """Read every page and validate identity before any caller persists data.

    AgentGuard I7 reports ``count`` for the current page, not the full result
    set. A full page carries ``next_offset`` even when it is the final full
    page, so one final empty page may be required to prove the listing ended.
    """
    items_all: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    offset = 0

    for _ in range(max_pages):
        payload = client.list_investigation_loops(request_id, limit=page_size, offset=offset)
        items = payload.get("items") if isinstance(payload, dict) else None
        count = payload.get("count") if isinstance(payload, dict) else None
        response_offset = payload.get("offset") if isinstance(payload, dict) else None
        response_limit = payload.get("limit") if isinstance(payload, dict) else None
        next_offset = payload.get("next_offset") if isinstance(payload, dict) else None
        if (
            not isinstance(items, list)
            or isinstance(count, bool)
            or not isinstance(count, int)
            or count < 0
            or count != len(items)
            or len(items) > page_size
            or response_offset != offset
            or response_limit != page_size
        ):
            raise LoopListContractError(
                502, "INVALID_UPSTREAM_CONTRACT", "AgentGuard Loop 列表分页字段无效"
            )

        if count == page_size:
            if isinstance(next_offset, bool) or next_offset != offset + count:
                raise LoopListContractError(
                    502, "INVALID_UPSTREAM_CONTRACT", "AgentGuard Loop 列表分页游标无效"
                )
        elif next_offset is not None:
            raise LoopListContractError(
                502, "INVALID_UPSTREAM_CONTRACT", "AgentGuard Loop 列表未满页却返回下一页游标"
            )

        for item in items:
            if not isinstance(item, dict):
                raise LoopListContractError(
                    502, "INVALID_UPSTREAM_CONTRACT", "AgentGuard Loop 列表包含无效记录"
                )
            loop_id = item.get("loop_id")
            if (
                not isinstance(loop_id, str)
                or not loop_id
                or loop_id.strip() != loop_id
                or len(loop_id) > 256
                or item.get("base_request_id") != request_id
            ):
                raise LoopListContractError(
                    502,
                    "INVALID_UPSTREAM_CONTRACT",
                    "AgentGuard Loop 身份字段缺失或基础调查不匹配",
                )
            if loop_id in seen_ids:
                raise LoopListContractError(
                    502, "INVALID_UPSTREAM_CONTRACT", "AgentGuard Loop 列表包含重复 loop_id"
                )
            seen_ids.add(loop_id)
            items_all.append(item)

        if next_offset is None:
            return items_all
        offset = next_offset

    raise LoopListContractError(
        503, "LOOP_RECONCILIATION_LIMIT", "Loop 数量超过安全分页上限；未登记不完整列表"
    )
