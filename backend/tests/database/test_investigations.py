"""PYTEST_DONT_REWRITE: fictional notes and credentials stay out of failure logs."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from threading import Barrier
from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete, event, func, select
from sqlalchemy.orm import sessionmaker
from test_ingestion import client as client
from test_ingestion import ingestion as ingestion
from test_ingestion import password_hash as password_hash
from test_models import ml as ml
from test_transaction_scoring import PAYLOAD, submit
from test_transaction_scoring import scoring as scoring

from app.auth.errors import AuthError
from app.investigations import service
from app.investigations.schema import AddNote, DismissAlert, OpenCase, ResolveCase, ReviewCase
from app.models import (
    Alert,
    AuditLog,
    Case,
    CaseEvent,
    Membership,
    ModelVersion,
    Organization,
    RiskSettings,
    Transaction,
    TransactionLabel,
)

pytestmark = pytest.mark.database
RESOLUTION = {
    "resolution": "INCONCLUSIVE",
    "resolution_note": "Fictional evidence is insufficient.",
    "version": 2,
}


@pytest.fixture
def investigation(scoring, migrated_engine):
    _, sessions, _, principal, _ = scoring
    with sessions.begin() as db:
        db.get(RiskSettings, principal.organization_id).alert_threshold = 0
    result, _ = submit(scoring)
    try:
        yield scoring, result
    finally:
        with sessionmaker(migrated_engine).begin() as db:
            cases = select(Case.id).where(Case.organization_id == principal.organization_id)
            db.execute(delete(CaseEvent).where(CaseEvent.case_id.in_(cases)))
            db.execute(delete(Case).where(Case.organization_id == principal.organization_id))


def open_case(investigation, note=None):
    fixture, result = investigation
    with fixture[1].begin() as db:
        case, created = service.open_case(
            db, fixture[3], result["alert_id"], OpenCase(note=note), "fixture"
        )
        return case.id, created


def begin_review(investigation, identifier):
    fixture, _ = investigation
    with fixture[1].begin() as db:
        service.review(
            db, fixture[3], identifier, ReviewCase(status="IN_REVIEW", version=1), "fixture"
        )


@pytest.mark.parametrize("role", ["ANALYST", "RISK_MANAGER", "ADMIN"])
def test_real_api_journey_preserves_evidence_and_redacts_audit(investigation, client, role):
    fixture, result = investigation
    _, sessions, _, principal, _ = fixture
    browser, headers = client
    with sessions.begin() as db:
        db.get(Membership, principal.membership_id).role = role
    tx_path = f"/api/v1/transactions/{result['transaction_id']}"
    original = browser.get(tx_path).json()["score"]
    explanation = browser.get(tx_path + "/explanation").json()
    alert_path = f"/api/v1/alerts/{result['alert_id']}"
    listed = browser.get("/api/v1/alerts?status=NEW").json()["items"]
    assert len(listed) == 1 and listed[0]["transaction_id"] == str(result["transaction_id"])
    opened = browser.post(
        alert_path + "/cases", headers=headers, json={"note": "Fictional opening note"}
    )
    assert opened.status_code == 201
    identifier = opened.json()["case_id"]
    path = f"/api/v1/cases/{identifier}"
    assert opened.json()["case"]["version"] == 1 and opened.json()["alert_status"] == "IN_CASE"
    assert (
        browser.post(
            alert_path + "/cases", headers=headers, json={"note": "Fictional opening note"}
        ).status_code
        == 200
    )
    assert (
        browser.post(alert_path + "/cases", headers=headers, json={"note": "different"}).status_code
        == 409
    )
    assert (
        browser.post(alert_path + "/dismiss", headers=headers, json={"reason": "demo"}).status_code
        == 409
    )
    assert (
        browser.post(
            path + "/resolve", headers=headers, json={**RESOLUTION, "version": 1}
        ).status_code
        == 409
    )
    review = browser.patch(path, headers=headers, json={"status": "IN_REVIEW", "version": 1})
    assert review.status_code == 200 and review.json()["version"] == 2
    assert (
        browser.patch(path, headers=headers, json={"status": "IN_REVIEW", "version": 1}).status_code
        == 409
    )
    note = browser.post(
        path + "/events", headers=headers, json={"note": "<script>fictional-note-marker</script>"}
    )
    assert note.status_code == 201 and note.json()["action"] == "NOTE_ADDED"
    closed = browser.post(path + "/resolve", headers=headers, json=RESOLUTION)
    assert closed.status_code == 200 and closed.json()["status"] == "CLOSED"
    assert (
        closed.json()["version"] == 3 and closed.json()["closed_at"] == closed.json()["updated_at"]
    )
    assert browser.post(path + "/resolve", headers=headers, json=RESOLUTION).json() == closed.json()
    assert (
        browser.post(
            path + "/resolve", headers=headers, json={**RESOLUTION, "resolution": "FALSE_POSITIVE"}
        ).status_code
        == 409
    )
    assert browser.post(path + "/events", headers=headers, json={"note": "late"}).status_code == 409
    assert (
        browser.patch(path, headers=headers, json={"status": "IN_REVIEW", "version": 3}).status_code
        == 409
    )
    details = browser.get(path).json()
    assert details["score"] == original and details["explanation"] == explanation
    assert [e["action"] for e in details["events"]] == [
        "CASE_OPENED",
        "STATUS_CHANGED",
        "NOTE_ADDED",
        "CASE_CLOSED",
    ]
    assert all(e["actor_user_id"] == str(principal.user_id) for e in details["events"])
    assert browser.get(tx_path).json()["score"] == original
    assert browser.get("/api/v1/cases?status=CLOSED").json()["items"][0]["id"] == identifier
    with sessions() as db:
        audits = list(db.scalars(select(AuditLog).where(AuditLog.resource_id == UUID(identifier))))
        assert len(audits) == 4 and all(a.request_id for a in audits)
        assert "fictional-note-marker" not in str([a.metadata_json for a in audits])
        assert not db.scalar(
            select(TransactionLabel.transaction_id).where(
                TransactionLabel.transaction_id == result["transaction_id"]
            )
        )


def test_dismissal_and_optional_body(investigation, client):
    fixture, result = investigation
    browser, headers = client
    path = f"/api/v1/alerts/{result['alert_id']}"
    dismissed = browser.post(
        path + "/dismiss", headers=headers, json={"reason": "  Fictional dismissal  "}
    )
    assert dismissed.status_code == 200
    assert dismissed.json()["dismissal_reason"] == "Fictional dismissal"
    assert dismissed.json()["dismissed_by"] == str(fixture[3].user_id)
    assert (
        browser.post(path + "/dismiss", headers=headers, json={"reason": "again"}).status_code
        == 409
    )
    assert browser.post(path + "/cases", headers=headers).status_code == 409
    other, _ = submit(fixture, {**PAYLOAD, "external_id": "another"})
    assert (
        browser.post(f"/api/v1/alerts/{other['alert_id']}/cases", headers=headers).status_code
        == 201
    )
    with fixture[1]() as db:
        audit = db.scalars(select(AuditLog).where(AuditLog.resource_id == result["alert_id"])).one()
        assert "Fictional dismissal" not in str(audit.metadata_json)


@pytest.mark.parametrize(
    "method,suffix,payload",
    [
        ("post", "alert/dismiss", {"reason": "demo"}),
        ("post", "alert/cases", {}),
        ("patch", "case", {"status": "IN_REVIEW", "version": 1}),
        ("post", "case/events", {"note": "demo"}),
        ("post", "case/resolve", RESOLUTION),
    ],
)
def test_auth_csrf_and_wrong_org_mutations(investigation, client, method, suffix, payload):
    fixture, result = investigation
    identifier, _ = open_case(investigation)
    browser, headers = client
    kind, _, tail = suffix.partition("/")
    path = (
        f"/api/v1/alerts/{result['alert_id']}" if kind == "alert" else f"/api/v1/cases/{identifier}"
    )
    if tail:
        path += "/" + tail
    send = getattr(browser, method)
    assert send(path, headers={"origin": "http://testserver"}, json=payload).status_code == 403
    assert (
        send(
            path, headers={**headers, "Origin": "https://hostile.invalid"}, json=payload
        ).status_code
        == 403
    )
    assert send(path, headers={**headers, "X-CSRF-Token": "wrong"}, json=payload).status_code == 403
    from app.auth.dependencies import authenticated

    browser.app.dependency_overrides[authenticated] = lambda: replace(
        fixture[3], organization_id=uuid4()
    )
    try:
        assert send(path, headers=headers, json=payload).status_code == 404
    finally:
        browser.app.dependency_overrides.clear()
    browser.cookies.clear()
    assert send(path, headers=headers, json=payload).status_code == 401


@pytest.mark.parametrize(
    "path", ["/alerts", "/cases", "/cases/00000000-0000-0000-0000-000000000001"]
)
def test_reads_require_auth(investigation, client, path):
    browser, _ = client
    browser.cookies.clear()
    assert browser.get("/api/v1" + path).status_code == 401


def test_json_body_and_note_bounds(investigation, client, caplog):
    identifier, _ = open_case(investigation)
    browser, headers = client
    path = f"/api/v1/cases/{identifier}/events"
    assert browser.post(path, headers=headers, json={"note": "😀" * 2000}).status_code == 201
    for note in (" ", "x" * 2001, "bad\u0000input"):
        assert browser.post(path, headers=headers, json={"note": note}).status_code == 422
    response = browser.post(path, headers=headers, content=b'{"note":"' + b"x" * 33000 + b'"}')
    assert response.status_code == 413 and "x" * 100 not in response.text + caplog.text


@pytest.mark.parametrize(
    "race", ["open", "dismiss_open", "review", "resolve", "conflicting_resolve", "note_resolve"]
)
def test_real_postgres_concurrency(investigation, race):
    fixture, result = investigation
    identifier = None
    if race not in {"open", "dismiss_open"}:
        identifier, _ = open_case(investigation)
        if race != "review":
            begin_review(investigation, identifier)
    barrier = Barrier(2)

    def run(index):
        try:
            with fixture[1].begin() as db:
                barrier.wait(timeout=10)
                if race == "open" or (race == "dismiss_open" and index == 0):
                    return service.open_case(
                        db, fixture[3], result["alert_id"], OpenCase(), "race"
                    )[1]
                if race == "dismiss_open":
                    service.dismiss(
                        db, fixture[3], result["alert_id"], DismissAlert(reason="demo"), "race"
                    )
                elif race == "review":
                    service.review(
                        db,
                        fixture[3],
                        identifier,
                        ReviewCase(status="IN_REVIEW", version=1),
                        "race",
                    )
                elif race == "note_resolve" and index == 0:
                    service.add_note(db, fixture[3], identifier, AddNote(note="race note"), "race")
                else:
                    value = (
                        {**RESOLUTION, "resolution": "FALSE_POSITIVE"}
                        if race == "conflicting_resolve" and index == 0
                        else RESOLUTION
                    )
                    service.resolve(db, fixture[3], identifier, ResolveCase(**value), "race")
                return "ok"
        except AuthError as exc:
            return exc.status

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(run, (0, 1)))
    with fixture[1]() as db:
        cases = list(
            db.scalars(select(Case).where(Case.organization_id == fixture[3].organization_id))
        )
        assert len(cases) <= 1
        if race == "open":
            assert sorted(results) == [False, True] and len(cases) == 1
        elif race in {"dismiss_open", "review", "conflicting_resolve"}:
            assert results.count(409) == 1
        elif race == "resolve":
            assert results == ["ok", "ok"]
        else:
            assert results[1] == "ok" and results[0] in ("ok", 409)
        if cases:
            events = list(
                db.scalars(
                    select(CaseEvent)
                    .where(CaseEvent.case_id == cases[0].id)
                    .order_by(CaseEvent.created_at, CaseEvent.id)
                )
            )
            actions = [e.action for e in events]
            assert actions.count("CASE_OPENED") == 1 and actions.count("CASE_CLOSED") <= 1
            if "CASE_CLOSED" in actions:
                assert actions[-1] == "CASE_CLOSED" and cases[0].version == 3
            assert db.scalar(
                select(func.count())
                .select_from(AuditLog)
                .where(AuditLog.resource_id == cases[0].id)
            ) == len(events)
        assert db.get(Alert, result["alert_id"]).status == ("IN_CASE" if cases else "DISMISSED")


@pytest.mark.parametrize(
    "operation,failure",
    [
        (operation, failure)
        for operation in ("open", "dismiss", "review", "note", "resolve")
        for failure in ("audit_logs", "case_events")
        if operation != "dismiss" or failure != "case_events"
    ],
)
def test_atomic_rollback_after_write_failure(investigation, operation, failure):
    fixture, result = investigation
    identifier = None
    if operation not in {"open", "dismiss"}:
        identifier, _ = open_case(investigation)
        if operation == "resolve":
            begin_review(investigation, identifier)
    with fixture[1]() as db:
        before = (
            db.get(Alert, result["alert_id"]).status,
            db.scalar(select(func.count()).select_from(CaseEvent)),
            db.scalar(select(func.count()).select_from(AuditLog)),
        )
        case = db.get(Case, identifier) if identifier else None
        case_state = (case.status, case.version, case.updated_at) if case else None

    def fail(connection, cursor, statement, parameters, context, executemany):
        if statement.startswith(f"INSERT INTO {failure}"):
            raise RuntimeError("fixture failure")

    event.listen(fixture[0], "before_cursor_execute", fail)
    try:
        with pytest.raises(RuntimeError, match="fixture failure"), fixture[1].begin() as db:
            if operation == "open":
                service.open_case(db, fixture[3], result["alert_id"], OpenCase(), "failure")
            elif operation == "dismiss":
                service.dismiss(
                    db, fixture[3], result["alert_id"], DismissAlert(reason="demo"), "failure"
                )
            elif operation == "review":
                service.review(
                    db, fixture[3], identifier, ReviewCase(status="IN_REVIEW", version=1), "failure"
                )
            elif operation == "note":
                service.add_note(db, fixture[3], identifier, AddNote(note="demo"), "failure")
            else:
                service.resolve(db, fixture[3], identifier, ResolveCase(**RESOLUTION), "failure")
    finally:
        event.remove(fixture[0], "before_cursor_execute", fail)
    with fixture[1]() as db:
        assert before == (
            db.get(Alert, result["alert_id"]).status,
            db.scalar(select(func.count()).select_from(CaseEvent)),
            db.scalar(select(func.count()).select_from(AuditLog)),
        )
        if identifier:
            case = db.get(Case, identifier)
            assert (case.status, case.version, case.updated_at) == case_state
        else:
            assert not db.scalar(
                select(Case.id).where(Case.organization_id == fixture[3].organization_id)
            )


def test_stable_lists_filters_and_bounded_timeline(investigation, client, migrated_engine):
    fixture, first = investigation
    browser, _ = client
    identifiers = [open_case(investigation)[0]]
    for index in range(2):
        result, _ = submit(fixture, {**PAYLOAD, "external_id": f"page-{index}"})
        identifiers.append(open_case((fixture, result))[0])
    stamp = datetime(2026, 2, 1, tzinfo=UTC)
    with sessionmaker(migrated_engine).begin() as db:
        for alert in db.scalars(
            select(Alert).where(Alert.organization_id == fixture[3].organization_id)
        ):
            alert.created_at = stamp
        for case in db.scalars(
            select(Case).where(Case.organization_id == fixture[3].organization_id)
        ):
            case.updated_at = stamp
        for index in range(105):
            db.add(
                CaseEvent(
                    case_id=identifiers[0],
                    actor_user_id=fixture[3].user_id,
                    action="NOTE_ADDED",
                    note="Fictional page fixture",
                    previous_status="OPEN",
                    new_status="OPEN",
                    created_at=stamp + timedelta(seconds=index),
                )
            )
    for resource in ("alerts", "cases"):
        seen, cursor = [], None
        while True:
            data = browser.get(
                f"/api/v1/{resource}", params={"limit": 1, **({"cursor": cursor} if cursor else {})}
            ).json()
            seen.extend(row["id"] for row in data["items"])
            cursor = data["next_cursor"]
            if cursor is None:
                break
        assert len(seen) == 3 and seen == sorted(set(seen))
        assert browser.get(
            f"/api/v1/{resource}",
            params={
                "date_from": stamp.isoformat(),
                "date_to": (stamp + timedelta(seconds=1)).isoformat(),
            },
        ).json()["items"]
        assert (
            browser.get(f"/api/v1/{resource}", params={"date_to": stamp.isoformat()}).json()[
                "items"
            ]
            == []
        )
        for query in ({"limit": 101}, {"cursor": "bad"}, {"date_from": "2026-01-01"}):
            assert browser.get(f"/api/v1/{resource}", params=query).status_code == 422
    assert browser.get("/api/v1/alerts?status=NEW").json()["items"] == []
    band = browser.get(f"/api/v1/transactions/{first['transaction_id']}").json()["score"][
        "risk_band"
    ]
    assert len(browser.get("/api/v1/alerts", params={"risk_band": band}).json()["items"]) == 3
    path = f"/api/v1/cases/{identifiers[0]}"
    seen, cursor = [], None
    query_counts = []

    def count(*args):
        if args[2].lstrip().upper().startswith("SELECT"):
            query_counts.append(1)

    event.listen(fixture[0], "before_cursor_execute", count)
    try:
        while True:
            data = browser.get(
                path, params={"events_limit": 25, **({"events_cursor": cursor} if cursor else {})}
            ).json()
            assert len(data["events"]) <= 25
            seen.extend(row["id"] for row in data["events"])
            cursor = data["next_events_cursor"]
            if cursor is None:
                break
    finally:
        event.remove(fixture[0], "before_cursor_execute", count)
    assert len(seen) == len(set(seen)) == 106
    assert len(query_counts) <= 60  # Fixed query budget over five pages; no per-event queries.
    assert browser.get(path + "?events_limit=101").status_code == 422
    assert browser.get(path + "?events_cursor=invalid").status_code == 422


@pytest.mark.parametrize("broken_link", ["alert", "transaction", "model"])
def test_cross_org_parent_chain_is_never_exposed(
    investigation, client, migrated_engine, broken_link
):
    fixture, result = investigation
    identifier, _ = open_case(investigation)
    browser, headers = client
    foreign = uuid4()
    model, record_id = {
        "alert": (Alert, result["alert_id"]),
        "transaction": (Transaction, result["transaction_id"]),
        "model": (ModelVersion, result["model_version_id"]),
    }[broken_link]
    with sessionmaker(migrated_engine).begin() as db:
        db.add(Organization(id=foreign, name="Fictional boundary fixture"))
        db.flush()
        db.get(model, record_id).organization_id = foreign
    try:
        assert browser.get("/api/v1/alerts").json()["items"] == []
        assert browser.get("/api/v1/cases").json()["items"] == []
        assert browser.get(f"/api/v1/cases/{identifier}").status_code == 404
        assert (
            browser.post(
                f"/api/v1/cases/{identifier}/events", headers=headers, json={"note": "demo"}
            ).status_code
            == 404
        )
        assert (
            browser.post(f"/api/v1/alerts/{result['alert_id']}/cases", headers=headers).status_code
            == 404
        )
    finally:
        with sessionmaker(migrated_engine).begin() as db:
            db.get(model, record_id).organization_id = fixture[3].organization_id
            db.execute(delete(Organization).where(Organization.id == foreign))
