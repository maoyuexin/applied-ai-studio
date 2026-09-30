import copy
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import catalog_demo as demo


def fixture_response(record, data):
    fields = {}
    for name, expected in record["reference"].items():
        value = None
        if expected["status"] == "supported":
            value = expected.get("values", [" ".join(expected.get("contains", []))])[0]
        evidence = [{"source_id": document["id"], "quote": document["text"]}
                    for document in record["documents"]] if expected["status"] != "missing" else []
        fields[name] = {"status": expected["status"], "value": value,
                        "qualifier": expected["qualifier"], "evidence": evidence}
    return {"product_id": record["id"], "fields": fields, "title": record["name"],
            "bullets": [{"text": f"Product code: {record['id']}", "fields": ["product_code"]}]}


def test_evidence_and_prompt_boundary():
    data = demo.load_evidence()
    assert [record["kind"] for record in data["records"]].count("real") == 3
    assert [record["kind"] for record in data["records"]].count("fictional") == 2
    for record in data["records"]:
        prompt = json.loads(demo.make_prompt(data, record))
        assert set(prompt) == {"product_id", "documents", "fields"}
        assert "reference" not in prompt and "required" not in prompt
        assert set(record["reference"]) == set(record["field_names"])


@pytest.mark.parametrize("index,route", [(0, "Human review"), (1, "Hold"), (2, "Human review"), (3, "Hold"), (4, "Hold")])
def test_reference_routes(index, route):
    data = demo.load_evidence()
    record = data["records"][index]
    response = fixture_response(record, data)
    report = demo.evaluate(json.dumps(response), data, record)
    assert report["schema_ok"]
    assert report["reference_correct"] == len(record["field_names"])
    assert report["route"] == route


def test_negative_mutations():
    data = demo.load_evidence()
    record = data["records"][0]
    original = fixture_response(record, data)
    response = copy.deepcopy(original)
    response["fields"]["length_cm"]["value"] = 8
    assert demo.evaluate(json.dumps(response), data, record)["route"] == "Hold"
    response = copy.deepcopy(original)
    response["fields"]["length_cm"]["qualifier"] = "exact"
    assert demo.evaluate(json.dumps(response), data, record)["route"] == "Hold"
    response = copy.deepcopy(original)
    response["fields"]["material"]["evidence"][0]["quote"] = "Invented exact quotation"
    assert demo.evaluate(json.dumps(response), data, record)["route"] == "Hold"
    response = copy.deepcopy(original)
    response["bullets"][0]["text"] = "Guaranteed waterproof bunting"
    assert demo.evaluate(json.dumps(response), data, record)["route"] == "Hold"
    for raw in ["not json", "[]", json.dumps({**original, "extra": True})]:
        assert not demo.evaluate(raw, data, record)["schema_ok"]


def test_pack_and_conflict_are_not_silently_resolved():
    data = demo.load_evidence()
    for index, name, value in [(3, "selling_unit", "six-pack"), (4, "capacity_ml", 750)]:
        record = data["records"][index]
        response = fixture_response(record, data)
        response["fields"][name].update(status="supported", value=value,
            qualifier="exact" if isinstance(value, int) else None,
            evidence=[{"source_id": record["documents"][0]["id"], "quote": record["documents"][0]["text"]}])
        report = demo.evaluate(json.dumps(response), data, record)
        assert report["route"] == "Hold"
        assert any("reference check" in issue for issue in report["issues"])


@pytest.mark.skipif(not demo.CAPTURE.exists(), reason="Actual model capture not yet recorded")
def test_saved_capture_is_authentic_and_reproducible(tmp_path):
    data, saved, reports = demo.replay()
    assert len(reports) == 5
    assert all(report["raw_response"] and report["seconds"] > 0 for report in reports)
    assert saved["model"] == demo.MODEL
    changed = copy.deepcopy(saved)
    changed["records"][0]["raw_response"] += " "
    filename = tmp_path / "mutated.json"
    filename.write_text(json.dumps(changed))
    with pytest.raises(ValueError, match="fingerprint"):
        demo.replay(filename)