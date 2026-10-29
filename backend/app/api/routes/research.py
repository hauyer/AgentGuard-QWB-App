"""Project-scoped read and preregistration workflows for AgentGuard RC5."""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from datetime import UTC, datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Body, Depends, Header, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.api.deps import require_role, require_role_csrf
from app.core.data_mode import DataMode
from app.core.db import open_session
from app.integrations.agentguard_client import AgentGuardClient, AgentGuardError
from app.models.app import ProjectStudySubmission
from app.services.auth_service import AppUser
from app.services.project_service import ProjectServiceError, require_project_access

router = APIRouter()

AGENTGUARD_RC5_SOURCE = "71d5017be4108932a00c56e631c63806d66adeeb"
MAX_STUDY_REQUEST_BYTES = 1024 * 1024
IDEMPOTENCY_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


# RC5's StudyRegistrationRequest uses additionalProperties=false. Keep this
# allowlist aligned with that exact frozen schema; upstream remains authoritative
# for the full value constraints and typed validation errors.
REGISTRATION_FIELDS = {
    "schema_version", "title", "research_question", "primary_hypothesis",
    "primary_outcome", "primary_direction", "secondary_outcomes",
    "analysis_method", "multiplicity_method", "alpha", "planned_pairs",
    "planned_case_families", "seed", "matching_variables", "inclusion_criteria",
    "exclusion_criteria", "stopping_rule", "missing_data_rule", "deviations_policy",
    "protocol_version", "code_revision", "track", "protocol_ref", "dataset_ref",
    "dataset_version", "split_sha256", "case_family_ref", "model_id",
    "model_revision", "tokenizer_revision", "decoding_config_ref", "probe_scope",
    "probe_target", "probe_layer", "probe_token", "probe_validation_ref",
    "label_semantics", "metric_definitions", "metric_units", "arms",
    "warden_contract_id", "warden_runtime_id", "warden_mode", "warden_probe_id",
    "warden_sae_id", "warden_capture_targets", "approval_requirements",
    "supersedes_study_id",
}
REQUIRED_REGISTRATION_FIELDS = {
    "title", "research_question", "primary_hypothesis", "primary_outcome",
    "planned_pairs", "planned_case_families", "inclusion_criteria",
    "stopping_rule", "missing_data_rule",
}

def get_agentguard_client(request: Request) -> AgentGuardClient:
    return request.app.state.agentguard_client


ClientDep = Annotated[AgentGuardClient, Depends(get_agentguard_client)]
Viewer = Annotated[AppUser, Depends(require_role("viewer"))]
AnalystCsrf = Annotated[AppUser, Depends(require_role_csrf("analyst"))]
StudySort = Literal["registered_at", "title"]
SortOrder = Literal["asc", "desc"]


def _error(status: int, code: str, message: str, request_id: str | None = None) -> JSONResponse:
    detail: dict[str, Any] = {"error": code, "message": message}
    if request_id:
        detail["request_id"] = request_id
    return JSONResponse(status_code=status, content={"detail": detail})


def _request_fingerprint(payload: dict[str, Any]) -> tuple[str, str]:
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    raw = serialized.encode("utf-8")
    return hashlib.sha256(raw).hexdigest(), serialized


def _source_mode(client: AgentGuardClient, request: Request) -> str:
    configured = (request.app.state.settings.app_data_mode or "").strip().lower()
    if configured in {item.value for item in DataMode}:
        return configured
    try:
        system_capabilities = client.capabilities()
    except AgentGuardError:
        return DataMode.UNAVAILABLE.value
    backend_mode = str(system_capabilities.get("backend_mode", "")).lower()
    return DataMode.SYNTHETIC.value if backend_mode == "synthetic" else DataMode.LIVE.value


