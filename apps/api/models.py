"""Typed records for the REGEN API. They mirror what the engine writes to the append-only event log; the API never
invents fields. The TypeScript client in apps/web is generated from these via OpenAPI."""
from typing import Literal, Optional

from pydantic import BaseModel, Field

Stage = Literal["listen", "judge", "write", "apply", "hear"]
Tone = Literal["calm", "quiet", "win", "you", "alarm"]


class Event(BaseModel):
    """One line of workspace/events.jsonl, with the fields every consumer relies on lifted out."""
    id: int = Field(description="Position in the log (1-based); stable because the log is append-only")
    ts: str
    kind: str
    job: Optional[str] = None
    status: Optional[str] = None
    data: dict = Field(default_factory=dict, description="The full original event")


LiveKind = Literal["discovered", "gate.skip", "resume", "apply.start", "submitted", "parked", "apply.fail",
                   "shadow.answer", "shadow.abstain", "outcome"]
SignalKind = Literal["gear", "keywords", "cap", "targeting", "shadow.mode", "human.check", "problem", "problem.clear",
                     "outreach.sent"]
By = Literal["engine", "shadow", "desk", "you", "user", "operator", "api"]


class Narration(BaseModel):
    """An event as one plain-English sentence (engine.live.server.narrate). ALIVE Phase 0 adds the typed fields
    (all optional, so older clients keep working): kind, job (the posting URL: one chip followed across stages),
    company (never sent on the public site), by, detail (skip reason / parked question, shortened), conf (Shadow's
    confidence on shadow.answer), jobs (the postings an apply.start batch or an outcome covers)."""
    id: int
    ts: Optional[str] = None
    stage: Stage
    tone: Tone
    text: str
    verified: Optional[bool] = None
    kind: Optional[LiveKind] = None
    job: Optional[str] = None
    company: Optional[str] = None
    by: Optional[str] = None
    detail: Optional[str] = None
    conf: Optional[float] = None
    jobs: Optional[list[str]] = None


class Signal(BaseModel):
    """A control-plane event with no pipeline stage (engine.live.server.signal): gear, cap dial, Role Keywords,
    targeting, Shadow mode, desk checks, warning lights, outreach marked sent. SSE event type `signal`."""
    id: int
    ts: Optional[str] = None
    kind: SignalKind
    text: str
    by: Optional[str] = None
    detail: Optional[str] = None


class Application(BaseModel):
    """Latest state of one job (later events win)."""
    job: str
    company: str
    role: str
    status: str
    ts: str
    url: Optional[str] = None
    lane: Optional[str] = None
    proof: Optional[str] = Field(None, description="Proof screenshot path, only when the file exists on disk")
    resume: Optional[str] = None
    facts: list[str] = Field(default_factory=list, description="Fact Bank ids the resume was built from")
    answers: list[tuple[str, Optional[str]]] = Field(default_factory=list, description="Question -> answer, as submitted")
    detail: Optional[str] = None


class Outcome(BaseModel):
    ts: str
    company: Optional[str] = None
    outcome: str
    subject: Optional[str] = None
    jobs: list[str] = Field(default_factory=list)


class HumanItem(BaseModel):
    """Something only the user can do (each job's latest status, never stale history)."""
    job: str
    status: str
    text: str
    url: Optional[str] = None
    resume: Optional[str] = None
    missing: list[str] = Field(default_factory=list, description="Questions the engine could not answer (answer them via POST /api/answers)")


class AnswerIn(BaseModel):
    """One answer typed in the web app for a question the engine could not answer."""
    job: str
    question: str = Field(max_length=500)
    answer: str = Field(max_length=2000)


class AnswerOut(BaseModel):
    pattern: str
    answer: str
    source: str


class Drafted(BaseModel):
    """An answer the engine drafted from Fact Bank entries and sent without waiting (for review)."""
    ts: str
    job: Optional[str] = None
    status: str
    question: str
    answer: str
    facts: list[str] = Field(default_factory=list)


class Snapshot(BaseModel):
    verified: int
    verified_today: int
    waiting: int
    boards: int
    last_poll: Optional[float] = None
    by_lane: dict[str, int] = Field(default_factory=dict)
    outcomes: dict[str, int] = Field(default_factory=dict)
    backend: Literal["postgres", "jsonl"]
