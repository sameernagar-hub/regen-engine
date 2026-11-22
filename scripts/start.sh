#!/usr/bin/env sh
# START: bring the bank stack up and wait until every service the assistant's MCPs depend on answers.
#   regen-bank   = HTTP MCP inside the stack (127.0.0.1:8790/mcp)
#   regen-engine = stdio MCP (scripts/mcp_stdio.py) that runs inside deploy-pipeline-1 once it is up
# A Claude session opened before the stack was up sees regen-bank as "failed to connect": after this prints
# "MCP ready", call any regen-bank tool (e.g. fleet_status) and the client reconnects.
# Then: engine gear N, cap level, keywords on|off (ask the user), shadow mode.
set -e
cd "$(dirname "$0")/.."
REGEN_MCP_WRITE=1 REGEN_DAYS=30 REGEN_MAX_PER_DAY=150 REGEN_TABS=4 REGEN_ASHBY_PER_PASS="${REGEN_ASHBY_PER_PASS:-5}" \
REGEN_LOOP_MIN=3 REGEN_SOURCES_EVERY=3 REGEN_MAX=150 \
  docker compose -f deploy/bank.compose.yml up -d --scale applier=1

wait_for() {  # name url
  i=0
  until curl -s -o /dev/null -m 3 "$2"; do
    i=$((i + 1)); [ "$i" -ge 60 ] && { echo "$1 NOT ready after 120 s ($2)"; return 1; }
    sleep 2
  done
  echo "$1 ready"
}
wait_for "api" "http://127.0.0.1:8787/api/control/fleet"
wait_for "regen-bank MCP" "http://127.0.0.1:8790/mcp"
docker inspect -f '{{.State.Running}}' deploy-pipeline-1 | grep -q true && echo "regen-engine MCP target (deploy-pipeline-1) ready"
echo "MCP ready"
