# REGEN engine: always-on discovery in a container.
# Discovery (scan / watch / newgrad / boards) needs only the Python standard library, so the image stays small
# and has no browser. Applying stays on your machine (headed browser + your email codes).
#
#   docker compose -f deploy/docker-compose.yml up -d watcher
#
# Your profile/ and workspace/ are bind-mounted: all state stays in your local folders, nothing in the image.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PYTHONIOENCODING=utf-8 \
    REGEN_PROFILE=/data/profile REGEN_WORKSPACE=/data/workspace
WORKDIR /app
COPY engine/ engine/
COPY profile.example/ profile.example/

# Least privilege: run as an unprivileged user, no shell tools added.
RUN useradd --create-home --uid 10001 regen
USER regen

ENTRYPOINT ["python", "-m", "engine"]
CMD ["watch", "10"]
