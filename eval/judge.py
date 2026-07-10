"""Judge phase: the LLM half of the grade, via headless `claude -p` (spec #11).

Judge model and rubrics are PINNED here and never change in the same run as a
system change (run-eval doctrine: you'd be moving the ruler with the object).
The judge (Opus) is stronger than the system under test (Sonnet) to avoid
self-preference bias, and runs through the local Claude Code CLI — zero
marginal cost on the subscription. Dependency: a logged-in `claude` CLI;
without it, `eval judge` fails with a clear message. Judge calls are not
Langfuse-traced (scores are pushed programmatically, #16).
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path

from eval.golden import Category, GoldenQuestion, GoldenSet
from eval.report import AnswerRecord

JUDGE_MODEL = "claude-opus-4-8"

RUBRICS: dict[Category, str] = {
    Category.SINGLE_HOP: (
        "PASS only if the answer states every expected fact and is grounded in the cited "
        "sources (no fact beyond what citations could support). Wrong, missing, or "
        "unsupported facts FAIL. hallucinated=true if the answer asserts lore facts that "
        "contradict or go beyond the expected facts."
    ),
    Category.MULTI_HOP: (
        "PASS only if the answer states every expected fact AND connects them correctly "
        "(the multi-hop chain is explicit or clearly implied). A right final fact reached "
        "by a wrong or missing chain FAILS. hallucinated=true if any link in the chain is "
        "invented rather than grounded."
    ),
    Category.CONTINUITY_CONFLICT: (
        "PASS only if the answer handles continuity as the expected behavior describes — "
        "distinguishing canon from Legends instead of blending them, and attributing each "
        "fact to the right continuity. Blended or misattributed continuities FAIL. "
        "hallucinated=true if a fact is asserted in a continuity where it does not hold."
    ),
    Category.UNANSWERABLE: (
        "PASS only if the answer clearly refuses — says the subject is not in its corpus "
        "or that it does not know — without asserting lore facts about the subject. Any "
        "substantive answer about the subject FAILS with hallucinated=true, even if hedged."
    ),
}

_PROMPT = """\
You are the Judge for a Star Wars lore QA eval. Grade ONE answer against the rubric.
Judge only what is written; do not use your own lore knowledge to fill gaps.

Category: {category}
Rubric: {rubric}

Question: {question}
Expected facts: {expected_facts}
Expected continuity behavior: {expected_continuity}

Answer under judgment:
{answer}

Titles cited by the answer: {citations}

Return ONLY a JSON object, no prose, no code fences:
{{"passed": <bool>, "hallucinated": <bool>, "reasoning": "<one sentence>"}}"""


class JudgeUnavailableError(Exception):
    """The claude CLI is missing, logged out, or returned an error envelope."""


@dataclass(frozen=True)
class Verdict:
    """The Judge's structured verdict on one answer."""

    passed: bool
    hallucinated: bool
    reasoning: str

    @classmethod
    def parse(cls, text: str) -> Verdict:
        """Parse the model's JSON (tolerating code fences); anything else is a hard error."""
        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`").removeprefix("json").strip()
        try:
            data = json.loads(cleaned)
        except ValueError:
            raise ValueError(f"unparseable verdict: {text[:200]!r}") from None
        if not isinstance(data, dict):
            raise ValueError(f"verdict must be a JSON object: {cleaned[:200]!r}")
        if not isinstance(data.get("passed"), bool) or not isinstance(data.get("hallucinated"), bool):
            raise ValueError(f"verdict fields must be booleans: {cleaned[:200]!r}")
        return cls(passed=data["passed"], hallucinated=data["hallucinated"], reasoning=str(data.get("reasoning", "")))


class ClaudeJudge:
    """One judgment per call through `claude -p` (owned CLI transport, model pinned).

    `env` is injected by the composition root (ADR-0004: environment read there
    only). It must NOT contain ANTHROPIC_API_KEY: the key would bill the API per
    token instead of the subscription (spec #11: judging costs nothing per run)
    and overrides the claude.ai login.
    """

    def __init__(self, env: dict[str, str]):
        self._model = JUDGE_MODEL
        self._env = env

    def judge(self, question: GoldenQuestion, record: AnswerRecord) -> Verdict:
        prompt = _PROMPT.format(
            category=question.category,
            rubric=RUBRICS[question.category],
            question=question.question,
            expected_facts=", ".join(question.expected_facts) or "(none — unanswerable)",
            expected_continuity=question.expected_continuity,
            answer=record.answer,
            citations=", ".join(c.title for c in record.citations) or "(none)",
        )
        try:
            proc = subprocess.run(
                ["claude", "-p", prompt, "--output-format", "json", "--model", self._model],
                capture_output=True,
                text=True,
                timeout=300,
                env=self._env,
            )
        except FileNotFoundError:
            raise JudgeUnavailableError(
                "`claude` CLI not found — the Judge runs through Claude Code; install it and run `claude login`"
            ) from None
        except subprocess.TimeoutExpired:
            raise JudgeUnavailableError("claude CLI timed out after 300s") from None
        if proc.returncode != 0:
            raise JudgeUnavailableError(f"claude CLI failed (logged out?): {proc.stderr.strip()[:300]}")
        try:
            envelope = json.loads(proc.stdout)
        except ValueError:
            raise JudgeUnavailableError(f"claude CLI printed non-JSON: {proc.stdout[:300]!r}") from None
        if envelope.get("is_error"):
            raise JudgeUnavailableError(f"claude CLI returned an error: {envelope.get('result', '')[:300]}")
        return Verdict.parse(envelope["result"])


class JudgeRunner:
    """Judges every persisted answer in a run dir; existing verdicts are kept (re-judge = delete them)."""

    def __init__(self, judge: ClaudeJudge):
        self._judge = judge

    def run(self, run_dir: Path, golden: GoldenSet) -> int:
        manifest_path = run_dir / "run.json"
        if not manifest_path.exists():
            raise ValueError(f"{run_dir}: no manifest — the run is incomplete and cannot be judged")
        manifest = json.loads(manifest_path.read_text())
        by_id = {q.id: q for q in golden.questions}
        judged = 0
        pairs = [(s, q) for s in manifest["strategies"] for q in manifest["questions"]]
        for i, (strategy, qid) in enumerate(pairs, 1):
            verdict_path = run_dir / strategy / f"{qid}.verdict.json"
            if verdict_path.exists():
                print(f"[{i}/{len(pairs)}] {strategy}/{qid}: verdict exists, kept")
                continue
            record = AnswerRecord.from_json(json.loads((run_dir / strategy / f"{qid}.json").read_text()))
            verdict = self._judge.judge(by_id[qid], record)
            verdict_path.write_text(json.dumps({**asdict(verdict), "judge_model": JUDGE_MODEL}, indent=2))
            judged += 1
            flag = "  ⚠ HALLUCINATED" if verdict.hallucinated else ""
            print(f"[{i}/{len(pairs)}] {strategy}/{qid}: {'PASS' if verdict.passed else 'FAIL'}{flag}")
        return judged
