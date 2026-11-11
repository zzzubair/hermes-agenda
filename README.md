# agenda

A Hermes plugin that gives the agent its own running todo list, always in context.

- Per turn, only items due within 24 hours (max 5) are injected, one line each; overdue ones carry their context. Nothing due means nothing injected, so the model's context stays clean. `agenda list` shows everything.
- `max_tokens` (default 300) caps the injection. Item text is capped at 120 chars, context at 300.
- One `agenda` tool: `add`, `done`, `drop`, `snooze`, `edit`, `list`, `search`.
- Every item needs a `when` (today, tomorrow, this week, next week, a date or a time) and `context` (why, source, next step).
- Every change is timestamped in the item's history. Ticked or dropped items move to an append-only archive you can search later.
- `remind_at` and `snooze` schedule a one-off wake through the [wake](https://github.com/zzzubair/hermes-wake) plugin's `wake` CLI. Closing an item cancels its wake.
- Snoozed items are hidden from the injected list until their time.

## Install

```bash
git clone https://github.com/zzzubair/hermes-agenda ~/.hermes/plugins/agenda
hermes plugins enable agenda
```

Settings in `config.yaml`:

```yaml
plugins:
  entries:
    agenda:
      settings:
        user_name: Alex
        max_tokens: 300
```

Times use Hermes's top-level `timezone`. Data lives in `$HERMES_HOME/agenda/` (`open.json`, `archive.jsonl`), never in this repo.

MIT licensed.
