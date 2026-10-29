from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, Request, Response

from app.auth.dependencies import Database, Identity
from app.investigations import service, views
from app.investigations.schema import AddNote, DismissAlert, OpenCase, ResolveCase, ReviewCase

router = APIRouter(prefix="/api/v1")


@router.get("/alerts")
def alerts(
    db: Database, principal: Identity, filters: Annotated[views.AlertFilters, Query()]
) -> dict[str, object]:
    return views.list_alerts(db, principal, filters)


@router.post("/alerts/{identifier}/dismiss")
def dismiss(
    identifier: UUID, payload: DismissAlert, request: Request, db: Database, principal: Identity
) -> dict[str, object]:
    return views.alert_view(
        service.dismiss(db, principal, identifier, payload, request.state.request_id)
    )


@router.post("/alerts/{identifier}/cases", status_code=201)
def open_case(
    identifier: UUID,
    request: Request,
    response: Response,
    db: Database,
    principal: Identity,
    payload: OpenCase | None = None,
) -> dict[str, object]:
    case, created = service.open_case(
        db, principal, identifier, payload or OpenCase(), request.state.request_id
    )
    response.status_code = 201 if created else 200
    return {
        "case_id": case.id,
        "alert_id": case.alert_id,
        "alert_status": "IN_CASE",
        "case": views.case_view(case),
    }


@router.get("/cases")
def cases(
    db: Database, principal: Identity, filters: Annotated[views.CaseFilters, Query()]
) -> dict[str, object]:
    return views.list_cases(db, principal, filters)


@router.get("/cases/{identifier}")
def detail(
    identifier: UUID,
    db: Database,
    principal: Identity,
    events_limit: int = Query(default=50, ge=1, le=100),
    events_cursor: str | None = Query(default=None, max_length=100),
) -> dict[str, object]:
    return views.detail(db, principal, identifier, events_limit, events_cursor)


@router.patch("/cases/{identifier}")
def review(
    identifier: UUID, payload: ReviewCase, request: Request, db: Database, principal: Identity
) -> dict[str, object]:
    return views.case_view(
        service.review(db, principal, identifier, payload, request.state.request_id)
    )


@router.post("/cases/{identifier}/events", status_code=201)
def note(
    identifier: UUID, payload: AddNote, request: Request, db: Database, principal: Identity
) -> dict[str, object]:
    return views.event_view(
        service.add_note(db, principal, identifier, payload, request.state.request_id)
    )


@router.post("/cases/{identifier}/resolve")
def resolve(
    identifier: UUID, payload: ResolveCase, request: Request, db: Database, principal: Identity
) -> dict[str, object]:
    return views.case_view(
        service.resolve(db, principal, identifier, payload, request.state.request_id)
    )
