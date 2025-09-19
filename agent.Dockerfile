# Sprint 18: The Secure Sandbox
# This Dockerfile is optimized for a minimal build context.

# 1. Base Image
FROM python:3.11-slim
WORKDIR /app

# 2. Dependency Management
# This layer is cached as long as the lock file doesn't change.
RUN pip install poetry
COPY pyproject.toml poetry.lock ./
RUN poetry install --no-root

# 3. Test Runner Installation
RUN pip install pytest

# 4. Copy the application code from the workspace context
COPY . .

# 5. The CMD for the container
CMD ["pytest"]

