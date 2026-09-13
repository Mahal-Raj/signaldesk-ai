FROM python:3.13-slim@sha256:bc497696e8e6fbd43c70fd7b39f3097b212704c0425de72201349ea435c9e911
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=8090
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY --chown=65532:65532 signaldesk signaldesk
COPY --chown=65532:65532 web web
USER 65532:65532
EXPOSE 8090
HEALTHCHECK --interval=30s --timeout=3s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8090/healthz')"
CMD ["python", "-m", "signaldesk.server"]

