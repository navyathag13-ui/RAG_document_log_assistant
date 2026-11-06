"""Work-order field extraction: grounding checks, the retry, the fallback and
the /extract endpoint. The model is replaced by scripted replies so these run
offline, but they go through the real extraction_service code paths."""
import json
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.main import app
from app.services import extraction_service as ex

DOC = """WORK ORDER WO-2291
Equipment: PMP-104 (Coolant Pump 4)
Date: March 3, 2026
Technician: Maria Lopez
Replaced 2 bearings and 1 mechanical seal. Pump was down for 90 minutes.
Status: closed, running normally."""


def reply(**overrides):
    body = {
        "equipment_id": "PMP-104",
        "work_date": "2026-03-03",
        "technician": "Maria Lopez",
        "parts": [{"name": "bearings", "quantity": 2}, {"name": "mechanical seal", "quantity": 1}],
        "downtime_hours": 1.5,
        "status": "resolved",
        "needs_human_review": False,
    }
    body.update(overrides)
    return json.dumps(body)


def scripted(*replies):
    seen = []

    def call(feedback):
        seen.append(feedback)
        return replies[len(seen) - 1]

    return call, seen


def test_valid_reply_passes_first_time():
    fields, meta = ex.generate(scripted(reply())[0], DOC)
    assert meta.validated and meta.attempts == 1
    assert fields.equipment_id == "PMP-104" and fields.downtime_hours == 1.5
    assert [p.quantity for p in fields.parts] == [2, 1]


def test_made_up_values_fail_grounding():
    for bad in (
        {"equipment_id": "PMP-401"},
        {"technician": "Mark Lopez"},
        {"parts": [{"name": "impeller", "quantity": 1}]},
        {"work_date": "2025-03-03"},
        {"work_date": "2026-03-17"},
        {"work_date": "03/03/2026"},
    ):
        try:
            ex.parse(reply(**bad), DOC)
        except Exception:
            continue
        raise AssertionError(f"{bad} should have failed validation")


def test_out_of_range_numbers_fail():
    for bad in ({"parts": [{"name": "bearings", "quantity": 0}]}, {"downtime_hours": -1}, {"status": "done"}):
        try:
            ex.parse(reply(**bad), DOC)
        except Exception:
            continue
        raise AssertionError(f"{bad} should have failed validation")


def test_retry_tells_the_model_what_was_wrong():
    call, seen = scripted(reply(equipment_id="PMP-401"), reply())
    fields, meta = ex.generate(call, DOC)
    assert meta.validated and meta.attempts == 2
    assert seen[0] is None and "PMP-401" in seen[1]


def test_two_bad_replies_give_empty_fields_and_review():
    call, _ = scripted(reply(technician="Mark Lopez"), "not json")
    fields, meta = ex.generate(call, DOC)
    assert meta.fallback_used and not meta.validated and meta.errors
    assert fields.equipment_id is None and fields.parts == [] and fields.needs_human_review


def test_missing_equipment_or_date_forces_review():
    fields, _ = ex.generate(scripted(reply(work_date=None))[0], DOC)
    assert fields.work_date is None and fields.needs_human_review


def test_plural_part_names_match_the_document():
    fields = ex.parse(reply(parts=[{"name": "bearing", "quantity": 2}]), DOC)
    assert fields.parts[0].name == "bearing"


def test_extract_without_llm_is_offline_and_flagged():
    fields, meta, provider = ex.extract(DOC)
    assert provider == "none" and meta.mode == "offline" and fields.needs_human_review


def test_extract_uses_the_given_client():
    msg = SimpleNamespace(content=reply())
    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(
        create=lambda **kw: SimpleNamespace(choices=[SimpleNamespace(message=msg)]))))
    fields, meta, _ = ex.extract(DOC, client=client, model="m")
    assert meta.validated and fields.technician == "Maria Lopez"


def test_extract_endpoint_offline(tmp_path):
    with TestClient(app) as client:
        r = client.post("/extract", files={"file": ("wo.txt", DOC.encode(), "text/plain")})
        assert r.status_code == 200
        body = r.json()
        assert body["provider"] == "none" and body["fields"]["needs_human_review"] is True
        bad = client.post("/extract", files={"file": ("wo.exe", b"x", "application/octet-stream")})
        assert bad.status_code == 415