def _require_operation(client: AgentGuardClient, key: str) -> JSONResponse | None:
    operations = client.discover_operations()
    if not operations.get(key):
        code = "AGENTGUARD_OPERATION_UNAVAILABLE" if client.discovery_error is None else "AGENTGUARD_OPERATION_UNKNOWN"
        message = (
            f"固定版本未发布所需接口：{key}。"
            if client.discovery_error is None
            else f"无法核验 AgentGuard 是否发布接口：{key}。"
        )
        return _error(503, code, message)
    return None


def _study_record(row: ProjectStudySubmission) -> dict[str, Any]:
    response = None
    if row.response_payload:
        try:
            response = json.loads(row.response_payload)
        except json.JSONDecodeError:
            response = None
    return {
        "study_id": row.study_id,
        "title": row.title,
        "track": row.track,
        "status": row.status,
        "study": response,
        "registration_sha256": row.registration_sha256,
        "request_id": row.request_id,
        "source": {
            "mode": "recorded",
            "origin_mode": row.source_mode,
            "agentguard_commit": row.source_commit,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        },
        "error_code": row.error_code,
        "error_message": row.error_message,
    }


def _project_link(settings, user: AppUser, project_id: int, study_id: str):
    try:
        require_project_access(settings, user, project_id, required_role="viewer")
    except ProjectServiceError as exc:
        return None, _error(exc.status_code, exc.code, str(exc))
    session = open_session(settings)
    if session is None:
        return None, _error(503, "PROJECT_STUDIES_REQUIRE_DATABASE", "研究记录需要已配置的持久化数据库。")
    with session:
        row = session.scalar(select(ProjectStudySubmission).where(
            ProjectStudySubmission.project_id == project_id,
            ProjectStudySubmission.study_id == study_id,
            ProjectStudySubmission.status == "LINKED",
        ))
        if row is None:
            return None, _error(404, "STUDY_NOT_FOUND", "项目中没有此 Study。")
        # Detach only the scalar values used after the session closes.
        session.expunge(row)
    return row, None


@router.get("/research/capabilities", response_model=None)
def research_capabilities(request: Request, client: ClientDep, user: Viewer) -> dict | JSONResponse:
    operation_error = _require_operation(client, "GET /v1/research/capabilities")
    if operation_error:
        return operation_error
    try:
        report = client.get_research_capabilities()
    except AgentGuardError as exc:
        return _error(exc.status_code or 502, exc.code, str(exc), exc.request_id)
    if not isinstance(report.get("capabilities"), list) or not isinstance(report.get("backend_status"), str):
        return _error(502, "RESEARCH_CAPABILITIES_BAD_RESPONSE", "AgentGuard 研究能力报告不符合 RC5 合同。")
    return {
        "meta": {
            "data_mode": _source_mode(client, request),
            "agentguard_commit": AGENTGUARD_RC5_SOURCE,
            "source_note": "能力状态由 AgentGuard RC5 实时返回；API 可连接不代表 WARDEN 已就绪。",
        },
        "report": report,
    }


