import copy
import json

import pytest


def log_entries(caplog):
    entries = []
    for record in caplog.records:
        try:
            entries.append(json.loads(record.getMessage()))
        except ValueError:
            pass
    return entries


def record_with(message, message_id="id-1"):
    return {"Sns": {"MessageId": message_id, "Message": message}}


def test_valid_record_logs_success_with_event_id_and_masked_email(
    subscriber_module, load_event, caplog
):
    caplog.set_level("INFO")

    result = subscriber_module.lambda_handler(load_event("sns-user-registered.json"), None)

    assert result == {"status": "ok"}
    assert log_entries(caplog) == [
        {
            "message": "evento procesado con éxito",
            "event": "USER_REGISTERED",
            "messageId": "95df01b4-ee98-5cb9-9903-4c221d41eb5e",
            "email": "c***@email.com",
        }
    ]


def test_all_records_are_processed(subscriber_module, load_event, caplog):
    caplog.set_level("INFO")
    event = copy.deepcopy(load_event("sns-user-registered.json"))
    second = json.dumps({"event": "USER_REGISTERED", "name": "Ana", "email": "ana@email.com"})
    event["Records"].append(record_with(second, "id-2"))
    event["Records"].append(record_with(second, "id-3"))

    subscriber_module.lambda_handler(event, None)

    entries = log_entries(caplog)
    assert [e["messageId"] for e in entries] == [
        "95df01b4-ee98-5cb9-9903-4c221d41eb5e",
        "id-2",
        "id-3",
    ]
    assert entries[1]["email"] == "a***@email.com"


def test_non_json_message_logs_error_and_raises(subscriber_module, caplog):
    caplog.set_level("INFO")
    event = {"Records": [record_with("this is not json", "bad-1")]}

    with pytest.raises(ValueError):
        subscriber_module.lambda_handler(event, None)

    errors = [r for r in caplog.records if r.levelname == "ERROR"]
    assert len(errors) == 1
    assert "bad-1" in errors[0].getMessage()


def test_bad_record_does_not_prevent_processing_the_others(subscriber_module, caplog):
    caplog.set_level("INFO")
    good = json.dumps({"event": "USER_REGISTERED", "email": "carlos@email.com"})
    event = {"Records": [record_with("nope", "bad"), record_with(good, "good")]}

    with pytest.raises(ValueError):
        subscriber_module.lambda_handler(event, None)

    assert [e["messageId"] for e in log_entries(caplog) if "event" in e] == ["good"]


def test_logs_never_contain_the_full_email(subscriber_module, load_event, caplog):
    caplog.set_level("DEBUG")

    subscriber_module.lambda_handler(load_event("sns-user-registered.json"), None)

    assert "carlos@email.com" not in caplog.text
    assert "carlos@" not in caplog.text


@pytest.mark.parametrize(
    "email, expected",
    [
        ("carlos@email.com", "c***@email.com"),
        ("a@b.co", "a***@b.co"),
        ("no-at-sign", "***"),
        ("@email.com", "***"),
        (None, "***"),
        (123, "***"),
    ],
)
def test_mask_email(subscriber_module, email, expected):
    assert subscriber_module.mask_email(email) == expected


def test_message_without_email_still_succeeds(subscriber_module, caplog):
    caplog.set_level("INFO")
    event = {"Records": [record_with(json.dumps({"event": "USER_REGISTERED"}))]}

    subscriber_module.lambda_handler(event, None)

    assert log_entries(caplog)[0]["email"] == "***"
