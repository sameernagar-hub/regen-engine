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


class Narration(BaseModel):
    """An event as one plain-English sentence (engine.live.server.narrate)."""
    id: int
    ts: Optional[str] = None
    stage: Stage
    tone: Tone
    text: str
    verified: Optional[bool] = None


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
