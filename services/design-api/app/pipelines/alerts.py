"""Alerts pipeline: facts per moment + languages + rules (gate) -> models draft a short alert and an answer to a
resident's question in every language, several tries -> a second model back-translates and the app checks length,
disclosure, numbers and watch terms against the facts -> you sign every draft: approve, edit or reject (gate) ->
report. Nothing is ever sent.

Generic: any facts and languages. A run can be started from a kit (kit.json).
"""

from __future__ import annotations

import csv
import io
import json
import re
import statistics
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, Field, ValidationError

from ..providers.base import ProviderError
from ..store import now
from .base import ActionError, Pipeline, StepSpec, Template, check, clean_text
from .video import _first_error

if TYPE_CHECKING:
    from ..engine import RunContext

KIT_FORMAT = "design-studio-alerts-kit"
PARTS = ("alert", "answer")
DEFAULT_INSTRUCTIONS = ("You draft short public messages for a public agency. Use only the facts you are given: add no "
                        "places, closures, shelters, times, numbers or instructions that are not in the facts, except "
                        "general safety advice. When the facts do not answer a resident's question, say so plainly and "
                        "say where to look. Reply with JSON only.")
CHECK_SYSTEM = ("You check public messages against the facts they were written from. Translate faithfully; do not fix "
                "or soften anything. Reply with JSON only.")
CHECK_KEYS = ("length", "disclosure", "numbers", "watch", "reviewer")
VERDICTS = ("approve", "edit", "reject")


class Language(BaseModel):
    code: str = Field(pattern=r"^[a-z]{2,3}(-[A-Za-z]{2,4})?$")
    name: str = Field(min_length=2, max_length=40)
    disclosure: str = Field(min_length=2, max_length=60)


