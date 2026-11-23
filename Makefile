PYTHON_VERSION ?= 3.15
IMAGE ?= lambda-sns-tests

.PHONY: test test-local build

build:
	docker build --build-arg PYTHON_VERSION=$(PYTHON_VERSION) -t $(IMAGE) .

# Run the test suite inside the Lambda-like image.
test: build
	docker run --rm $(IMAGE)

# Run the test suite with the local Python (needs requirements-dev.txt installed).
test-local:
	python3 -m pytest -q