@router.get("/projects/{project_id}/studies", response_model=None)
def project_studies_list(
    request: Request,
    project_id: int,
    user: Viewer,
    track: Annotated[str | None, Query(max_length=32)] = None,
    sort_by: StudySort = "registered_at",
    sort_order: SortOrder = "desc",
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> dict | JSONResponse:
    settings = request.app.state.settings
    try:
        require_project_access(settings, user, project_id, required_role="viewer")
    except ProjectServiceError as exc:
        return _error(exc.status_code, exc.code, str(exc))
    session = open_session(settings)
    if session is None:
        return _error(503, "PROJECT_STUDIES_REQUIRE_DATABASE", "研究记录需要已配置的持久化数据库。")
    with session:
        conditions = [ProjectStudySubmission.project_id == project_id]
        if track:
            conditions.append(ProjectStudySubmission.track == track)
        total = session.scalar(
            select(func.count()).select_from(ProjectStudySubmission).where(*conditions)
        ) or 0
        sort_column = (
            ProjectStudySubmission.title if sort_by == "title"
            else ProjectStudySubmission.created_at
        )
        ordering = sort_column.asc() if sort_order == "asc" else sort_column.desc()
        rows = session.scalars(
            select(ProjectStudySubmission).where(*conditions).order_by(ordering, ProjectStudySubmission.id)
            .limit(limit).offset(offset)
        ).all()
        items = [_study_record(row) for row in rows]
    next_offset = offset + len(items) if offset + len(items) < total else None
    return {
        "meta": {
            "data_mode": "recorded",
            "source_note": "只列出本项目在 App 中持久化登记的 Study；没有查询或泄露上游全局索引。",
        },
        "items": items,
        "count": len(items),
        "total": total,
        "limit": limit,
        "offset": offset,
        "next_offset": next_offset,
    }


@router.post("/projects/{project_id}/studies", response_model=None)
def project_study_register(
    request: Request,
    project_id: int,
    client: ClientDep,
    user: AnalystCsrf,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=128)],
    payload: Annotated[dict[str, Any], Body()],
) -> dict | JSONResponse:
    settings = request.app.state.settings
    try:
        require_project_access(settings, user, project_id, required_role="analyst")
    except ProjectServiceError as exc:
        return _error(exc.status_code, exc.code, str(exc))
    if not IDEMPOTENCY_PATTERN.fullmatch(idempotency_key):
        return _error(422, "IDEMPOTENCY_KEY_INVALID", "Idempotency-Key 格式不符合 AgentGuard RC5 合同。")
    extra = set(payload) - REGISTRATION_FIELDS
    missing = REQUIRED_REGISTRATION_FIELDS - set(payload)
    if extra:
        return _error(422, "STUDY_REQUEST_FIELDS_INVALID", "Study 请求包含 RC5 未声明的字段。")
    if missing:
        return _error(422, "STUDY_REQUEST_FIELDS_MISSING", "Study 预注册缺少必要字段。")
    fingerprint, serialized = _request_fingerprint(payload)
    if len(serialized.encode("utf-8")) > MAX_STUDY_REQUEST_BYTES:
        return _error(413, "STUDY_REQUEST_TOO_LARGE", "Study 预注册正文超过 App 的大小限制。")
    operation_error = _require_operation(client, "POST /v1/studies")
    if operation_error:
        return operation_error
    session = open_session(settings)
    if session is None:
        return _error(503, "PROJECT_STUDIES_REQUIRE_DATABASE", "Study 注册需要已配置的持久化数据库。")

    idempotency_hash = hashlib.sha256(idempotency_key.encode("utf-8")).hexdigest()
    # The upstream idempotency key is deterministic and contains no user key in
    # clear text. It is stable across an explicit retry after an ambiguous POST.
    upstream_key = hashlib.sha256(
        f"qwb-study:{project_id}:{user.username}:{idempotency_hash}".encode()
    ).hexdigest()
    request_id = str(uuid.uuid4())
    with session:
        row = session.scalar(select(ProjectStudySubmission).where(
            ProjectStudySubmission.project_id == project_id,
            ProjectStudySubmission.created_by == user.username,
            ProjectStudySubmission.idempotency_key_hash == idempotency_hash,
        ))
        if row is not None:
            if row.request_fingerprint != fingerprint:
                return _error(409, "IDEMPOTENCY_CONFLICT", "此幂等键已用于不同的 Study 请求。", row.request_id)
            if row.status == "LINKED":
                return JSONResponse(status_code=200, content={
                    "submission": _study_record(row), "replayed": True,
                })
            if row.status == "REJECTED":
                return _error(409, row.error_code or "STUDY_SUBMISSION_REJECTED",
                              row.error_message or "AgentGuard 已拒绝此 Study 注册。", row.request_id)
            if row.status == "ORPHANED":
                return _error(
                    409, row.error_code or "STUDY_MAPPING_CONFLICT",
                    row.error_message or "上游 Study 无法安全关联到当前项目。", row.request_id,
                )
            # SUBMISSION_AMBIGUOUS is retried only when the caller explicitly
            # repeats this same request with the same key. RC5 guarantees that
            # this upstream replay returns the original Study for the same body.
            # A SUBMITTING row may also belong to a worker that stopped between
            # the durable intent and response commit; an explicit repeat can
            # safely recover it through the same upstream key.
            row.status = "SUBMITTING"
            row.request_id = request_id
            row.error_code = None
            row.error_message = None
        else:
            row = ProjectStudySubmission(
                project_id=project_id,
                title=str(payload.get("title", ""))[:240],
                track=payload.get("track") if isinstance(payload.get("track"), str) else None,
                idempotency_key_hash=idempotency_hash,
                request_fingerprint=fingerprint,
                request_payload=serialized,
                status="SUBMITTING",
                request_id=request_id,
                source_commit=AGENTGUARD_RC5_SOURCE,
                source_mode="unknown",
                created_by=user.username,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
            session.add(row)
        try:
            session.commit()  # durable intent before any upstream POST
            session.refresh(row)
        except IntegrityError:
            session.rollback()
            concurrent = session.scalar(select(ProjectStudySubmission).where(
                ProjectStudySubmission.project_id == project_id,
                ProjectStudySubmission.created_by == user.username,
                ProjectStudySubmission.idempotency_key_hash == idempotency_hash,
            ))
            if concurrent is not None:
                if concurrent.request_fingerprint != fingerprint:
                    return _error(
                        409, "IDEMPOTENCY_CONFLICT",
                        "此幂等键已被并发请求用于不同的 Study 正文。", concurrent.request_id,
                    )
                return JSONResponse(status_code=202, content={
                    "submission": _study_record(concurrent), "replayed": True,
                    "message": "同一请求已在处理中，请稍后查询。",
                })
            return _error(409, "STUDY_SUBMISSION_CONFLICT", "Study 注册与现有项目关联冲突。", request_id)

    # Store whether this AgentGuard instance reports a synthetic backend. This
    # label is separate from WARDEN readiness and the presence of a Study row.
    source_mode = _source_mode(client, request)
    try:
        response = client.register_study(payload, idempotency_key=upstream_key, request_id=request_id)
    except AgentGuardError as exc:
        ambiguous = exc.status_code == 0 or exc.status_code >= 500
        with session:
            saved = session.get(ProjectStudySubmission, row.id)
            if saved is not None:
                saved.status = "SUBMISSION_AMBIGUOUS" if ambiguous else "REJECTED"
                saved.source_mode = source_mode
                saved.error_code = exc.code
                saved.error_message = str(exc)[:500]
                saved.updated_at = datetime.now(UTC)
                session.commit()
        request.app.state.audit_service.record(
            actor=user.username, role=user.role, action="research.study.register",
            target=f"submission:{row.id}", project_id=project_id,
            detail=(
                f"status={'SUBMISSION_AMBIGUOUS' if ambiguous else 'REJECTED'}; "
                f"payload_sha256={fingerprint}; request_id={request_id}"
            ),
        )
        if ambiguous:
            return JSONResponse(status_code=202, content={
                "submission": {"submission_id": row.id, "status": "SUBMISSION_AMBIGUOUS",
                               "title": row.title, "request_id": request_id,
                               "source": {"mode": "recorded", "origin_mode": source_mode,
                                          "agentguard_commit": AGENTGUARD_RC5_SOURCE}},
                "replayed": False,
                "message": "提交结果不确定。请在确认后使用同一 Idempotency-Key 和相同正文显式重试。",
            })
        return _error(exc.status_code or 502, exc.code, str(exc), request_id)

    study_id = response.get("study_id")
    registration_sha256 = response.get("registration_sha256")
    if (
        not isinstance(study_id, str) or not study_id or len(study_id) > 128
        or not isinstance(registration_sha256, str)
        or not SHA256_PATTERN.fullmatch(registration_sha256)
    ):
        with session:
            saved = session.get(ProjectStudySubmission, row.id)
            if saved is not None:
                saved.status = "SUBMISSION_AMBIGUOUS"
                saved.source_mode = source_mode
                saved.error_code = "STUDY_RESPONSE_UNVERIFIED"
                saved.error_message = "AgentGuard returned an incomplete RC5 registration response."
                saved.updated_at = datetime.now(UTC)
                session.commit()
        request.app.state.audit_service.record(
            actor=user.username, role=user.role, action="research.study.register",
            target=f"submission:{row.id}", project_id=project_id,
            detail=(
                f"status=SUBMISSION_AMBIGUOUS; payload_sha256={fingerprint}; "
                f"request_id={request_id}; error=STUDY_RESPONSE_UNVERIFIED; "
                f"source={AGENTGUARD_RC5_SOURCE}"
            ),
        )
        return JSONResponse(status_code=202, content={
            "submission": {"submission_id": row.id, "status": "SUBMISSION_AMBIGUOUS",
                           "title": row.title, "request_id": request_id},
            "replayed": False,
            "message": "AgentGuard 响应缺少可核验的 Study 标识或注册摘要；记录已保留待对账。",
        })

    with session:
        saved = session.get(ProjectStudySubmission, row.id)
        if saved is None:
            return _error(500, "STUDY_MAPPING_MISSING", "Study 注册意图丢失，未建立项目映射。", request_id)
        saved.study_id = study_id
        saved.registration_sha256 = registration_sha256
        saved.response_payload = json.dumps(response, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        saved.source_mode = source_mode
        saved.status = "LINKED"
        saved.error_code = None
        saved.error_message = None
        saved.updated_at = datetime.now(UTC)
        try:
            session.commit()
            session.refresh(saved)
        except IntegrityError:
            session.rollback()
            orphan = session.get(ProjectStudySubmission, row.id)
            if orphan is not None:
                orphan.status = "ORPHANED"
                orphan.response_payload = json.dumps(
                    response, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                )
                orphan.source_mode = source_mode
                orphan.error_code = "STUDY_MAPPING_CONFLICT"
                orphan.error_message = "AgentGuard returned a Study ID that is already linked elsewhere."
                orphan.updated_at = datetime.now(UTC)
                session.commit()
            request.app.state.audit_service.record(
                actor=user.username, role=user.role, action="research.study.register",
                target=f"submission:{row.id}", project_id=project_id,
                detail=(
                    f"status=ORPHANED; payload_sha256={fingerprint}; "
                    f"registration_sha256={registration_sha256}; request_id={request_id}; "
                    f"error=STUDY_MAPPING_CONFLICT; source={AGENTGUARD_RC5_SOURCE}"
                ),
            )
            return _error(
                409, "STUDY_ALREADY_LINKED",
                "AgentGuard 返回的 Study 已映射到其他项目；未向当前项目公开。", request_id,
            )
        result = _study_record(saved)

    request.app.state.audit_service.record(
        actor=user.username, role=user.role, action="research.study.register",
        target=study_id, project_id=project_id,
        detail=(
            f"status=LINKED; payload_sha256={fingerprint}; "
            f"registration_sha256={registration_sha256}; request_id={request_id}; "
            f"source={AGENTGUARD_RC5_SOURCE}"
        ),
    )
    return JSONResponse(status_code=201, content={"submission": result, "replayed": False})


@router.get("/projects/{project_id}/studies/{study_id}", response_model=None)
def project_study_detail(
    request: Request, project_id: int, study_id: str, client: ClientDep, user: Viewer,
) -> dict | JSONResponse:
    row, error = _project_link(request.app.state.settings, user, project_id, study_id)
    if error:
        return error
    operation_error = _require_operation(client, "GET /v1/studies/{study_id}")
    if operation_error:
        return operation_error
    try:
        study = client.get_study(study_id)
    except AgentGuardError as exc:
        return _error(exc.status_code or 502, exc.code, str(exc), exc.request_id)
    if study.get("study_id") != study_id:
        return _error(502, "STUDY_RESPONSE_MISMATCH", "AgentGuard 返回的 Study 标识与项目映射不一致。")
    return {
        "meta": {"data_mode": _source_mode(client, request), "agentguard_commit": AGENTGUARD_RC5_SOURCE,
                 "source_note": "仅在验证本地项目映射后读取 AgentGuard Study 详情。"},
        "study": study,
        "project_registration": _study_record(row),
    }


@router.get("/projects/{project_id}/studies/{study_id}/integrity", response_model=None)
def project_study_integrity(
    request: Request, project_id: int, study_id: str, client: ClientDep, user: Viewer,
) -> dict | JSONResponse:
    _, error = _project_link(request.app.state.settings, user, project_id, study_id)
    if error:
        return error
    operation_error = _require_operation(client, "GET /v1/studies/{study_id}/integrity")
    if operation_error:
        return operation_error
    try:
        integrity = client.get_study_integrity(study_id)
    except AgentGuardError as exc:
        return _error(exc.status_code or 502, exc.code, str(exc), exc.request_id)
    return {
        "meta": {"data_mode": _source_mode(client, request), "agentguard_commit": AGENTGUARD_RC5_SOURCE},
        "integrity": integrity,
    }


@router.get("/projects/{project_id}/studies/{study_id}/analyses", response_model=None)
def project_study_analyses(
    request: Request,
    project_id: int,
    study_id: str,
    client: ClientDep,
    user: Viewer,
    evidence_mode: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
    sort_order: SortOrder = "asc",
) -> dict | JSONResponse:
    _, error = _project_link(request.app.state.settings, user, project_id, study_id)
    if error:
        return error
    operation_error = _require_operation(client, "GET /v1/studies/{study_id}/analyses")
    if operation_error:
        return operation_error
    try:
        report = client.list_study_analyses(
            study_id, evidence_mode=evidence_mode, limit=limit, offset=offset,
            sort_order=sort_order,
        )
    except AgentGuardError as exc:
        return _error(exc.status_code or 502, exc.code, str(exc), exc.request_id)
    if not isinstance(report.get("items"), list):
        return _error(502, "STUDY_ANALYSES_BAD_RESPONSE", "AgentGuard 分析列表不符合 RC5 合同。")
    return {
        "meta": {
            "data_mode": _source_mode(client, request),
            "agentguard_commit": AGENTGUARD_RC5_SOURCE,
            "source_note": "按上游原值展示；每条记录的 evidence_mode、source_validation 和 limitations 决定证据效力。",
        },
        **report,
    }


@router.post("/projects/{project_id}/studies/{study_id}/runs", response_model=None)
def submit_project_study_run(
    request: Request, project_id: int, study_id: str, client: ClientDep, user: AnalystCsrf,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=128)],
    payload: Annotated[dict[str, Any], Body()],
) -> dict | JSONResponse:
    try:
        require_project_access(request.app.state.settings, user, project_id, required_role="analyst")
    except ProjectServiceError as exc:
        return _error(exc.status_code, exc.code, str(exc))
    _, error = _project_link(request.app.state.settings, user, project_id, study_id)
    if error:
        return error
    if (set(payload) != {"arm_id"} or not isinstance(payload["arm_id"], str)
            or not IDEMPOTENCY_PATTERN.fullmatch(payload["arm_id"])
            or not IDEMPOTENCY_PATTERN.fullmatch(idempotency_key)):
        return _error(422, "STUDY_RUN_INVALID", "只允许注册的实验臂及有效幂等键。")
    try:
        return client.submit_study_run(study_id, payload["arm_id"], idempotency_key)
    except AgentGuardError as exc:
        return _error(exc.status_code or 502, exc.code, str(exc), exc.request_id)


