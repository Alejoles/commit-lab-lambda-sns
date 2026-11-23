# Test environment that mirrors the AWS Lambda Python runtime.
# Override the version if the Lambda console offers a different one:
#   docker build --build-arg PYTHON_VERSION=3.14 -t lambda-sns-tests .
ARG PYTHON_VERSION=3.15
FROM public.ecr.aws/lambda/python:${PYTHON_VERSION}

WORKDIR /app

COPY requirements-dev.txt .
RUN pip install --no-cache-dir -r requirements-dev.txt

COPY . .

# The base image entrypoint starts the Lambda runtime interface client; replace it.
ENTRYPOINT ["python", "-m", "pytest"]
CMD ["-q"]
