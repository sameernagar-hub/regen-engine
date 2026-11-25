#!/usr/bin/env sh
# IGNITION (11-24): the whole start in one command. Brings the bank stack up (scripts/start.sh), then runs
# `engine ignite` inside the pipeline as the engine user: gear (<= 3), Role Keywords, cap level, Shadow mode, every
# orchestrator agent resumed. Args pass through, e.g. `sh scripts/ignite.sh --keywords off --cap 0`.
# Defaults are the user's usual run: gear 3, keywords on, cap 4 (150/day), Shadow autopilot.
set -e
cd "$(dirname "$0")/.."
sh scripts/start.sh
MSYS_NO_PATHCONV=1 docker exec -u 10001 deploy-pipeline-1 python -m engine ignite "$@"
echo "IGNITION done. Watch agent asks with: docker exec deploy-pipeline-1 python -m engine cord watch"