@router.get("/projects/{project_id}/studies/{study_id}/run-batches", response_model=None)
def list_project_study_batches(
    request: Request, project_id: int, study_id: str, client: ClientDep, user: Viewer,
    limit: Annotated[int, Query(ge=1, le=100)] = 50, offset: Annotated[int, Query(ge=0)] = 0,
) -> dict | JSONResponse:
    _, error = _project_link(request.app.state.settings, user, project_id, study_id)
    if error:
        return error
    try:
        return client.list_study_batches(study_id, limit=limit, offset=offset)
    except AgentGuardError as exc:
        return _error(exc.status_code or 502, exc.code, str(exc), exc.request_id)


@router.post("/projects/{project_id}/studies/{study_id}/run-batches", response_model=None)
def submit_project_study_batch(
    request: Request, project_id: int, study_id: str, client: ClientDep, user: AnalystCsrf,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=128)],
) -> dict | JSONResponse:
    try:
        require_project_access(request.app.state.settings, user, project_id, required_role="analyst")
    except ProjectServiceError as exc:
        return _error(exc.status_code, exc.code, str(exc))
    _, error = _project_link(request.app.state.settings, user, project_id, study_id)
    if error:
        return error
    if not IDEMPOTENCY_PATTERN.fullmatch(idempotency_key):
        return _error(422, "STUDY_BATCH_INVALID", "批次需要有效幂等键。")
    try:
        return client.submit_study_batch(study_id, idempotency_key)
    except AgentGuardError as exc:
        return _error(exc.status_code or 502, exc.code, str(exc), exc.request_id)


