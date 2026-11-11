"""Agenda: the agent's own running todo list, always in context.

Open items live in $HERMES_HOME/agenda/open.json. Ticked or dropped items move to
$HERMES_HOME/agenda/archive.jsonl (append-only, searchable) so nothing is lost.
Personal settings (your name) come from config.yaml: plugins.entries.agenda.settings.
A pre_llm_call hook shows the open list; one tool lets the model add, tick,
drop, snooze, edit and search. Reminders reuse the `wake` CLI.
"""
import hashlib, json, os, re, secrets, shutil, subprocess, time
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

HOME = Path(os.environ.get("HERMES_HOME") or os.path.expanduser("~/.hermes"))
DIR = HOME / "agenda"
OPEN, ARCHIVE, STATE = DIR / "open.json", DIR / "archive.jsonl", DIR / "seen.json"
SOFT_CAP = 15
TEXT_MAX, CONTEXT_MAX = 120, 300  # chars per item; enforced on add/edit
DETAIL_HOURS = 48  # `agenda list`: items due this soon show their context line
INJECT_HOURS = 24  # per-turn injection: only items due within this window (or overdue)
INJECT_MAX = 5     # and at most this many; the rest are a count
FULL_EVERY = 3600  # re-show the full list at least hourly per chat, else only when it changes


def _config():
    try:
        import yaml
        return yaml.safe_load(open(HOME / "config.yaml")) or {}
    except Exception:
        return {}


def _setting(key, default):
    s = ((_config().get("plugins") or {}).get("entries") or {}).get("agenda") or {}
    return (s.get("settings") or {}).get(key) or default


def _user():
    s = ((_config().get("plugins") or {}).get("entries") or {}).get("agenda") or {}
    return (s.get("settings") or {}).get("user_name") or "the user"


def _tz():
    try:
        return ZoneInfo(_config().get("timezone") or "UTC")
    except Exception:
        return ZoneInfo("UTC")


def _now():
    return datetime.now(_tz())


def _parse_when(s):
    """'+30m' '+2h' '+3d', 'HH:MM' (next), 'YYYY-MM-DD', 'YYYY-MM-DD HH:MM' -> aware datetime."""
    s, now = (s or "").strip(), _now()
    low = s.lower()
    if low == "today":
        return now.replace(hour=23, minute=59, second=0, microsecond=0)
    if low == "tomorrow":
        return (now + timedelta(days=1)).replace(hour=10, minute=0, second=0, microsecond=0)
    if low == "this week":
        return (now + timedelta(days=6 - now.weekday())).replace(hour=18, minute=0, second=0, microsecond=0)
    if low == "next week":
        return (now + timedelta(days=7 - now.weekday())).replace(hour=10, minute=0, second=0, microsecond=0)
    m = re.fullmatch(r"\+(\d+)([mhd])", s)
    if m:
        unit = {"m": "minutes", "h": "hours", "d": "days"}[m[2]]
        return now + timedelta(**{unit: int(m[1])})
    if re.fullmatch(r"\d{1,2}:\d{2}", s):
        h, mi = map(int, s.split(":"))
        t = now.replace(hour=h, minute=mi, second=0, microsecond=0)
        return t if t > now else t + timedelta(days=1)
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            t = datetime.strptime(s, fmt).replace(tzinfo=_tz())
            return t.replace(hour=10) if fmt == "%Y-%m-%d" else t
        except ValueError:
            pass
    raise ValueError(f"can't read time {s!r}; use today, tomorrow, this week, next week, +2h, 14:30, 2026-11-20 or 2026-11-20 14:30")


def _rel(t, now):
    days = (t.date() - now.date()).days
    if t < now:
        return "OVERDUE"
    return {0: "today", 1: "tomorrow"}.get(days, f"in {days}d")


def _fmt(iso):
    t = datetime.fromisoformat(iso).astimezone(_tz())
    return t.strftime("%a %d %b %H:%M")


def _load():
    try:
        return json.loads(OPEN.read_text())
    except Exception:
        return []


