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
from app.services.loop_contract import LoopListContractError, read_all_investigation_loops


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
            request_id=row.submission_id,
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
        row_id = row.id
        status = row.status
        actor = row.created_by
        upstream_payload = json.loads(row.request_payload)
    except SQLAlchemyError as exc:
        raise LoopCreationError(503, "SUBMISSION_STORAGE_UNAVAILABLE", "Loop 提交状态暂不可用") from exc
    except json.JSONDecodeError as exc:
        raise LoopCreationError(503, "SUBMISSION_STATE_INVALID", "保存的 Loop 请求无法恢复") from exc
    finally:
        session.close()
    if status in {"COMPLETED", "FAILED"}:
        return LoopCreationResult(200, _public_payload(_load_submission(settings, row_id)))
    if status == "LINK_PENDING":
        return _complete_pending_link(settings, row_id)
    if status in {"SUBMITTING", "SUBMISSION_AMBIGUOUS"}:
        return _retry_ambiguous_with_idempotency(settings, client, row_id)
    if status != "PREPARED":
        raise LoopCreationError(409, "SUBMISSION_STATE_INVALID", "该提交当前不能恢复")
    return submit_loop(
        settings,
        client,
        project_id=project_id,
        request_id=request_id,
        submission_id=submission_id,
        actor=actor,
        upstream_payload=upstream_payload,
    )