@router.get("/projects/{project_id}/studies/{study_id}/runs", response_model=None)
def list_project_study_runs(
    request: Request, project_id: int, study_id: str, client: ClientDep, user: Viewer,
) -> dict | JSONResponse:
    _, error = _project_link(request.app.state.settings, user, project_id, study_id)
    if error:
        return error
    try:
        return client.list_study_runs(study_id)
    except AgentGuardError as exc:
        return _error(exc.status_code or 502, exc.code, str(exc), exc.request_id)


@router.post("/projects/{project_id}/studies/{study_id}/replicate-batches", response_model=None)
def submit_project_replicate_batch(
    request: Request, project_id: int, study_id: str, client: ClientDep, user: AnalystCsrf,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=128)],
    payload: Annotated[dict[str, Any], Body()],
) -> dict | JSONResponse:
    try:
        require_project_access(request.app.state.settings, user, project_id, required_role="analyst")
    except ProjectServiceError as exc:
        return _error(exc.status_code, exc.code, str(exc))
    _, error = _project_link(request.app.state.settings, user, project_id, study_id)
    if error:
        return error
    if (set(payload) != {"replicate_id"} or not isinstance(payload["replicate_id"], str)
            or not IDEMPOTENCY_PATTERN.fullmatch(payload["replicate_id"])
            or not IDEMPOTENCY_PATTERN.fullmatch(idempotency_key)):
        return _error(422, "REPLICATE_BATCH_INVALID", "重复实验需要新的重复编号和有效提交意图。")
    try:
        return client.submit_replicate_batch(study_id, payload["replicate_id"], idempotency_key)
    except AgentGuardError as exc:
        return _error(exc.status_code or 502, exc.code, str(exc), exc.request_id)


