"""Durable, project-scoped orchestration for AgentGuard loop creation."""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.core.config import Settings
from app.core.db import open_session
from app.integrations.agentguard_client import AgentGuardClient, AgentGuardError
from app.models.app import (
    InvestigationLoopSubmission,
    ProjectInvestigation,
    ProjectInvestigationLoop,
)


class LoopCreationError(RuntimeError):
    def __init__(self, status_code: int, code: str, message: str) -> None:
        self.status_code = status_code
        self.code = code
        super().__init__(message)


@dataclass(frozen=True)
class LoopCreationResult:
    status_code: int
    payload: dict[str, Any]


def submit_loop(
    settings: Settings,
    client: AgentGuardClient,
    *,
    project_id: int,
    request_id: str,
    submission_id: str,
    actor: str,
    upstream_payload: dict[str, Any],
) -> LoopCreationResult:
    """Submit once, then reconcile only from durable state and read-only data.

    The BFF correlation id remains stable across browser retries. The upstream
    idempotency key is generated once and committed before any POST is sent.
    A process restart with a recorded SUBMITTING state never generates a new
    key or blindly submits again.
    """
    row, is_new = _create_or_load_submission(
        settings,
        project_id=project_id,
        request_id=request_id,
        submission_id=submission_id,
        actor=actor,
        upstream_payload=upstream_payload,
    )
    if row.status == "COMPLETED":
        return LoopCreationResult(200, _public_payload(row))
    if row.status == "FAILED":
        return LoopCreationResult(row.error_status_code or 409, _public_payload(row))
    if row.status == "LINK_PENDING":
        return _complete_pending_link(settings, row.id)
    if row.status in {"SUBMITTING", "SUBMISSION_AMBIGUOUS"}:
        return _reconcile_ambiguous(settings, client, row.id)
    if row.status != "PREPARED":
        raise LoopCreationError(503, "SUBMISSION_STATE_INVALID", "Loop 提交状态无法识别")

    try:
        baseline_ids = _read_all_loop_ids(client, request_id)
    except LoopCreationError:
        raise
    except AgentGuardError as exc:
        raise LoopCreationError(
            exc.status_code or 502,
            exc.code or "LOOP_RECONCILIATION_UNAVAILABLE",
            str(exc),
        ) from exc

    _persist_baseline(settings, row.id, baseline_ids)
    claimed = _claim_post(settings, row.id)
    if not claimed:
        latest = _load_submission(settings, row.id)
        if latest.status == "LINK_PENDING":
            return _complete_pending_link(settings, row.id)
        if latest.status in {"SUBMITTING", "SUBMISSION_AMBIGUOUS"}:
            return _reconcile_ambiguous(settings, client, row.id)
        if latest.status == "COMPLETED":
            return LoopCreationResult(200, _public_payload(latest))
        return LoopCreationResult(202, _public_payload(latest))

    try:
        upstream_result = client.create_investigation_loop(
            upstream_payload,
            idempotency_key=row.idempotency_key,
        )
    except AgentGuardError as exc:
        ambiguous = exc.status_code >= 500 or exc.status_code <= 0
        status = "SUBMISSION_AMBIGUOUS" if ambiguous else "FAILED"
        _set_failure(
            settings,
            row.id,
            status=status,
            error_code=exc.code or ("UPSTREAM_RESULT_UNKNOWN" if ambiguous else "UPSTREAM_REJECTED"),
            error_message=str(exc),
            error_status_code=503 if ambiguous else (exc.status_code or 502),
        )
        latest = _load_submission(settings, row.id)
        return LoopCreationResult(503 if ambiguous else (exc.status_code or 502), _public_payload(latest))
    except Exception as exc:  # transport adapters may surface a non-AgentGuard exception
        _set_failure(
            settings,
            row.id,
            status="SUBMISSION_AMBIGUOUS",
            error_code="UPSTREAM_RESULT_UNKNOWN",
            error_message=f"AgentGuard 请求结果不明（{type(exc).__name__}）",
            error_status_code=503,
        )
        return LoopCreationResult(503, _public_payload(_load_submission(settings, row.id)))

    loop_id = upstream_result.get("loop_id") if isinstance(upstream_result, dict) else None
    base_request_id = upstream_result.get("base_request_id") if isinstance(upstream_result, dict) else None
    if (
        not isinstance(loop_id, str)
        or not loop_id
        or loop_id.strip() != loop_id
        or len(loop_id) > 256
        or base_request_id != request_id
    ):
        _set_failure(
            settings,
            row.id,
            status="SUBMISSION_AMBIGUOUS",
            error_code="INVALID_UPSTREAM_IDENTITY",
            error_message="AgentGuard 创建响应缺少有效 loop_id 或基础调查不匹配；需要对账",
            error_status_code=503,
        )
        return LoopCreationResult(503, _public_payload(_load_submission(settings, row.id)))

    _store_upstream_result(settings, row.id, loop_id, upstream_result)
    return _complete_pending_link(settings, row.id)


