FROM python:3.12.10-slim-bookworm@sha256:fd95fa221297a88e1cf49c55ec1828edd7c5a428187e67b5d1805692d11588db AS dependencies
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_NO_CACHE_DIR=1
COPY requirements-lock.linux.txt /tmp/requirements-lock.linux.txt
RUN python -m venv /opt/venv && /opt/venv/bin/pip install --require-hashes -r /tmp/requirements-lock.linux.txt

FROM python:3.12.10-slim-bookworm@sha256:fd95fa221297a88e1cf49c55ec1828edd7c5a428187e67b5d1805692d11588db
COPY --from=dependencies /opt/venv /opt/venv
ENV PATH=/opt/venv/bin:$PATH PYTHONPATH=/app/code/src:/app/code PYTHONHASHSEED=0 \
    OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 \
    MPLBACKEND=Agg PYTHONDONTWRITEBYTECODE=1
WORKDIR /app
COPY . /app
ENTRYPOINT ["python", "/app/reproduce.py"]
CMD ["--mode", "fast", "--output", "/tmp/reproduction"]