@router.get("/projects/{project_id}/studies/{study_id}/comparisons/batches/{batch_id}", response_model=None)
def project_batch_comparison(
    request: Request, project_id: int, study_id: str, batch_id: str, client: ClientDep, user: Viewer,
) -> dict | JSONResponse:
    _, error = _project_link(request.app.state.settings, user, project_id, study_id)
    if error:
        return error
    if not IDEMPOTENCY_PATTERN.fullmatch(batch_id):
        return _error(422, "COMPARISON_BATCH_INVALID", "批次编号无效。")
    try:
        return client.get_batch_comparison(study_id, batch_id)
    except AgentGuardError as exc:
        return _error(exc.status_code or 502, exc.code, str(exc), exc.request_id)


@router.get("/projects/{project_id}/studies/{study_id}/submission-intents/{intent_key}", response_model=None)
def project_submission_intent(
    request: Request, project_id: int, study_id: str, intent_key: str, client: ClientDep, user: Viewer,
) -> dict | JSONResponse:
    _, error = _project_link(request.app.state.settings, user, project_id, study_id)
    if error:
        return error
    if not IDEMPOTENCY_PATTERN.fullmatch(intent_key):
        return _error(422, "SUBMISSION_INTENT_INVALID", "提交标识无效。")
    try:
        return client.get_submission_intent(study_id, intent_key)
    except AgentGuardError as exc:
        return _error(exc.status_code or 502, exc.code, str(exc), exc.request_id)


