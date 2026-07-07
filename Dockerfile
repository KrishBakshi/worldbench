# WorldBench container image.
#
# Builds the benchmark package with its GEOS/Shapely system dependency and
# exposes the `worldbench` CLI as the default entrypoint.

FROM python:3.12-slim

# System dependencies: GEOS is required by Shapely; build-essential covers any
# packages that need to compile wheels.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libgeos-dev \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install dependencies first (better layer caching), then the source.
COPY pyproject.toml README.md ./
COPY benchmark ./benchmark
COPY prompts ./prompts

RUN pip install --upgrade pip && pip install -e '.[dev]'

# Generated artifacts are written here; mount them as volumes to persist.
RUN mkdir -p outputs reports

# Default to showing the CLI help; override with e.g.
#   docker run --rm worldbench worldbench list
ENTRYPOINT ["worldbench"]
CMD ["--help"]
