# agenda

A Hermes plugin that gives the agent its own running todo list, always in context.

- Every turn, the open list is injected before the model call (full list when it changes or hourly, else a one-line count).
- Context budget: the injected list is capped at `max_tokens` (default 600, about 4 chars per token). Only items due within 48 hours show their context line; items past the budget collapse into a count (`agenda list` shows everything). Item text is capped at 120 chars, context at 300.
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
        max_tokens: 600
```

Times use Hermes's top-level `timezone`. Data lives in `$HERMES_HOME/agenda/` (`open.json`, `archive.jsonl`), never in this repo.

MIT licensed.