@router.get("/projects/{project_id}/studies/{study_id}/arms/{arm_id}/execution-contract", response_model=None)
def project_execution_contract(
    request: Request, project_id: int, study_id: str, arm_id: str, client: ClientDep, user: Viewer,
) -> dict | JSONResponse:
    _, error = _project_link(request.app.state.settings, user, project_id, study_id)
    if error:
        return error
    if not IDEMPOTENCY_PATTERN.fullmatch(arm_id):
        return _error(422, "EXECUTION_ARM_INVALID", "实验臂编号无效。")
    try:
        return client.get_execution_contract(study_id, arm_id)
    except AgentGuardError as exc:
        return _error(exc.status_code or 502, exc.code, str(exc), exc.request_id)


@router.get("/projects/{project_id}/studies/{study_id}/runs/{workflow_id}", response_model=None)
def get_project_study_run(
    request: Request, project_id: int, study_id: str, workflow_id: str,
    client: ClientDep, user: Viewer,
) -> dict | JSONResponse:
    _, error = _project_link(request.app.state.settings, user, project_id, study_id)
    if error:
        return error
    try:
        return client.get_study_run(study_id, workflow_id)
    except AgentGuardError as exc:
        return _error(exc.status_code or 502, exc.code, str(exc), exc.request_id)


