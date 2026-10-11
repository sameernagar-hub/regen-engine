# REGEN applier: one engine worker = one headed Chromium (on a virtual display) per container.
# Scale-out: N containers share the workspace volume and claim batches from workspace/batches/inbox (atomic rename).
#
#   docker compose -f deploy/appliers.compose.yml up -d --build --scale applier=4
#   REGEN_APPLIERS=docker python -m engine run --loop 10 ...   (the host pipeline dispatches; workers apply)
#
# Headed, not headless: some ATSs bot-flag headless browsers. Xvfb gives the headed browser a screen in the container.
# The profile/ and workspace/ folders are bind-mounted; the image holds code only, never personal data.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PYTHONIOENCODING=utf-8 \
    REGEN_PROFILE=/data/profile REGEN_WORKSPACE=/data/workspace \
    REGEN_PW_PROFILE=/home/regen/pw-profile PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    TZ=America/Los_Angeles
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir playwright reportlab pypdf \
 && python -m playwright install --with-deps chromium \
 && apt-get update && apt-get install -y --no-install-recommends xvfb xauth tzdata \
 && rm -rf /var/lib/apt/lists/*
COPY engine/ engine/
COPY profile.example/ profile.example/

# Least privilege: an unprivileged user; the browser profile lives in the container, not on the shared volume.
RUN useradd --create-home --uid 10001 regen && chmod -R a+rx /ms-playwright
USER regen

# Xvfb started directly (xvfb-run as PID 1 waits forever for a signal it never gets), then the engine owns PID 1.
ENV DISPLAY=:99
ENTRYPOINT ["sh", "-c", "Xvfb :99 -screen 0 1366x900x24 -nolisten tcp >/dev/null 2>&1 & sleep 1; exec python -m engine \"$@\"", "--"]
CMD ["worker"]
