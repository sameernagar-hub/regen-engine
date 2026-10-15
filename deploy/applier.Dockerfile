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
RUN pip install --no-cache-dir playwright reportlab pypdf "mcp>=2.0" \
 && python -m playwright install --with-deps chromium \
 && apt-get update && apt-get install -y --no-install-recommends xvfb xauth tzdata \
 && rm -rf /var/lib/apt/lists/*
# own layer so the browser layer above stays cached: the read-only API service (control room fleet view) and the Postgres ledger use it
RUN pip install --no-cache-dir "fastapi>=0.142" "uvicorn>=0.54" "pydantic>=2.13" "psycopg[binary]>=3.3" "pytest>=8"
# repo-sync container: git for its own clone, pytest to check commits before they reach bot/sync
RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*
# the desk: the Xvfb screen served as a web page (noVNC) so the user can sign in to Workday tenants in that browser
RUN apt-get update && apt-get install -y --no-install-recommends x11vnc novnc python3-websockify websockify \
 && rm -rf /var/lib/apt/lists/* && ln -sf /usr/share/novnc/vnc.html /usr/share/novnc/index.html
COPY engine/ engine/
COPY apps/__init__.py apps/
COPY apps/api/ apps/api/
COPY profile.example/ profile.example/

# Least privilege: an unprivileged user; the browser profile lives in the container, not on the shared volume.
RUN useradd --create-home --uid 10001 regen && chmod -R a+rx /ms-playwright \
 && mkdir -p /app/site /repo /home/regen/desk-profile && chown regen /app/site /repo /home/regen/desk-profile  # repo-sync: feed build dir + its own clone (volume seeded from here)
USER regen

# Xvfb started directly (xvfb-run as PID 1 waits forever for a signal it never gets), then the engine owns PID 1.
ENV DISPLAY=:99
ENTRYPOINT ["sh", "-c", "rm -f /tmp/.X99-lock; Xvfb :99 -screen 0 1366x900x24 -nolisten tcp >/dev/null 2>&1 & sleep 1; exec python -m engine \"$@\"", "--"]
CMD ["worker"]