@router.get("/projects/{project_id}/studies/{study_id}/runs/{workflow_id}/visualization", response_model=None)
def project_visualization(
    request: Request, project_id: int, study_id: str, workflow_id: str, client: ClientDep,
    user: Viewer, through_seq: Annotated[int | None, Query(ge=0)] = None,
) -> dict | JSONResponse:
    _, error = _project_link(request.app.state.settings, user, project_id, study_id)
    if error:
        return error
    try:
        return client.get_experiment_view(study_id, workflow_id, "visualization", through_seq=through_seq)
    except AgentGuardError as exc:
        return _error(exc.status_code or 502, exc.code, str(exc), exc.request_id)


@router.get("/projects/{project_id}/studies/{study_id}/runs/{workflow_id}/timeline", response_model=None)
def project_timeline(
    request: Request, project_id: int, study_id: str, workflow_id: str, client: ClientDep,
    user: Viewer, after_seq: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> dict | JSONResponse:
    _, error = _project_link(request.app.state.settings, user, project_id, study_id)
    if error:
        return error
    try:
        return client.get_experiment_view(study_id, workflow_id, "timeline", after_seq=after_seq, limit=limit)
    except AgentGuardError as exc:
        return _error(exc.status_code or 502, exc.code, str(exc), exc.request_id)


@router.get("/projects/{project_id}/studies/{study_id}/comparison", response_model=None)
def project_comparison(
    request: Request, project_id: int, study_id: str, client: ClientDep, user: Viewer,
) -> dict | JSONResponse:
    _, error = _project_link(request.app.state.settings, user, project_id, study_id)
    if error:
        return error
    try:
        return client.get_study_comparison(study_id)
    except AgentGuardError as exc:
        return _error(exc.status_code or 502, exc.code, str(exc), exc.request_id)