def get_submission(
    settings: Settings,
    *,
    project_id: int,
    request_id: str,
    submission_id: str,
) -> dict[str, Any] | None:
    session = _open_session(settings)
    try:
        row = session.scalar(
            select(InvestigationLoopSubmission).where(
                InvestigationLoopSubmission.project_id == project_id,
                InvestigationLoopSubmission.base_request_id == request_id,
                InvestigationLoopSubmission.submission_id == submission_id,
            )
        )
        return _public_payload(row) if row is not None else None
    except SQLAlchemyError as exc:
        raise LoopCreationError(503, "SUBMISSION_STORAGE_UNAVAILABLE", "Loop 提交状态暂不可用") from exc
    finally:
        session.close()


def resume_submission(
    settings: Settings,
    client: AgentGuardClient,
    *,
    project_id: int,
    request_id: str,
    submission_id: str,
) -> LoopCreationResult:
    """Resume a persisted submission without accepting a replacement body.

    PREPARED means the POST was never claimed, so resuming it is safe. Every
    state after SUBMITTING reconciles through read-only calls only.
    """
    session = _open_session(settings)
    try:
        row = session.scalar(
            select(InvestigationLoopSubmission).where(
                InvestigationLoopSubmission.project_id == project_id,
                InvestigationLoopSubmission.base_request_id == request_id,
                InvestigationLoopSubmission.submission_id == submission_id,
            )
        )
        if row is None:
            raise LoopCreationError(404, "SUBMISSION_NOT_FOUND", "未找到该 Loop 提交记录")
        upstream_payload = json.loads(row.request_payload)
    except SQLAlchemyError as exc:
        raise LoopCreationError(503, "SUBMISSION_STORAGE_UNAVAILABLE", "Loop 提交状态暂不可用") from exc
    except json.JSONDecodeError as exc:
        raise LoopCreationError(503, "SUBMISSION_STATE_INVALID", "保存的 Loop 请求无法恢复") from exc
    finally:
        session.close()
    return submit_loop(
        settings,
        client,
        project_id=project_id,
        request_id=request_id,
        submission_id=submission_id,
        actor=row.created_by,
        upstream_payload=upstream_payload,
    )