def _save(items):
    DIR.mkdir(parents=True, exist_ok=True)
    tmp = OPEN.with_suffix(".tmp")
    tmp.write_text(json.dumps(items, indent=1, ensure_ascii=False))
    os.replace(tmp, OPEN)


def _wake(cmd, *args):
    try:
        exe = shutil.which("wake") or str(HOME / "bin" / "wake")
        out = subprocess.run([exe, cmd, *args],
                             capture_output=True, text=True, timeout=20).stdout
        m = re.search(r"wake ([0-9a-f]{12})", out)
        return m[1] if m else None
    except Exception:
        return None


def _set_wake(item, when, why):
    if item.get("wake_id"):
        _wake("cancel", item["wake_id"])
    item["wake_id"] = _wake("add", when.strftime("%Y-%m-%d %H:%M"),
                            f"Agenda [{item['id']}] {why}: {item['text']}. Check it, then act or message {_user()}; update the agenda.")


def _render(items, now, budget=None):
    """Open items, soonest first. Context lines only for items due within DETAIL_HOURS.
    With a token budget (~4 chars/token), stop early and count what's left."""
    far = datetime.max.replace(tzinfo=_tz())
    key = lambda i: (datetime.fromisoformat(i["when"]) if i.get("when") else far, i["created"])
    live = [i for i in sorted(items, key=key)
            if not (i.get("snooze_until") and datetime.fromisoformat(i["snooze_until"]) > now)]
    hidden = len(items) - len(live)
    head = f"[agenda] {len(live)} open"
    head += f", {hidden} snoozed" if hidden else ""
    if len(live) > SOFT_CAP:
        head += f". Over {SOFT_CAP}: tick, drop or merge stale items"
    due = sum(1 for i in live if i.get("when") and datetime.fromisoformat(i["when"]) <= now)
    head += " (tool `agenda`: add/done/drop/snooze/edit/list/search; keep it true)"
    if due:
        head += (f". {due} due: raise ONE at a natural break (task just finished, or a casual message), never mid-task;"
                 " if they defer, snooze it: 'later' = +2h, 'tomorrow' = tomorrow, or the time they name")
    head += ":"
    lines, used, left = [head], len(head), 0
    limit = budget * 4 if budget else None
    for n, it in enumerate(live):
        tag = "you" if it["owner"] == "me" else _user()
        w = it.get("when")
        wt = datetime.fromisoformat(w) if w else None
        when = f"{_rel(wt, now)}, {_fmt(w)}" if w else "NO DATE: set one"
        line = f"- [{it['id']}] {when} | {tag}: {it['text']}"
        if not budget or (wt and (wt - now).total_seconds() < DETAIL_HOURS * 3600):
            ctx = it.get("context") or "no context: add why/source/next step"
            line += f"\n    {ctx} (added {_fmt(it['created'])})"
        if limit and used + len(line) > limit:
            left = len(live) - n
            break
        lines.append(line)
        used += len(line) + 1
    if left:
        lines.append(f"+{left} later item(s) not shown: `agenda list` for all")
    return "\n".join(lines)


def _render_due(items, now, budget):
    """Per-turn view: only what's due within INJECT_HOURS (max INJECT_MAX), one line each,
    context only for overdue/due-now items. Nothing due -> inject nothing."""
    live = [i for i in items if not (i.get("snooze_until") and datetime.fromisoformat(i["snooze_until"]) > now)]
    due = sorted((i for i in live if i.get("when") and
                  (datetime.fromisoformat(i["when"]) - now).total_seconds() < INJECT_HOURS * 3600),
                 key=lambda i: i["when"])
    if not due:
        return None
    head = (f"[agenda] {len(due)} due within {INJECT_HOURS}h of {len(live)} open "
            "(tool `agenda`; `list` for the rest). Raise ONE at a natural break, never mid-task; "
            "'later' = snooze +2h:")
    lines, limit = [head], budget * 4
    for n, it in enumerate(due[:INJECT_MAX]):
        wt = datetime.fromisoformat(it["when"])
        tag = "you" if it["owner"] == "me" else _user()
        line = f"- [{it['id']}] {_rel(wt, now)}, {_fmt(it['when'])} | {tag}: {it['text']}"
        if wt <= now:
            line += f"\n    {it.get('context', '')}"
        if sum(len(l) + 1 for l in lines) + len(line) > limit:
            break
        lines.append(line)
    more = len(due) - (len(lines) - 1)
    if more > 0:
        lines.append(f"+{more} more due: `agenda list`")
    return "\n".join(lines)