def manually_reconcile_submission(
    settings: Settings,
    client: AgentGuardClient,
    *,
    project_id: int,
    request_id: str,
    submission_id: str,
    actor: str,
    action: str,
    loop_id: str | None = None,
    operator_note: str | None = None,
) -> LoopCreationResult:
    """Resolve an ambiguous POST only with an explicit operator choice.

    A selected loop must be a new item in the complete upstream list and its
    detail must match both identities. Confirming no creation is allowed only
    when the complete list still equals the saved pre-POST baseline.
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
        row_id = row.id
        status = row.status
        baseline_json = row.baseline_loop_ids
    except SQLAlchemyError as exc:
        raise LoopCreationError(503, "SUBMISSION_STORAGE_UNAVAILABLE", "Loop 提交状态暂不可用") from exc
    finally:
        session.close()

    if status in {"COMPLETED", "FAILED"}:
        return LoopCreationResult(200, _public_payload(_load_submission(settings, row_id)))
    if status == "LINK_PENDING":
        return _complete_pending_link(settings, row_id)
    if action == "resume":
        if status != "PREPARED":
            return _retry_ambiguous_with_idempotency(settings, client, row_id)
        return resume_submission(
            settings,
            client,
            project_id=project_id,
            request_id=request_id,
            submission_id=submission_id,
        )
    if status not in {"SUBMITTING", "SUBMISSION_AMBIGUOUS", "LINK_PENDING"}:
        raise LoopCreationError(409, "SUBMISSION_STATE_INVALID", "该提交当前不需要人工对账")
    if not baseline_json:
        raise LoopCreationError(409, "SUBMISSION_BASELINE_MISSING", "缺少完整的提交前 Loop 基线，不能人工解除")

    baseline_ids = set(json.loads(baseline_json))
    try:
        current_ids = _read_all_loop_ids(client, request_id)
    except (AgentGuardError, LoopCreationError) as exc:
        raise LoopCreationError(
            503,
            "RECONCILIATION_UNAVAILABLE",
            "无法读取完整的 AgentGuard Loop 列表；提交仍保持锁定",
        ) from exc

    new_ids = set(current_ids) - baseline_ids
    if action == "confirm_not_created":
        if status != "SUBMISSION_AMBIGUOUS":
            raise LoopCreationError(
                409,
                "SUBMISSION_STILL_RUNNING",
                "提交仍在执行中，暂时不能确认上游未创建",
            )
        if new_ids:
            raise LoopCreationError(
                409,
                "NEW_LOOPS_REQUIRE_REVIEW",
                "上游出现了提交前不存在的 Loop；请核实后选择关联项，不能确认未创建",
            )
        _set_failure(
            settings,
            row_id,
            status="FAILED",
            error_code="OPERATOR_CONFIRMED_NOT_CREATED",
            error_message=f"Operator {actor} 核对后确认未创建；记录：{operator_note or ''}",
            error_status_code=409,
            expected_statuses={"SUBMISSION_AMBIGUOUS"},
        )
        return LoopCreationResult(200, _public_payload(_load_submission(settings, row_id)))

    if action != "associate_loop" or not loop_id:
        raise LoopCreationError(422, "INVALID_RECONCILIATION_ACTION", "需要选择关联 Loop 或确认上游未创建")
    if loop_id not in new_ids:
        raise LoopCreationError(
            409,
            "LOOP_NOT_A_NEW_CANDIDATE",
            "所选 Loop 不在本次提交前的完整基线之外，未建立归属",
        )
    try:
        detail = client.get_investigation_loop(loop_id)
    except AgentGuardError as exc:
        raise LoopCreationError(
            exc.status_code or 503,
            exc.code or "RECONCILIATION_DETAIL_UNAVAILABLE",
            "无法读取所选 Loop 详情；提交仍保持待核对",
        ) from exc
    if detail.get("loop_id") != loop_id or detail.get("base_request_id") != request_id:
        raise LoopCreationError(
            409,
            "RECONCILIATION_IDENTITY_MISMATCH",
            "所选 Loop 的上游身份不匹配，未建立归属",
        )
    _store_upstream_result(settings, row_id, loop_id, detail)
    return _complete_pending_link(settings, row_id)


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
        if row is not None and (row.base_request_id != request_id or row.request_fingerprint != fingerprint):
            raise LoopCreationError(
                409, "SUBMISSION_IDEMPOTENCY_CONFLICT", "Loop 提交发生并发冲突"
            ) from None
        if row is None:
            active = session.scalar(
                select(InvestigationLoopSubmission).where(
                    InvestigationLoopSubmission.project_id == project_id,
                    InvestigationLoopSubmission.base_request_id == request_id,
                    InvestigationLoopSubmission.status.in_(
                        {"PREPARED", "SUBMITTING", "SUBMISSION_AMBIGUOUS", "LINK_PENDING"}
                    ),
                )
            )
            if active is not None:
                raise LoopCreationError(
                    409,
                    "BASE_LOOP_SUBMISSION_IN_PROGRESS",
                    "该基础调查已有尚未完成或待对账的 Loop 提交",
                ) from None
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
    try:
        items = read_all_investigation_loops(client, request_id)
    except LoopListContractError as exc:
        raise LoopCreationError(exc.status_code, exc.code, str(exc)) from exc
    return [item["loop_id"] for item in items]


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
    # Repeated browser submissions do not trigger another POST. An Operator
    # must explicitly resume through the upstream's stable idempotency key or
    # resolve the record with audit evidence.
    _set_failure(
        settings,
        row_id,
        status="SUBMISSION_AMBIGUOUS",
        error_code="SUBMISSION_REQUIRES_MANUAL_RECONCILIATION",
        error_message=(
            "上游没有返回可验证的本次提交关联标识；为避免错误认领或重复执行，"
            "该基础调查的后续 Loop 创建已暂停，请由 Operator 核查并对账"
        ),
        error_status_code=503,
    )
    return LoopCreationResult(503, _public_payload(_load_submission(settings, row_id)))


def _retry_ambiguous_with_idempotency(
    settings: Settings,
    client: AgentGuardClient,
    row_id: int,
) -> LoopCreationResult:
    """Ask AgentGuard for the result using the exact persisted key and body.

    I7 guarantees that the same key and payload returns the registered Loop;
    this explicit Operator action therefore cannot create a second Loop. The
    client itself still never retries POST requests automatically.
    """
    row = _load_submission(settings, row_id)
    if row.status == "COMPLETED":
        return LoopCreationResult(200, _public_payload(row))
    if row.status == "LINK_PENDING":
        return _complete_pending_link(settings, row_id)
    if row.status not in {"SUBMITTING", "SUBMISSION_AMBIGUOUS"}:
        raise LoopCreationError(409, "SUBMISSION_STATE_INVALID", "该提交当前不需要幂等恢复")

    try:
        stored_payload = json.loads(row.request_payload)
        upstream_result = client.create_investigation_loop(
            stored_payload,
            idempotency_key=row.idempotency_key,
            request_id=row.submission_id,
        )
    except (AgentGuardError, json.JSONDecodeError) as exc:
        code = exc.code if isinstance(exc, AgentGuardError) else "SUBMISSION_STATE_INVALID"
        message = str(exc) if isinstance(exc, AgentGuardError) else "保存的 Loop 请求无法恢复"
        _set_failure(
            settings,
            row_id,
            status="SUBMISSION_AMBIGUOUS",
            error_code=code or "UPSTREAM_RESULT_UNKNOWN",
            error_message=message,
            error_status_code=503,
            expected_statuses={"SUBMITTING", "SUBMISSION_AMBIGUOUS"},
        )
        return LoopCreationResult(503, _public_payload(_load_submission(settings, row_id)))

    loop_id = upstream_result.get("loop_id") if isinstance(upstream_result, dict) else None
    base_request_id = upstream_result.get("base_request_id") if isinstance(upstream_result, dict) else None
    if (
        not isinstance(loop_id, str)
        or not loop_id
        or loop_id.strip() != loop_id
        or len(loop_id) > 256
        or base_request_id != row.base_request_id
    ):
        _set_failure(
            settings,
            row_id,
            status="SUBMISSION_AMBIGUOUS",
            error_code="INVALID_UPSTREAM_IDENTITY",
            error_message="AgentGuard 幂等恢复未返回匹配的 Loop 身份；提交仍待核对",
            error_status_code=503,
            expected_statuses={"SUBMITTING", "SUBMISSION_AMBIGUOUS"},
        )
        return LoopCreationResult(503, _public_payload(_load_submission(settings, row_id)))

    _store_upstream_result(settings, row_id, loop_id, upstream_result)
    linked = _complete_pending_link(settings, row_id)
    if linked.status_code == 201:
        return LoopCreationResult(200, linked.payload)
    return linked


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
                row.error_message = "基础调查项目归属已变化；Loop 已创建但需要 Operator 对账"
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
                row.error_message = "该 Loop 已关联其他项目或基础调查；需要 Operator 对账"
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
            409, "LOOP_OWNERSHIP_CONFLICT", "Loop 归属写入发生并发冲突；需要 Operator 对账"
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
    expected_statuses: set[str] | None = None,
) -> None:
    session = _open_session(settings)
    try:
        with session.begin():
            row = session.get(InvestigationLoopSubmission, row_id)
            if row is not None and row.status != "COMPLETED":
                if expected_statuses is not None and row.status not in expected_statuses:
                    return
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
