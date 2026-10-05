# engine.memory: agentic memory and the profile knowledge graph

**Status: designed, stack runs in Docker (`deploy/docker-compose.yml`). The ingesters are next (v0.4).**

The memory layer is what turns a script into an engine. It keeps a **knowledge graph of you**
(your facts, skills, projects and preferences) linked to **everything the engine has seen and done**
(jobs, companies, questions, answers, resumes, outcomes). Agents read from it to decide and write to it to learn.

## Stores (one Docker stack, local by default)

| Store | Container | Holds |
|---|---|---|
| Graph | `neo4j:5` | Profile graph + job/company/skill/outcome graph (`schema.cypher`) |
| Vectors + events | `pgvector/pgvector:pg16` | JD and fact embeddings for similarity search; durable copy of `events.jsonl` |

## Three kinds of memory

| Kind | What it remembers | Example |
|---|---|---|
| **Semantic** (profile graph) | Who you are, as verified facts | `(:Fact {id:"u_pipelines"})-[:DEMONSTRATES]->(:Skill {name:"Kafka"})` |
| **Episodic** (event graph) | What happened, when, with proof | `(:Application)-[:FOR]->(:Job)`, `(:Application)-[:RESULTED_IN]->(:Outcome {type:"OA"})` |
| **Procedural** (site memory) | How to operate each ATS/site | Field label → preset key mappings that worked, failure signatures, step order |

## Planned interface

```python
from engine.memory import graph
graph.ingest_profile("profile/fact_bank.json")     # Fact/Skill/Project/Role nodes
graph.ingest_events("workspace/events.jsonl")      # Job/Application/Outcome nodes
graph.facts_for(job_id)                            # best facts for a JD (graph + vector)
graph.similar_jobs(job_id, k=10)                   # cluster reuse: which resume variant won here before
graph.answer_memory(question_label)                # previously approved answer for this question
```