def on_pre_llm_call(**kw):
    try:
        sid = str(kw.get("session_id") or "")
        if not sid or kw.get("parent_session_id"):
            return None
        items = _load()
        if not items:
            return None
        now = _now()
        body = _render_due(items, now, budget=int(_setting("max_tokens", 300)))
        if not body:
            return None
        h = hashlib.sha1(body.encode()).hexdigest()[:10]
        try:
            seen = json.loads(STATE.read_text())
        except Exception:
            seen = {}
        prev = seen.get(sid, {})
        full = kw.get("is_first_turn") or prev.get("h") != h or time.time() - prev.get("t", 0) > FULL_EVERY
        if full:
            seen[sid] = {"h": h, "t": time.time()}
            seen = dict(sorted(seen.items(), key=lambda kv: kv[1]["t"])[-200:])
            DIR.mkdir(parents=True, exist_ok=True)
            STATE.write_text(json.dumps(seen))
            return {"context": body}
        return {"context": body.split(" (tool", 1)[0] + ", unchanged since last shown."}
    except Exception:
        return None


def _log(it, action, detail=""):
    it.setdefault("history", []).append([_now().isoformat(timespec="minutes"), action, detail])


def _archive(it, status, note):
    it.update(status=status, closed=_now().isoformat(timespec="minutes"), note=note or "")
    _log(it, status, note or "")
    if it.get("wake_id"):
        _wake("cancel", it["wake_id"])
    with ARCHIVE.open("a") as f:
        f.write(json.dumps(it, ensure_ascii=False) + "\n")


def _too_long(args):
    if len(args.get("text") or "") > TEXT_MAX:
        return f"error: text over {TEXT_MAX} chars; shorten it (detail goes in context)"
    if len(args.get("context") or "") > CONTEXT_MAX:
        return f"error: context over {CONTEXT_MAX} chars; keep why/source/next step only"


def handle(args, **_):
    a = args.get("action")
    items, now = _load(), _now()
    find = lambda i: next((x for x in items if x["id"] == i), None)
    try:
        if a == "list":
            if not items:
                return "agenda empty"
            sn = [f"- [{i['id']}] snoozed until {_fmt(i['snooze_until'])} | {i['text']}"
                  for i in items if i.get("snooze_until") and datetime.fromisoformat(i["snooze_until"]) > now]
            return _render(items, now) + ("\nSnoozed:\n" + "\n".join(sn) if sn else "")
        if a in ("add", "edit") and _too_long(args):
            return _too_long(args)
        if a == "add":
            if not (args.get("when") and args.get("context")):
                return "error: add needs `when` (today/tomorrow/this week/date/time) and `context` (why it matters, where it came from, next step)"
            it = {"id": secrets.token_hex(2), "text": args["text"].strip(), "owner": args.get("owner", "me"),
                  "created": now.isoformat(timespec="minutes"),
                  "when": _parse_when(args["when"]).isoformat(timespec="minutes"),
                  "context": args["context"].strip()}
            _log(it, "added", f"when {_fmt(it['when'])}")
            if args.get("remind_at"):
                _set_wake(it, _parse_when(args["remind_at"]), "reminder")
            items.append(it)
            _save(items)
            return f"added [{it['id']}]" + (f", wake {it.get('wake_id')}" if it.get("wake_id") else "")
        if a in ("done", "drop"):
            it = find(args.get("id"))
            if not it:
                return f"no open item {args.get('id')!r}"
            items.remove(it)
            _archive(it, "done" if a == "done" else "dropped", args.get("note"))
            _save(items)
            return f"{a} [{it['id']}] archived"
        if a == "snooze":
            it = find(args.get("id"))
            if not it:
                return f"no open item {args.get('id')!r}"
            t = _parse_when(args.get("until") or "+2h")
            it["snooze_until"] = t.isoformat(timespec="minutes")
            _log(it, "snoozed", f"until {_fmt(it['snooze_until'])}")
            if it.get("wake_id") and not args.get("keep_wake"):
                _wake("cancel", it.pop("wake_id"))
            _save(items)
            return f"snoozed [{it['id']}] until {_fmt(it['snooze_until'])}"
        if a == "edit":
            it = find(args.get("id"))
            if not it:
                return f"no open item {args.get('id')!r}"
            for k in ("text", "owner", "context"):
                if args.get(k):
                    it[k] = args[k]
            if args.get("when"):
                it["when"] = _parse_when(args["when"]).isoformat(timespec="minutes")
            if args.get("remind_at"):
                _set_wake(it, _parse_when(args["remind_at"]), "reminder")
            _log(it, "edited", ", ".join(k for k in ("text", "owner", "context", "when", "remind_at") if args.get(k)))
            _save(items)
            return f"edited [{it['id']}]"
        if a == "search":
            q, out = (args.get("query") or "").lower(), []
            if ARCHIVE.exists():
                for line in ARCHIVE.read_text().splitlines():
                    if q in line.lower():
                        r = json.loads(line)
                        hist = "; ".join(f"{_fmt(t)} {a}{' ' + d if d else ''}" for t, a, d in r.get("history", []))
                        out.append(f"[{r['id']}] {r['status']}: {r['text']}\n    {hist or 'added ' + _fmt(r['created'])}" + (f"\n    outcome: {r['note']}" if r.get("note") else ""))
            return "\n".join(out[-20:]) or "no archived match"
        return "unknown action"
    except (KeyError, ValueError) as e:
        return f"error: {e}"


