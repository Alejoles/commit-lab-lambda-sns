"""Subscriber Lambda: consumes SNS messages and logs them (simulated processing).

Invoked asynchronously by SNS. Standard dependencies only.

Idempotency design note: SNS Standard topics deliver at least once, so the same
message can arrive more than once. This handler is idempotent by construction:
it only writes a log line and touches no disk, network or other service, so
processing a duplicate has no additional effect. A handler with side effects
(database writes, emails) should deduplicate on Sns.MessageId.
"""

import json
import logging

PROCESSED_MESSAGE = "evento procesado con éxito"

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def mask_email(email):
    """Mask an email as first character + '***' + domain (c***@email.com)."""
    if not isinstance(email, str) or "@" not in email:
        return "***"
    local, _, domain = email.partition("@")
    if not local or not domain:
        return "***"
    return f"{local[0]}***@{domain}"


def _process_record(record):
    sns = record.get("Sns", {})
    message_id = sns.get("MessageId")
    try:
        payload = json.loads(sns.get("Message"))
    except (TypeError, ValueError) as error:
        logger.error(
            json.dumps(
                {"message": "invalid SNS message: not JSON", "messageId": message_id},
                ensure_ascii=False,
            )
        )
        raise ValueError("SNS message is not valid JSON") from error

    if not isinstance(payload, dict):
        payload = {}

    logger.info(
        json.dumps(
            {
                "message": PROCESSED_MESSAGE,
                "event": payload.get("event"),
                "messageId": message_id,
                "email": mask_email(payload.get("email")),
            },
            ensure_ascii=False,
        )
    )


def lambda_handler(event, context):
    failures = []
    # Every record is processed; failures are raised at the end so one bad
    # record does not hide the rest and the error shows up in function metrics.
    for record in event.get("Records", []):
        try:
            _process_record(record)
        except ValueError as error:
            failures.append(error)

    if failures:
        raise ValueError(f"{len(failures)} record(s) failed processing")

    return {"status": "ok"}