class Moment(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    group: str = Field("", max_length=40)
    facts: str = Field(min_length=10, max_length=2000)
    question: str = Field("", max_length=300)
    note: str = Field("", max_length=400)


class AlertsBrief(BaseModel):
    brief: str = Field(min_length=10, max_length=4000)
    instructions: str = Field(DEFAULT_INSTRUCTIONS, min_length=10, max_length=2000)
    moments: list[Moment] = Field(min_length=1, max_length=12)
    languages: list[Language] = Field(min_length=1, max_length=6)
    models: list[str] = Field(min_length=1, max_length=4)
    tries: int = Field(1, ge=1, le=3)
    max_chars: int = Field(160, ge=60, le=600)
    watch_terms: list[str] = Field(default_factory=list, max_length=60)


# Numbers: every number in a message must come from the facts (rounding and 24-hour clock allowed)

_NUMBER = re.compile(r"(?<![\w.])(\d+(?:[.,]\d+)?)(?![\w])")
_CLOCK = re.compile(r"\b(\d{1,2})(?::(\d{2}))?\s*(a\.?m\.?|p\.?m\.?)", re.IGNORECASE)
_WORDS = {word: index + 1 for index, word in enumerate(
    ("one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven", "twelve"))}
_MONTHS = {name: index + 1 for index, name in enumerate(
    ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"))}


def numbers_in(text: str) -> list[float]:
    """Numbers as written: 43.1, 43,1 (decimal comma), 1,000 (thousands)."""
    values = []
    for raw in _NUMBER.findall(text):
        if "," in raw:
            whole, part = raw.split(",", 1)
            raw = whole + part if len(part) == 3 else f"{whole}.{part}"
        try:
            values.append(float(raw))
        except ValueError:
            continue
    return values


def allowed_numbers(facts: str) -> set[float]:
    """Numbers the facts state, rounded to 0 or 1 decimals, plus 24-hour clock hours and month numbers."""
    allowed: set[float] = set()
    for value in numbers_in(facts):
        allowed.update({value, round(value, 1), float(round(value))})
    for hour, _, half in _CLOCK.findall(facts):
        hour_value = int(hour) % 12 + (12 if half.lower().startswith("p") else 0)
        allowed.add(float(hour_value))
    for word in re.findall(r"[A-Za-z]+", facts):
        month = _MONTHS.get(word.lower()[:3])
        if month and len(word) >= 3:
            allowed.add(float(month))
        if word.lower() in _WORDS:
            allowed.add(float(_WORDS[word.lower()]))
    return allowed


def unknown_numbers(text: str, allowed: set[float]) -> list[str]:
    found = []
    for value in numbers_in(text):
        if not any(abs(value - known) < 1e-6 for known in allowed):
            found.append(f"{value:g}")
    return list(dict.fromkeys(found))


def watch_hits(text: str, facts: str, terms: list[str]) -> list[str]:
    """Watch terms (e.g. shelter, closed) in the message that the facts never mention."""
    low, known = text.lower(), facts.lower()
    return [term for term in terms if re.search(rf"\b{re.escape(term)}", low) and not re.search(rf"\b{re.escape(term)}", known)]


def compose_draft(moment: dict[str, Any], languages: list[dict[str, Any]], max_chars: int) -> str:
    lines = ["FACTS (the only facts you may use):", moment["facts"], "",
             f"1. ALERT: one text-message alert for residents, at most {max_chars} characters, in each language below. "
             "End each alert with the disclosure given for its language, word for word."]
    if moment["question"]:
        lines.append(f"2. ANSWER: a reply to this resident's question, at most 400 characters, in each language: "
                     f"\"{moment['question']}\"")
    lines.append("Languages:")
    lines += [f"- {lang['code']} = {lang['name']} (disclosure: \"{lang['disclosure']}\")" for lang in languages]
    keys = ", ".join(f'"{lang["code"]}": "..."' for lang in languages)
    shape = f'{{"alert": {{{keys}}}' + (f', "answer": {{{keys}}}}}' if moment["question"] else "}")
    lines.append(f"Reply as JSON: {shape}")
    return "\n".join(lines)


def compose_check(moment: dict[str, Any], languages: list[dict[str, Any]], messages: dict[str, dict[str, str]]) -> str:
    lines = ["FACTS:", moment["facts"], ""]
    if moment["question"]:
        lines += [f"RESIDENT'S QUESTION: {moment['question']}", ""]
    lines.append("MESSAGES:")
    for lang in languages:
        for part in PARTS:
            text = (messages.get(part) or {}).get(lang["code"])
            if text:
                lines.append(f"[{lang['code']} {part}] {text}")
    disclosures = ", ".join(f'"{lang["disclosure"]}"' for lang in languages)
    lines += ["", "For each message: translate it into English (copy English messages as they are), then list only real "
              "problems: a statement that contradicts the facts or changes their meaning; a specific detail the facts do "
              "not give (a place, road, closure, shelter, time, number, forecast or official order); or, in an answer, "
              "a claim to know something the facts do not say. Not problems: the required disclosure line "
              f"({disclosures}); general safety advice such as avoiding floodwater or not driving through water; "
              "pointing people to the phone lines in the facts; saying that something is not known. Do not list "
              "anything that agrees with the facts. An empty list if there are no real problems.",
              'Reply as JSON: {"back": {"<code>": {"alert": "...", "answer": "..."}}, '
              '"issues": {"<code>": [{"part": "alert" or "answer", "text": "..."}]}}']
    return "\n".join(lines)


def grade_message(part: str, lang: dict[str, Any], text: str, back: str, issues: list[str], facts: str,
                  allowed: set[float], watch_terms: list[str], max_chars: int) -> list[dict[str, str]]:
    """The checks for one message. They flag; a person decides."""
    checks = []
    if part == "alert":
        size = len(text)
        checks.append(check("length", f"{size} of {max_chars} characters", "ok" if size <= max_chars else "bad"))
        has = lang["disclosure"].lower() in text.lower()
        checks.append(check("disclosure", "Discloses AI" if has else f"No “{lang['disclosure']}” line",
                            "ok" if has else "bad"))
    extra = unknown_numbers(text, allowed)
    checks.append(check("numbers", "Every number is in the facts" if not extra else f"Numbers not in the facts: "
                        f"{', '.join(extra)}", "ok" if not extra else "bad"))
    hits = watch_hits(f"{text} {back}", facts, watch_terms)
    checks.append(check("watch", "No watch terms" if not hits else f"Not in the facts: {', '.join(hits)}",
                        "ok" if not hits else "bad", "searched in the message and its back-translation"))
    checks.append(check("reviewer", "Second model: no issues" if not issues else f"Second model: {'; '.join(issues)}",
                        "ok" if not issues else "warn", "a model's reading; you decide"))
    return checks


def build_report(moments: list[dict[str, Any]], languages: list[dict[str, Any]], models: list[str], tries: int,
                 drafts: list[dict[str, Any]]) -> dict[str, Any]:
    codes = [lang["code"] for lang in languages]
    counts = {"drafts": 0, "blocked": 0, "failed": 0, "expected": len(moments) * len(models) * tries}
    summary: dict[str, Any] = {}
    signed = {"approve": 0, "edit": 0, "reject": 0, "open": 0, "approved_flagged": 0}
    by_language = {code: {"messages": 0, "flagged": 0} for code in codes}
    for model in models:
        mine = [d for d in drafts if d["params"].get("model") == model]
        row = {"drafts": 0, "messages": 0, "flagged": 0, "checks": {key: 0 for key in CHECK_KEYS},
               "seconds": [], "consistent": None}
        for draft in mine:
            if draft["status"] in ("blocked", "failed"):
                counts[draft["status"]] += 1
                continue
            if draft["status"] != "ready":
                continue
            counts["drafts"] += 1
            row["drafts"] += 1
            if draft["metrics"].get("seconds") is not None:
                row["seconds"].append(float(draft["metrics"]["seconds"]))
            for code, parts in (draft["data"].get("grades") or {}).items():
                for part_checks in parts.values():
                    row["messages"] += 1
                    by_language.setdefault(code, {"messages": 0, "flagged": 0})["messages"] += 1
                    bad = [c for c in part_checks if c["state"] in ("bad", "warn")]
                    if bad:
                        row["flagged"] += 1
                        by_language[code]["flagged"] += 1
                    for item in bad:
                        row["checks"][item["key"]] = row["checks"].get(item["key"], 0) + 1
        row["median_seconds"] = round(statistics.median(row["seconds"]), 2) if row["seconds"] else None
        del row["seconds"]
        summary[model] = row
    for draft in drafts:
        if draft["status"] != "ready":
            continue
        verdict = (draft["data"].get("signoff") or {}).get("verdict")
        signed[verdict if verdict in VERDICTS else "open"] += 1
        if verdict == "approve" and draft["data"].get("flagged"):
            signed["approved_flagged"] += 1
    return {"counts": counts, "models": summary, "languages": by_language, "signed": signed}


class AlertsPipeline(Pipeline):
    key = "alerts"
    title = "Alerts"
    summary = "Turn facts into short public alerts and answers in several languages, check every message against " \
              "the facts and sign each one: approve, edit or reject. Nothing is ever sent."
    roles = ("text-draft", "text-judge")
    steps = (
        StepSpec("setup", "Facts, languages, rules", gate=True,
                 description="Check the facts for each moment, the languages and the rules before any model writes."),
        StepSpec("draft", "Draft the messages", role="text-draft",
                 description="One call per moment × model × try: an alert and an answer in every language, as JSON."),
        StepSpec("check", "Check every message", role="text-judge",
                 description="A second model back-translates; the app checks length, the AI disclosure, numbers and "
                             "watch terms against the facts. Checks flag; you decide."),
        StepSpec("desk", "Sign-off desk", gate=True,
                 description="Approve, edit or reject each draft. Nothing is sent; your decision is the record."),
        StepSpec("report", "Report", role="tool",
                 description="Flags by model, check and language, your sign-offs, CSV and JSON downloads."),
    )
    templates = (Template("blank", "Public alerts", "Facts in, alerts in several languages out, a person signs"),)

    def normalize_brief(self, brief: dict[str, Any]) -> dict[str, Any]:
        try:
            normalized = AlertsBrief.model_validate(brief).model_dump()
        except ValidationError as error:
            raise ActionError(_first_error(error)) from error
        codes = [lang["code"] for lang in normalized["languages"]]
        if len(set(codes)) != len(codes):
            raise ActionError("Each language needs its own code.")
        for moment in normalized["moments"]:
            moment["name"] = clean_text(moment["name"], 80)
            moment["group"] = clean_text(moment["group"], 40)
            moment["facts"] = "\n".join(line.strip() for line in moment["facts"].strip().splitlines() if line.strip())
            moment["question"] = clean_text(moment["question"], 300)
        normalized["watch_terms"] = list(dict.fromkeys(t.strip().lower() for t in normalized["watch_terms"] if t.strip()))
        normalized["models"] = list(dict.fromkeys(m.strip() for m in normalized["models"] if m.strip()))
        if not normalized["models"]:
            raise ActionError("Pick at least one model.")
        return normalized

    def estimate(self, brief: dict[str, Any]) -> dict[str, Any]:
        drafts = len(brief["moments"]) * len(brief["models"]) * brief["tries"]
        return {"text_calls": drafts * 2, "minutes": round(max(drafts * 2 * 12 / 4 / 60, 0.5), 1),
                "basis": "one drafting call and one checking call per moment × model × try, about 4 at a time"}

    # Helpers

    def drafts(self, ctx: RunContext) -> list[dict[str, Any]]:
        return [a for a in ctx.artifacts(step_key="draft", kind="draft") if a["status"] != "superseded"]

    def _moment(self, ctx: RunContext, index: int) -> dict[str, Any]:
        return ctx.brief["moments"][index]

    def _check_models(self, ctx: RunContext, models: list[str]) -> None:
        ctx.require("text-draft")
        if ctx.providers.fake:
            return
        allowed = ctx.settings.text_model_list
        missing = [model for model in models if model not in allowed]
        if missing:
            raise ActionError(f"Not a text model on this install: {', '.join(missing)}. "
                              f"Choose from: {', '.join(allowed)}.")

    def _report(self, ctx: RunContext) -> dict[str, Any]:
        brief = ctx.brief
        report = build_report(brief["moments"], brief["languages"], brief["models"], brief["tries"], self.drafts(ctx))
        ctx.set_step_data("check", report=report)
        return report

    # Execution

    async def start_step(self, ctx: RunContext, step: dict[str, Any]) -> None:
        key = step["key"]
        brief = ctx.brief
        if key == "setup":
            ctx.set_step_data("setup", system=brief["instructions"],
                              prompts=[compose_draft(m, brief["languages"], brief["max_chars"]) for m in brief["moments"]],
                              calls=self.estimate(brief)["text_calls"])
            ctx.event("info", f"{len(brief['moments'])} moments · {len(brief['languages'])} languages · "
                              f"{len(brief['models'])} model(s) × {brief['tries']} tries.", code="setup")
        elif key == "draft":
            self._check_models(ctx, brief["models"])
            made = {(a["params"].get("moment"), a["params"].get("model"), a["params"].get("try")) for a in self.drafts(ctx)}
            for attempt in range(1, brief["tries"] + 1):
                for index, moment in enumerate(brief["moments"]):
                    for model in brief["models"]:
                        if (index, model, attempt) in made:
                            continue
                        ctx.add_artifact("draft", "draft", grp=model, label=f"{moment['name']} · {model} · try {attempt}",
                                         role="text-draft", deployment=model,
                                         params={"model": model, "try": attempt, "moment": index})
        elif key == "check":
            ctx.require("text-judge")
            checked = {a["parent_id"] for a in ctx.artifacts(step_key="check", kind="check") if a["status"] != "superseded"}
            for draft in self.drafts(ctx):
                if draft["status"] == "ready" and draft["id"] not in checked:
                    ctx.add_artifact("check", "check", grp=draft["params"]["model"], label=f"Check · {draft['label']}",
                                     role="text-judge", parent_id=draft["id"], params=dict(draft["params"]))
        elif key == "desk":
            report = self._report(ctx)
            flagged = sum(row["flagged"] for row in report["models"].values())
            messages = sum(row["messages"] for row in report["models"].values())
            ctx.event("info", f"Checked {messages} messages: {flagged} flagged. Sign each draft.", code="checked")
        elif key == "report":
            if not ctx.artifacts(step_key="report"):
                ctx.add_artifact("report", "report", label="report (JSON)", role="tool")
                ctx.add_artifact("report", "table", label="messages (CSV)", role="tool")

    async def run_artifact(self, ctx: RunContext, artifact: dict[str, Any]) -> None:
        if artifact["kind"] == "draft":
            await self._run_draft(ctx, artifact)
        elif artifact["kind"] == "check":
            await self._run_check(ctx, artifact)
        elif artifact["kind"] in ("report", "table"):
            self._run_report(ctx, artifact)

    async def _complete(self, ctx: RunContext, role: str, deployment: str, system: str, user: str, *, purpose: str,
                        context: dict[str, Any]) -> Any:
        ctx.reserve(role)
        try:
            return await ctx.providers.text.complete(deployment, system, user, json_mode=True, max_tokens=4000,
                                                     purpose=purpose, context=context)
        except ProviderError:
            ctx.store.release("text", 1)
            raise

    async def _run_draft(self, ctx: RunContext, artifact: dict[str, Any]) -> None:
        brief = ctx.brief
        moment = self._moment(ctx, artifact["params"]["moment"])
        result = await self._complete(
            ctx, "text-draft", artifact["params"]["model"], brief["instructions"],
            compose_draft(moment, brief["languages"], brief["max_chars"]), purpose="alerts.draft",
            context={"moment": moment["name"], "facts": moment["facts"], "languages": brief["languages"],
                     "question": bool(moment["question"]),
                     "try": artifact["params"]["try"]})
        try:
            payload = result.json()
        except ProviderError:
            payload = {}
        messages: dict[str, dict[str, str]] = {}
        for part in PARTS:
            if part == "answer" and not moment["question"]:
                continue
            raw = payload.get(part) if isinstance(payload, dict) else None
            messages[part] = {lang["code"]: clean_text((raw or {}).get(lang["code"]) if isinstance(raw, dict) else "", 1200)
                              for lang in brief["languages"]}
        ctx.update_artifact(artifact["id"], status="ready", data={"raw": result.text[:6000], "messages": messages},
                            gen_seconds=result.seconds,
                            metrics={"seconds": result.seconds, "tokens": (result.usage or {}).get("total_tokens")})

    async def _run_check(self, ctx: RunContext, artifact: dict[str, Any]) -> None:
        brief = ctx.brief
        draft = ctx.artifact(artifact["parent_id"])
        moment = self._moment(ctx, draft["params"]["moment"])
        messages = draft["data"].get("messages") or {}
        result = await self._complete(
            ctx, "text-judge", ctx.deployment("text-judge"), CHECK_SYSTEM, compose_check(moment, brief["languages"], messages),
            purpose="alerts.check", context={"messages": messages, "languages": brief["languages"]})
        try:
            payload = result.json()
        except ProviderError:
            payload = {}
        payload = payload if isinstance(payload, dict) else {}
        back = payload.get("back") if isinstance(payload.get("back"), dict) else {}
        issues = payload.get("issues") if isinstance(payload.get("issues"), dict) else {}
        grades = self._grades(ctx, moment, messages, back, issues)
        ctx.update_artifact(artifact["id"], status="ready", data={"raw": result.text[:6000], "back": back},
                            gen_seconds=result.seconds, metrics={"seconds": result.seconds})
        flagged = any(c["state"] in ("bad", "warn") for parts in grades.values() for checks in parts.values() for c in checks)
        ctx.update_artifact(draft["id"], data={**draft["data"], "back": back, "grades": grades, "flagged": flagged},
                            checks=self._draft_checks(grades), quiet=True)

    def _grades(self, ctx: RunContext, moment: dict[str, Any], messages: dict[str, dict[str, str]],
                back: dict[str, Any], issues: dict[str, Any]) -> dict[str, dict[str, list[dict[str, str]]]]:
        brief = ctx.brief
        allowed = {"alert": allowed_numbers(moment["facts"]),
                   "answer": allowed_numbers(f"{moment['facts']}\n{moment['question']}")}
        grades: dict[str, dict[str, list[dict[str, str]]]] = {}
        for lang in brief["languages"]:
            code = lang["code"]
            raw_issues = issues.get(code) if isinstance(issues.get(code), list) else []
            for part, texts in messages.items():
                text = texts.get(code) or ""
                english = back.get(code) if isinstance(back.get(code), dict) else {}
                part_issues = [clean_text(item.get("text"), 200) for item in raw_issues
                               if isinstance(item, dict) and item.get("part") == part and item.get("text")]
                if not text:
                    grades.setdefault(code, {})[part] = [check("missing", "No message in this language", "bad")]
                    continue
                # A reply may repeat what the resident asked about (a place name) without inventing it.
                known = f"{moment['facts']}\n{moment['question']}" if part == "answer" else moment["facts"]
                grades.setdefault(code, {})[part] = grade_message(
                    part, lang, text, clean_text(english.get(part), 1200), part_issues, known, allowed[part],
                    brief["watch_terms"], brief["max_chars"])
        return grades

    @staticmethod
    def _draft_checks(grades: dict[str, dict[str, list[dict[str, str]]]]) -> list[dict[str, str]]:
        totals: dict[str, list[str]] = {}
        for code, parts in grades.items():
            for part, checks in parts.items():
                for item in checks:
                    if item["state"] in ("bad", "warn"):
                        totals.setdefault(item["key"], []).append(f"{code} {part}")
        if not totals:
            return [check("clean", "Every message passed every check", "ok")]
        return [check(key, f"{key}: {', '.join(where)}", "warn" if key == "reviewer" else "bad") for key, where in totals.items()]

    def _run_report(self, ctx: RunContext, artifact: dict[str, Any]) -> None:
        brief = ctx.brief
        report = self._report(ctx)
        drafts = self.drafts(ctx)
        if artifact["kind"] == "table":
            out = io.StringIO()
            writer = csv.writer(out)
            writer.writerow(["moment", "model", "try", "language", "part", "message", "back-translation", "flags",
                             "signed", "edited text", "seconds"])
            for draft in drafts:
                if draft["status"] != "ready":
                    continue
                moment = self._moment(ctx, draft["params"]["moment"])
                signoff = draft["data"].get("signoff") or {}
                for code, parts in self._rows(draft).items():
                    for part, text in parts.items():
                        flags = [c["label"] for c in ((draft["data"].get("grades") or {}).get(code) or {}).get(part, [])
                                 if c["state"] in ("bad", "warn")]
                        edited = ((signoff.get("edits") or {}).get(code) or {}).get(part, "")
                        back = ((draft["data"].get("back") or {}).get(code) or {})
                        writer.writerow([moment["name"], draft["params"].get("model"), draft["params"].get("try"), code,
                                         part, text, back.get(part, "") if isinstance(back, dict) else "",
                                         " | ".join(flags), signoff.get("verdict", ""), edited, draft["metrics"].get("seconds")])
            info = ctx.save_media(out.getvalue().encode(), "text/csv; charset=utf-8")
            ctx.update_artifact(artifact["id"], status="ready", media_sha=info.sha, media_type="text/csv",
                                metrics={"rows": out.getvalue().count("\n") - 1})
            return
        document = {
            "brief": brief["brief"], "instructions": brief["instructions"], "moments": brief["moments"],
            "languages": brief["languages"], "models": brief["models"], "tries": brief["tries"],
            "max_chars": brief["max_chars"], "watch_terms": brief["watch_terms"], "judge": ctx.deployment("text-judge"),
            "report": report,
            "drafts": [{"moment": d["params"]["moment"], "model": d["params"]["model"], "try": d["params"]["try"],
                        "messages": d["data"].get("messages"), "back": d["data"].get("back"),
                        "grades": d["data"].get("grades"), "signoff": d["data"].get("signoff"),
                        "seconds": d["metrics"].get("seconds")} for d in drafts if d["status"] == "ready"],
            "made": now(),
        }
        info = ctx.save_media(json.dumps(document, ensure_ascii=False, indent=1).encode(), "application/json")
        signed = report["signed"]
        flagged = sum(row["flagged"] for row in report["models"].values())
        messages = sum(row["messages"] for row in report["models"].values())
        checks = [
            check("drafts", f"{report['counts']['drafts']} of {report['counts']['expected']} drafts recorded",
                  "ok" if report["counts"]["drafts"] == report["counts"]["expected"] else "warn",
                  "blocked or failed calls are listed in the event log"),
            check("flagged", f"{flagged} of {messages} messages flagged", "warn" if flagged else "ok",
                  "length, AI disclosure, numbers, watch terms, second model"),
            check("signed", f"Signed: {signed['approve']} approved · {signed['edit']} edited · {signed['reject']} rejected"
                  f" · {signed['open']} not signed", "ok" if not signed["open"] else "warn", "nothing is ever sent"),
            check("approved_flagged", f"{signed['approved_flagged']} approved as written despite a flag",
                  "bad" if signed["approved_flagged"] else "ok", "a person approved a message the checks flagged"),
        ]
        ctx.update_artifact(artifact["id"], status="ready", media_sha=info.sha, media_type="application/json",
                            checks=checks, metrics={"drafts": report["counts"]["drafts"]})
        ctx.event("success", "Report ready: flags, sign-offs and downloads.", code="finished")

    @staticmethod
    def _rows(draft: dict[str, Any]) -> dict[str, dict[str, str]]:
        """Messages by language, then part."""
        rows: dict[str, dict[str, str]] = {}
        for part, texts in (draft["data"].get("messages") or {}).items():
            for code, text in texts.items():
                rows.setdefault(code, {})[part] = text
        return rows

    def step_settled(self, ctx: RunContext, step: dict[str, Any]) -> str:
        if step["key"] in ("draft", "check"):
            failed = [a for a in ctx.artifacts(step_key=step["key"]) if a["status"] == "failed"]
            return "failed" if failed else "done"
        return super().step_settled(ctx, step)

    # Gates and actions

    async def action(self, ctx: RunContext, name: str, payload: dict[str, Any]) -> dict[str, Any] | None:
        if name == "sign":
            if ctx.step("desk")["status"] != "waiting":
                raise ActionError("The sign-off desk is not open.")
            draft = ctx.artifact(str(payload.get("draft_id") or ""))
            if draft["kind"] != "draft" or draft["status"] != "ready":
                raise ActionError("Pick one of the run's drafts.")
            verdict = str(payload.get("verdict") or "")
            if verdict not in VERDICTS:
                raise ActionError("Verdict must be approve, edit or reject.")
            edits: dict[str, dict[str, str]] = {}
            if verdict == "edit":
                raw = payload.get("edits") if isinstance(payload.get("edits"), dict) else {}
                rows = self._rows(draft)
                for code, parts in raw.items():
                    if code not in rows or not isinstance(parts, dict):
                        continue
                    for part, text in parts.items():
                        text = clean_text(text, 1200)
                        if part in rows[code] and text and text != rows[code][part]:
                            edits.setdefault(code, {})[part] = text
                if not edits:
                    raise ActionError("Change at least one message, or approve it as written.")
            note = clean_text(payload.get("note"), 500)
            signoff = {"verdict": verdict, "edits": edits, "note": note, "at": now()}
            ctx.update_artifact(draft["id"], data={**draft["data"], "signoff": signoff}, quiet=True)
            ctx.store.add_decision(ctx.run_id, "sign", artifact_id=draft["id"], step_key="desk", verdict=verdict,
                                   note=note or None)
            self._report(ctx)
            ctx.event("info", f"You signed {draft['label']}: {verdict}.", code="signed")
            return None
        return await super().action(ctx, name, payload)

    def summarize(self, run: dict[str, Any], artifacts: list[dict[str, Any]]) -> dict[str, Any]:
        drafts = [a for a in artifacts if a["kind"] == "draft" and a["status"] == "ready"]
        flagged = sum(1 for a in drafts if a["data"].get("flagged"))
        signed = sum(1 for a in drafts if a["data"].get("signoff"))
        outputs = [f"{len(run['brief'].get('moments', []))} moments", f"{len(drafts)} drafts"]
        if drafts:
            outputs.append(f"{flagged} flagged")
            outputs.append(f"{signed} signed")
        return {"outputs": " · ".join(outputs), "drafts": len(drafts),
                "languages": [lang["code"] for lang in run["brief"].get("languages", [])],
                "models": sorted(run["brief"].get("models", []))}
