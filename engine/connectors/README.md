# engine.connectors: use the engine from anything

**Status: planned (v0.5).** The engine is a library first, so every connector is a thin layer over the same stages.

| Connector | For | Shape |
|---|---|---|
| **CLI** (shipped) | You, cron, CI | `python -m engine scan / batch / apply / status` |
| **Python library** (shipped) | Building your own app | `from engine.discovery.greenhouse import scan` |
| **MCP server** | Claude Desktop / Claude Code / any MCP client | tools: `discover_jobs`, `tailor_resume`, `apply`, `queue_status`, `memory_query`, `engine_control` |
| **REST + webhooks** | Web dashboards, other products | `POST /jobs/scan`, `POST /applications`, `GET /events`; webhook on `application.submitted`, `outcome.received` |
| **Plugin packaging** | Claude Code plugin / skill | Bundles the MCP server and skills for one-command install |
