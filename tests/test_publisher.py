import base64
import json

import pytest

from conftest import TOPIC_ARN


def call(module, event, context):
    response = module.lambda_handler(event, context)
    return response, json.loads(response["body"])


def test_valid_request_publishes_once_and_returns_200(
    publisher_module, sns_mock, context, load_event
):
    response, body = call(publisher_module, load_event("api-register-ok.json"), context)

    assert response["statusCode"] == 200
    assert response["headers"]["Content-Type"] == "application/json; charset=utf-8"
    assert body == {"message": "User registered and notification sent"}
    sns_mock.publish.assert_called_once_with(
        TopicArn=TOPIC_ARN,
        Message='{"event": "USER_REGISTERED", "name": "Carlos López", "email": "carlos@email.com"}',
        Subject="USER_REGISTERED",
        MessageAttributes={"event": {"DataType": "String", "StringValue": "USER_REGISTERED"}},
    )


def test_non_ascii_name_is_not_escaped(publisher_module, sns_mock, context, api_event):
    call(publisher_module, api_event({"name": "Carlos López", "email": "carlos@email.com"}), context)

    message = sns_mock.publish.call_args.kwargs["Message"]
    assert "López" in message
    assert "\\u" not in message


def test_subject_is_fixed_ascii(publisher_module, sns_mock, context, api_event):
    call(publisher_module, api_event({"name": "Álvaro Ñúñez", "email": "a@email.com"}), context)

    subject = sns_mock.publish.call_args.kwargs["Subject"]
    assert subject == "USER_REGISTERED"
    assert subject.isascii()


@pytest.mark.parametrize(
    "payload, field",
    [
        ({"email": "carlos@email.com"}, "name"),
        ({"name": "Carlos"}, "email"),
        ({}, "name"),
    ],
)
def test_missing_field_returns_400_without_publishing(
    publisher_module, sns_mock, context, api_event, payload, field
):
    response, body = call(publisher_module, api_event(payload), context)

    assert response["statusCode"] == 400
    assert body == {"error": f"Missing field: {field}"}
    sns_mock.publish.assert_not_called()


@pytest.mark.parametrize(
    "payload",
    [
        {"name": "", "email": "a@email.com"},
        {"name": "   ", "email": "a@email.com"},
        {"name": 123, "email": "a@email.com"},
        {"name": None, "email": "a@email.com"},
        {"name": "x" * 101, "email": "a@email.com"},
        {"name": "Carlos", "email": ""},
        {"name": "Carlos", "email": "   "},
        {"name": "Carlos", "email": 42},
        {"name": "Carlos", "email": ["a@email.com"]},
    ],
)
def test_empty_or_wrongly_typed_fields_return_400(
    publisher_module, sns_mock, context, api_event, payload
):
    response, body = call(publisher_module, api_event(payload), context)

    assert response["statusCode"] == 400
    assert "error" in body
    sns_mock.publish.assert_not_called()


@pytest.mark.parametrize(
    "email",
    ["not-an-email", "missing-at.com", "a@b", "@email.com", "a b@email.com", "a@" + "x" * 250 + ".com"],
)
def test_invalid_email_returns_400(publisher_module, sns_mock, context, api_event, email):
    response, _ = call(publisher_module, api_event({"name": "Carlos", "email": email}), context)

    assert response["statusCode"] == 400
    sns_mock.publish.assert_not_called()


@pytest.mark.parametrize("raw_body", ['{"name":', "not json", "[1, 2]", '"text"', "42", "null"])
def test_malformed_or_non_object_json_returns_400(
    publisher_module, sns_mock, context, api_event, raw_body
):
    response, body = call(publisher_module, api_event(raw_body), context)

    assert response["statusCode"] == 400
    assert "error" in body
    sns_mock.publish.assert_not_called()


@pytest.mark.parametrize("raw_body", ["", None])
def test_empty_or_null_body_returns_400(publisher_module, sns_mock, context, api_event, raw_body):
    event = api_event()
    event["body"] = raw_body

    response, _ = call(publisher_module, event, context)

    assert response["statusCode"] == 400
    sns_mock.publish.assert_not_called()