def _create_or_load_submission(
    settings: Settings,
    *,
    project_id: int,
    request_id: str,
    submission_id: str,
    actor: str,
    upstream_payload: dict[str, Any],
) -> tuple[InvestigationLoopSubmission, bool]:
    session = _open_session(settings)
    canonical_payload = json.dumps(upstream_payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    fingerprint = hashlib.sha256(canonical_payload.encode("utf-8")).hexdigest()
    try:
        row = session.scalar(
            select(InvestigationLoopSubmission).where(
                InvestigationLoopSubmission.project_id == project_id,
                InvestigationLoopSubmission.submission_id == submission_id,
            )
        )
        if row is not None:
            if row.base_request_id != request_id or row.request_fingerprint != fingerprint:
                raise LoopCreationError(
                    409,
                    "SUBMISSION_IDEMPOTENCY_CONFLICT",
                    "该提交编号已用于不同的调查或参数",
                )
            return row, False

        row = InvestigationLoopSubmission(
            project_id=project_id,
            base_request_id=request_id,
            submission_id=submission_id,
            idempotency_key=uuid.uuid4().hex,
            request_fingerprint=fingerprint,
            request_payload=canonical_payload,
            status="PREPARED",
            created_by=actor,
        )
        session.add(row)
        session.commit()
        return row, True
    except IntegrityError:
        session.rollback()
        row = session.scalar(
            select(InvestigationLoopSubmission).where(
                InvestigationLoopSubmission.project_id == project_id,
                InvestigationLoopSubmission.submission_id == submission_id,
            )
        )
        if row is None or row.base_request_id != request_id or row.request_fingerprint != fingerprint:
            raise LoopCreationError(
                409, "SUBMISSION_IDEMPOTENCY_CONFLICT", "Loop 提交发生并发冲突"
            ) from None
        return row, False
    except LoopCreationError:
        raise
    except SQLAlchemyError as exc:
        raise LoopCreationError(503, "SUBMISSION_STORAGE_UNAVAILABLE", "Loop 提交状态无法持久化") from exc
    finally:
        session.close()


def _read_all_loop_ids(client: AgentGuardClient, request_id: str) -> list[str]:
    all_items: list[dict[str, Any]] = []
    offset = 0
    expected_count: int | None = None
    page_size = 100
    for _ in range(20):
        payload = client.list_investigation_loops(request_id, limit=page_size, offset=offset)
        items = payload.get("items") if isinstance(payload, dict) else None
        count = payload.get("count") if isinstance(payload, dict) else None
        if not isinstance(items, list) or isinstance(count, bool) or not isinstance(count, int) or count < 0:
            raise LoopCreationError(502, "INVALID_UPSTREAM_CONTRACT", "AgentGuard Loop 列表无法用于安全对账")
        if expected_count is None:
            expected_count = count
        elif expected_count != count:
            raise LoopCreationError(503, "LOOP_LIST_CHANGED_DURING_READ", "Loop 列表分页期间发生变化，提交未发送")
        for item in items:
            if (
                not isinstance(item, dict)
                or not isinstance(item.get("loop_id"), str)
                or not item["loop_id"]
                or item.get("base_request_id") != request_id
            ):
                raise LoopCreationError(502, "INVALID_UPSTREAM_CONTRACT", "AgentGuard Loop 列表身份字段不完整")
            all_items.append(item)
        offset += len(items)
        if offset >= expected_count:
            break
        if not items:
            raise LoopCreationError(502, "INVALID_UPSTREAM_CONTRACT", "AgentGuard Loop 列表分页不完整")
    else:
        raise LoopCreationError(503, "LOOP_RECONCILIATION_LIMIT", "Loop 数量超过安全对账上限，提交未发送")
    ids = [item["loop_id"] for item in all_items]
    if len(ids) != len(set(ids)):
        raise LoopCreationError(502, "INVALID_UPSTREAM_CONTRACT", "AgentGuard Loop 列表包含重复 ID")
    if expected_count != len(ids):
        raise LoopCreationError(503, "LOOP_LIST_INCOMPLETE", "AgentGuard Loop 列表不完整，提交未发送")
    return ids


def _persist_baseline(settings: Settings, row_id: int, baseline_ids: list[str]) -> None:
    session = _open_session(settings)
    try:
        with session.begin():
            row = session.get(InvestigationLoopSubmission, row_id)
            if row is None:
                raise LoopCreationError(503, "SUBMISSION_STORAGE_UNAVAILABLE", "Loop 提交状态已丢失")
            if row.status == "PREPARED" and row.baseline_loop_ids is None:
                row.baseline_loop_ids = json.dumps(sorted(baseline_ids), separators=(",", ":"))
                row.updated_at = datetime.now(UTC)
    except LoopCreationError:
        raise
    except SQLAlchemyError as exc:
        raise LoopCreationError(503, "SUBMISSION_STORAGE_UNAVAILABLE", "Loop 对账基线无法持久化") from exc
    finally:
        session.close()


def _claim_post(settings: Settings, row_id: int) -> bool:
    session = _open_session(settings)
    try:
        result = session.execute(
            update(InvestigationLoopSubmission)
            .where(
                InvestigationLoopSubmission.id == row_id,
                InvestigationLoopSubmission.status == "PREPARED",
                InvestigationLoopSubmission.baseline_loop_ids.is_not(None),
            )
            .values(status="SUBMITTING", updated_at=datetime.now(UTC))
        )
        session.commit()
        return bool(result.rowcount)
    except SQLAlchemyError as exc:
        session.rollback()
        raise LoopCreationError(503, "SUBMISSION_STORAGE_UNAVAILABLE", "Loop 提交状态无法锁定") from exc
    finally:
        session.close()


def _reconcile_ambiguous(
    settings: Settings,
    client: AgentGuardClient,
    row_id: int,
) -> LoopCreationResult:
    row = _load_submission(settings, row_id)
    if not row.baseline_loop_ids:
        _set_failure(
            settings, row_id, status="SUBMISSION_AMBIGUOUS",
            error_code="SUBMISSION_REQUIRES_MANUAL_RECONCILIATION",
            error_message="提交开始前未能保存完整对账基线；为避免重复执行，请由管理员核查 AgentGuard",
            error_status_code=503,
        )
        return LoopCreationResult(503, _public_payload(_load_submission(settings, row_id)))
    try:
        current_ids = _read_all_loop_ids(client, row.base_request_id)
    except Exception as exc:  # read-only reconciliation may be retried later
        _set_failure(
            settings, row_id, status="SUBMISSION_AMBIGUOUS",
            error_code="RECONCILIATION_UNAVAILABLE",
            error_message=(str(exc) if isinstance(exc, (AgentGuardError, LoopCreationError))
                           else "无法读取上游 Loop 列表"),
            error_status_code=503,
        )
        return LoopCreationResult(503, _public_payload(_load_submission(settings, row_id)))
    baseline_ids = set(json.loads(row.baseline_loop_ids))
    new_ids = set(current_ids) - baseline_ids
    if len(new_ids) != 1:
        _set_failure(
            settings, row_id, status="SUBMISSION_AMBIGUOUS",
            error_code="SUBMISSION_REQUIRES_MANUAL_RECONCILIATION",
            error_message="无法唯一匹配本次创建结果；没有自动重发，请由管理员核查 AgentGuard",
            error_status_code=503,
        )
        return LoopCreationResult(503, _public_payload(_load_submission(settings, row_id)))
    loop_id = next(iter(new_ids))
    try:
        loop_payload = client.get_investigation_loop(loop_id)
    except AgentGuardError as exc:
        _set_failure(
            settings, row_id, status="SUBMISSION_AMBIGUOUS",
            error_code="RECONCILIATION_DETAIL_UNAVAILABLE",
            error_message=str(exc), error_status_code=503,
        )
        return LoopCreationResult(503, _public_payload(_load_submission(settings, row_id)))
    if loop_payload.get("loop_id") != loop_id or loop_payload.get("base_request_id") != row.base_request_id:
        _set_failure(
            settings, row_id, status="SUBMISSION_AMBIGUOUS",
            error_code="RECONCILIATION_IDENTITY_MISMATCH",
            error_message="上游 Loop 详情身份不匹配；需要管理员核查",
            error_status_code=503,
        )
        return LoopCreationResult(503, _public_payload(_load_submission(settings, row_id)))
    _store_upstream_result(settings, row_id, loop_id, loop_payload)
    return _complete_pending_link(settings, row_id)


def _store_upstream_result(settings: Settings, row_id: int, loop_id: str, payload: dict[str, Any]) -> None:
    session = _open_session(settings)
    try:
        with session.begin():
            row = session.get(InvestigationLoopSubmission, row_id)
            if row is None:
                raise LoopCreationError(503, "SUBMISSION_STORAGE_UNAVAILABLE", "Loop 提交状态已丢失")
            if row.status == "COMPLETED":
                return
            if row.status == "LINK_PENDING" and row.loop_id != loop_id:
                raise LoopCreationError(409, "LOOP_OWNERSHIP_CONFLICT", "该提交已关联到不同的上游 Loop")
            row.loop_id = loop_id
            row.response_payload = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
            row.status = "LINK_PENDING"
            row.error_code = None
            row.error_message = None
            row.error_status_code = None
            row.updated_at = datetime.now(UTC)
    except LoopCreationError:
        raise
    except SQLAlchemyError as exc:
        raise LoopCreationError(
            503,
            "SUBMISSION_AMBIGUOUS",
            "AgentGuard 已返回 Loop，但本地状态写入失败；请刷新对账",
        ) from exc
    finally:
        session.close()


def _complete_pending_link(settings: Settings, row_id: int) -> LoopCreationResult:
    session = _open_session(settings)
    try:
        with session.begin():
            row = session.get(InvestigationLoopSubmission, row_id)
            if row is None:
                raise LoopCreationError(503, "SUBMISSION_STORAGE_UNAVAILABLE", "Loop 提交状态已丢失")
            if row.status == "COMPLETED":
                return LoopCreationResult(200, _public_payload(row))
            if row.status != "LINK_PENDING" or not row.loop_id or not row.response_payload:
                raise LoopCreationError(503, "SUBMISSION_STATE_INVALID", "Loop 本地归属等待状态无效")
            base_rows = session.scalars(
                select(ProjectInvestigation).where(
                    ProjectInvestigation.agentguard_request_id == row.base_request_id
                )
            ).all()
            if (
                len(base_rows) != 1
                or base_rows[0].project_id != row.project_id
                or base_rows[0].verification != "verified"
                or base_rows[0].verification_source != "live"
            ):
                row.error_code = "INVESTIGATION_OWNERSHIP_CONFLICT"
                row.error_message = "基础调查项目归属已变化；Loop 已创建但需要管理员对账"
                row.error_status_code = 409
                row.updated_at = datetime.now(UTC)
                return LoopCreationResult(409, _public_payload(row))
            existing = session.scalar(
                select(ProjectInvestigationLoop).where(ProjectInvestigationLoop.loop_id == row.loop_id)
            )
            if existing is None:
                session.add(ProjectInvestigationLoop(
                    project_id=row.project_id,
                    base_request_id=row.base_request_id,
                    loop_id=row.loop_id,
                    created_by=row.created_by,
                    verified_source="agentguard",
                ))
            elif existing.project_id != row.project_id or existing.base_request_id != row.base_request_id:
                row.error_code = "LOOP_OWNERSHIP_CONFLICT"
                row.error_message = "该 Loop 已关联其他项目或基础调查；需要管理员对账"
                row.error_status_code = 409
                row.updated_at = datetime.now(UTC)
                return LoopCreationResult(409, _public_payload(row))
            row.status = "COMPLETED"
            row.error_code = None
            row.error_message = None
            row.error_status_code = None
            row.updated_at = datetime.now(UTC)
            return LoopCreationResult(201, _public_payload(row))
    except LoopCreationError:
        raise
    except IntegrityError as exc:
        session.rollback()
        row = session.get(InvestigationLoopSubmission, row_id)
        if row is not None and row.status == "COMPLETED":
            return LoopCreationResult(200, _public_payload(row))
        raise LoopCreationError(
            409, "LOOP_OWNERSHIP_CONFLICT", "Loop 归属写入发生并发冲突；需要管理员对账"
        ) from exc
    except SQLAlchemyError as exc:
        raise LoopCreationError(503, "LINK_PENDING", "Loop 已在 AgentGuard 创建，本地归属尚待恢复") from exc
    finally:
        session.close()


def _set_failure(
    settings: Settings,
    row_id: int,
    *,
    status: str,
    error_code: str,
    error_message: str,
    error_status_code: int,
) -> None:
    session = _open_session(settings)
    try:
        with session.begin():
            row = session.get(InvestigationLoopSubmission, row_id)
            if row is not None:
                row.status = status
                row.error_code = error_code[:64]
                row.error_message = error_message[:4000]
                row.error_status_code = error_status_code
                row.updated_at = datetime.now(UTC)
    except SQLAlchemyError as exc:
        raise LoopCreationError(503, "SUBMISSION_STORAGE_UNAVAILABLE", "Loop 提交状态无法保存") from exc
    finally:
        session.close()


def _load_submission(settings: Settings, row_id: int) -> InvestigationLoopSubmission:
    session = _open_session(settings)
    try:
        row = session.get(InvestigationLoopSubmission, row_id)
        if row is None:
            raise LoopCreationError(503, "SUBMISSION_STORAGE_UNAVAILABLE", "Loop 提交状态已丢失")
        return row
    except SQLAlchemyError as exc:
        raise LoopCreationError(503, "SUBMISSION_STORAGE_UNAVAILABLE", "Loop 提交状态暂不可用") from exc
    finally:
        session.close()


def _open_session(settings: Settings):
    session = open_session(settings)
    if session is None:
        raise LoopCreationError(503, "SUBMISSION_STORAGE_UNAVAILABLE", "Loop 创建需要可用的项目数据库")
    return session


def _public_payload(row: InvestigationLoopSubmission) -> dict[str, Any]:
    status = "SUBMISSION_AMBIGUOUS" if row.status == "SUBMITTING" else row.status
    response = None
    if row.response_payload:
        try:
            response = json.loads(row.response_payload)
        except json.JSONDecodeError:
            response = None
    return {
        "meta": {"data_mode": "live", "source": "agentguard"},
        "submission": {
            "submission_id": row.submission_id,
            "status": status,
            "loop_id": row.loop_id,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "error": ({"code": row.error_code, "message": row.error_message}
                      if row.error_code else None),
        },
        "loop": response,
    }
