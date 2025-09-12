# ---- Builder Stage ----
# This stage installs dependencies into a virtual environment.
FROM python:3.11-slim as builder

# Set the working directory
WORKDIR /app

# Install poetry
RUN pip install poetry

# Copy only the files needed to install dependencies
# This leverages Docker's layer caching.
COPY pyproject.toml poetry.lock ./

# Install dependencies into a virtual environment within the project
RUN poetry config virtualenvs.in-project true && \
    poetry install --no-root --no-dev

# ---- Runner Stage ----
# This stage copies the built environment and source code into a clean image.
FROM python:3.11-slim

# Set the working directory
WORKDIR /app

# Copy the virtual environment from the builder stage
COPY --from=builder /app/.venv ./.venv

# Set the PATH to include the virtual environment's binaries
ENV PATH="/app/.venv/bin:$PATH"

# Copy the application source code
COPY ./src ./src

# Expose the port the app runs on
EXPOSE 5000

# Set the command to run the application
# We use gunicorn for a production-ready server in a container.
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "src.codex_veritas.app.main:app"]