def test_invalid_json_event_file_returns_400(publisher_module, sns_mock, context, load_event):
    response, _ = call(publisher_module, load_event("api-register-invalid-json.json"), context)
    assert response["statusCode"] == 400


def test_missing_email_event_file_returns_400(publisher_module, sns_mock, context, load_event):
    response, body = call(publisher_module, load_event("api-register-missing-email.json"), context)
    assert response["statusCode"] == 400
    assert body == {"error": "Missing field: email"}


def test_base64_body_is_decoded(publisher_module, sns_mock, context, api_event):
    raw = json.dumps({"name": "Carlos López", "email": "carlos@email.com"}, ensure_ascii=False)
    encoded = base64.b64encode(raw.encode("utf-8")).decode("ascii")

    response, _ = call(publisher_module, api_event(encoded, isBase64Encoded=True), context)

    assert response["statusCode"] == 200
    assert "López" in sns_mock.publish.call_args.kwargs["Message"]


def test_invalid_base64_body_returns_400(publisher_module, sns_mock, context, api_event):
    response, _ = call(publisher_module, api_event("%%%not-base64%%%", isBase64Encoded=True), context)

    assert response["statusCode"] == 400
    sns_mock.publish.assert_not_called()


def test_sns_failure_returns_generic_500(publisher_module, sns_mock, context, load_event):
    sns_mock.publish.side_effect = RuntimeError("AccessDenied: /var/task/secret/path.py")

    response, body = call(publisher_module, load_event("api-register-ok.json"), context)

    assert response["statusCode"] == 500
    assert body == {"error": "Internal error"}
    assert "AccessDenied" not in response["body"]


def test_missing_topic_arn_returns_500(
    publisher_module, sns_mock, context, load_event, monkeypatch
):
    monkeypatch.delenv("TOPIC_ARN", raising=False)

    response, body = call(publisher_module, load_event("api-register-ok.json"), context)

    assert response["statusCode"] == 500
    assert body == {"error": "Internal error"}
    sns_mock.publish.assert_not_called()


def test_error_responses_leak_no_traces_or_paths(
    publisher_module, sns_mock, context, api_event, load_event, monkeypatch
):
    responses = [
        publisher_module.lambda_handler(api_event("{bad"), context),
        publisher_module.lambda_handler(api_event({"name": "x"}), context),
    ]
    sns_mock.publish.side_effect = RuntimeError("boom")
    responses.append(publisher_module.lambda_handler(load_event("api-register-ok.json"), context))
    monkeypatch.delenv("TOPIC_ARN")
    responses.append(publisher_module.lambda_handler(load_event("api-register-ok.json"), context))

    for response in responses:
        assert "Traceback" not in response["body"]
        assert ".py" not in response["body"]
        assert "/" not in response["body"]


def test_success_log_has_request_id_status_and_message_id(
    publisher_module, sns_mock, context, load_event, caplog
):
    caplog.set_level("INFO")

    call(publisher_module, load_event("api-register-ok.json"), context)

    entries = [json.loads(r.getMessage()) for r in caplog.records if r.getMessage().startswith("{")]
    assert {"requestId": "req-abc", "statusCode": 200, "messageId": "msg-123"} in entries


def test_logs_never_contain_the_email_or_body(
    publisher_module, sns_mock, context, load_event, api_event, caplog
):
    caplog.set_level("INFO")

    call(publisher_module, load_event("api-register-ok.json"), context)
    call(publisher_module, api_event({"name": "Carlos", "email": "bad-email@"}), context)

    assert "carlos@email.com" not in caplog.text
    assert "bad-email@" not in caplog.text


def test_module_imports_without_topic_arn(monkeypatch):
    import importlib.util

    from conftest import ROOT

    monkeypatch.delenv("TOPIC_ARN", raising=False)
    spec = importlib.util.spec_from_file_location(
        "publisher_import_check", ROOT / "publisher" / "lambda_function.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # must not raise

    assert callable(module.lambda_handler)
