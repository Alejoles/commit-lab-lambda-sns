"""Shared fixtures.

Both Lambdas are named lambda_function.py, so each one is loaded with importlib
under a distinct module name to avoid a name clash.
"""

import copy
import importlib.util
import json
import os
from pathlib import Path
from unittest import mock

import pytest

ROOT = Path(__file__).resolve().parent.parent

# boto3 needs a region to build a client at import time; no AWS call is made.
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
os.environ.setdefault("AWS_ACCESS_KEY_ID", "testing")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "testing")

TOPIC_ARN = "arn:aws:sns:<REGION>:<ACCOUNT_ID>:user-events"


def _load(name, relative_path):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="session")
def publisher_module():
    return _load("publisher_lambda", "publisher/lambda_function.py")


@pytest.fixture(scope="session")
def subscriber_module():
    return _load("subscriber_lambda", "subscriber/lambda_function.py")


@pytest.fixture
def sns_mock(publisher_module, monkeypatch):
    client = mock.Mock()
    client.publish.return_value = {"MessageId": "msg-123"}
    monkeypatch.setattr(publisher_module, "sns_client", client)
    monkeypatch.setenv("TOPIC_ARN", TOPIC_ARN)
    return client


@pytest.fixture
def context():
    return mock.Mock(aws_request_id="req-abc")


@pytest.fixture
def load_event():
    def _load_event(name):
        with open(ROOT / "events" / name, encoding="utf-8") as handle:
            return json.load(handle)

    return _load_event


@pytest.fixture
def api_event(load_event):
    """Factory: the valid API Gateway event with an optional replaced body."""

    def _build(body=None, **overrides):
        event = copy.deepcopy(load_event("api-register-ok.json"))
        if body is not None:
            event["body"] = body if isinstance(body, str) else json.dumps(body)
        event.update(overrides)
        return event

    return _build
