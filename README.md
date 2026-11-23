# Lambda + SNS notifications

A small pub/sub system on AWS: `POST /register` validates a user, publishes a `USER_REGISTERED` event to an SNS topic, and SNS fans it out to a subscriber Lambda and an email subscription.

## Architecture

```text
Client ── POST /register ──► API Gateway (stage dev) ──► Publisher Lambda
                                                              │ publish
                                                              ▼
                                                    SNS Topic "user-events"
                                                      │                 │
                                                      ▼                 ▼
                                           Subscriber Lambda     Email subscription
                                           (CloudWatch log)
```

## API contract

`POST /register`

Request:

```json
{"name": "Carlos López", "email": "carlos@email.com"}
```

Responses:

| Case | Status | Body |
| --- | --- | --- |
| Success | 200 | `{"message": "User registered and notification sent"}` |
| Missing field, invalid JSON, invalid types or email | 400 | `{"error": "<message>"}` (e.g. `Missing field: email`) |
| Publish failure or missing configuration | 500 | `{"error": "Internal error"}` |

Message published to SNS (with message attribute `event` = `USER_REGISTERED`):

```json
{"event": "USER_REGISTERED", "name": "Carlos López", "email": "carlos@email.com"}
```

## Repository layout

```text
publisher/lambda_function.py    # POST /register -> SNS publish
subscriber/lambda_function.py   # processes the SNS message (masked log)
tests/                          # pytest, no network or AWS needed
events/                         # sample events for the Lambda console Test tab
scripts/smoke.sh                # curl checks against the deployed API
scripts/make-local-events.sh    # fills event placeholders into git-ignored events/local/
Dockerfile, Makefile            # test environment mirroring the Lambda runtime
```

## Running the tests

With Docker (image based on the official Lambda Python runtime, default 3.15):

```bash
make test
make test PYTHON_VERSION=3.14   # if the Lambda console offers another version
```

Without Docker:

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
make test-local
```

`boto3` ships with the Lambda runtime, so it is a dev-only dependency and is not packaged.

## Deployment

Manual, through the AWS console, following the lab guide. Placeholders used throughout the repo: `<ACCOUNT_ID>`, `<REGION>`, `<API_ID>`. Real values never go in the repository.

Publisher environment variable: `TOPIC_ARN`. Recommended settings: 128 MB memory, 10 s timeout.

## Design decisions

- **Publisher Lambda instead of a direct API Gateway → SNS integration.** The Lambda validates the input, returns meaningful 400 errors, and builds the message and attributes in code that can be unit tested.
- **REST API with Lambda proxy integration.** The function receives the raw request and controls the status code and body.
- **Standard topic.** Email subscriptions and direct Lambda delivery are not supported by FIFO topics.
- **`event` message attribute.** SNS filter policies match on message attributes, not on the body, so the publisher sets `event` explicitly. This enables per-subscription filtering without changing the publisher.
- **Masked email in logs.** The subscriber logs `c***@email.com`; the publisher never logs the email.
- **Generic 500 responses.** Internal details stay in CloudWatch, never in the HTTP response.
- **Idempotency.** SNS Standard delivers at least once. The subscriber only logs, so reprocessing a message has no side effects.
- **Fixed ASCII `Subject`.** SNS only accepts ASCII subjects up to 100 characters, so user data is never placed in it.

## Experiments

Procedure and expected outcome. Screenshots live outside the repository to avoid leaking account data.

| Experiment | Procedure | Expected outcome |
| --- | --- | --- |
| A. Filter policy | Set `{"event": ["USER_REGISTERED"]}` on the Lambda subscription, then publish from the SNS console with attribute `event=USER_DELETED` and later `event=USER_REGISTERED` | First message reaches only the email subscription; the second reaches both |
| B. Decoupling | Delete the Lambda subscription and call `POST /register` | API still returns 200 and the email still arrives |

The Lambda subscription and its filter policy are restored afterwards.

## Limitations and future work

- SQS queue as a second subscriber and a dead-letter queue.
- Infrastructure as code (SAM or Terraform) and CI/CD with OIDC.

## Cleanup

Delete in this order, after submitting: API Gateway API → SNS topic → both Lambda functions → their CloudWatch log groups → the execution role (only if you created it). Check each console for leftovers.