SCHEMA = {
    "name": "agenda",
    "description": (
        "Your running todo list. Items due within 24h are shown to you each turn; `list` shows the rest. Add anything you owe the user or are waiting on them for. "
        "Every item needs `when` (today, tomorrow, this week, a date or a time: when it must happen or be looked at) "
        "and `context` (why it matters, where it came from, the next step). Items are raised in conversation when due, not by alarms. Security alerts (sign-ins, password or recovery changes) and money at risk are never agenda items: tell the user right away. "
        "Use remind_at ONLY for hard deadlines that must fire even if the user is silent (flight check-in, a renewal cutoff, a timed job of yours). "
        "Snooze hides an item until a time; it comes back into this list then, with no alarm. If the user defers: 'later' = +2h, 'tomorrow' only if they say it, else the time they name. "
        "Tick (done) or drop items the moment they resolve, with a short note; they move to a searchable archive. "
        "Keep it under 15 open: merge or drop stale items. Times: today, tomorrow, this week, next week, +2h, 14:30, 2026-11-20, 2026-11-20 14:30."
    ),
    "parameters": {"type": "object", "properties": {
        "action": {"type": "string", "enum": ["list", "add", "done", "drop", "snooze", "edit", "search"]},
        "id": {"type": "string", "description": "item id for done/drop/snooze/edit"},
        "text": {"type": "string", "description": "one line: what, and the next step"},
        "owner": {"type": "string", "enum": ["me", "user"], "description": "who has the next move (default me)"},
        "when": {"type": "string", "description": "required on add: when it must happen or be looked at"},
        "context": {"type": "string", "description": "required on add: why it matters, source, next step (1-2 lines)"},
        "remind_at": {"type": "string", "description": "hard deadlines only: schedules a wake that fires even if the user is silent"},
        "until": {"type": "string", "description": "snooze: hide until this time (default +2h); no alarm"},
        "note": {"type": "string", "description": "done/drop: outcome, kept in the archive"},
        "query": {"type": "string", "description": "search: text to find in the archive"},
    }, "required": ["action"]},
}


def register(ctx):
    ctx.register_tool(name="agenda", toolset="agenda", schema=SCHEMA, handler=handle, emoji="📋")
    ctx.register_hook("pre_llm_call", on_pre_llm_call)
