"""Publisher Lambda: POST /register -> validates the body and publishes to SNS.

Triggered by API Gateway (REST API, Lambda proxy integration).
Configuration: environment variable TOPIC_ARN (SNS Standard topic).
Dependencies: standard library + boto3 (already included in the Lambda runtime).
"""

import base64
import binascii
import json
import logging
import os
import re

import boto3

EVENT_NAME = "USER_REGISTERED"
# Fixed, ASCII-only subject. SNS only accepts ASCII, no line breaks, max 100
# characters, so user-provided data must never go into it.
SNS_SUBJECT = "USER_REGISTERED"

# Documented maximum lengths for the validated fields.
MAX_NAME_LENGTH = 100
MAX_EMAIL_LENGTH = 254  # practical limit for an email address (RFC 5321)

# Basic format check only (not exhaustive): local@domain.tld without spaces.
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

SUCCESS_MESSAGE = "User registered and notification sent"
INTERNAL_ERROR_MESSAGE = "Internal error"

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Created once per execution environment (reused across warm invocations).
# Tests replace this module attribute with a mock.
sns_client = boto3.client("sns")


class ValidationError(Exception):
    """Client error that maps to an HTTP 400 response."""


def _response(status_code, payload):
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json; charset=utf-8"},
        "body": json.dumps(payload, ensure_ascii=False),
    }


def _log(request_id, status_code, **extra):
    logger.info(
        json.dumps(
            {"requestId": request_id, "statusCode": status_code, **extra},
            ensure_ascii=False,
        )
    )


def _parse_body(event):
    raw = event.get("body")
    if raw is None or raw == "":
        raise ValidationError("Request body is required")
    try:
        if event.get("isBase64Encoded"):
            raw = base64.b64decode(raw, validate=True).decode("utf-8")
        data = json.loads(raw)
    except (binascii.Error, UnicodeDecodeError, ValueError, TypeError):
        raise ValidationError("Invalid JSON body") from None
    if not isinstance(data, dict):
        raise ValidationError("Body must be a JSON object")
    return data


def _validate(data):
    """Return (name, email) or raise ValidationError with the first error."""
    for field in ("name", "email"):
        if field not in data:
            raise ValidationError(f"Missing field: {field}")

    name, email = data["name"], data["email"]

    if not isinstance(name, str) or not name.strip():
        raise ValidationError("Invalid field: name")
    name = name.strip()
    if len(name) > MAX_NAME_LENGTH:
        raise ValidationError("Invalid field: name")

    if not isinstance(email, str):
        raise ValidationError("Invalid field: email")
    email = email.strip()
    if len(email) > MAX_EMAIL_LENGTH or not EMAIL_PATTERN.match(email):
        raise ValidationError("Invalid field: email")

    return name, email


def lambda_handler(event, context):
    request_id = getattr(context, "aws_request_id", None)

    try:
        name, email = _validate(_parse_body(event))
    except ValidationError as error:
        _log(request_id, 400, error=str(error))
        return _response(400, {"error": str(error)})

    topic_arn = os.environ.get("TOPIC_ARN")
    if not topic_arn:
        # Checked at invocation time (not import time) so the module always loads.
        _log(request_id, 500, error="TOPIC_ARN environment variable is not set")
        return _response(500, {"error": INTERNAL_ERROR_MESSAGE})

    message = json.dumps(
        {"event": EVENT_NAME, "name": name, "email": email},
        ensure_ascii=False,  # keep "López" readable in the email
    )

    try:
        result = sns_client.publish(
            TopicArn=topic_arn,
            Message=message,
            Subject=SNS_SUBJECT,
            MessageAttributes={
                "event": {"DataType": "String", "StringValue": EVENT_NAME}
            },
        )
    except Exception as error:  # noqa: BLE001 - never leak details to the client
        _log(
            request_id,
            500,
            error="SNS publish failed",
            errorType=type(error).__name__,
        )
        return _response(500, {"error": INTERNAL_ERROR_MESSAGE})

    _log(request_id, 200, messageId=result.get("MessageId"))
    return _response(200, {"message": SUCCESS_MESSAGE})
