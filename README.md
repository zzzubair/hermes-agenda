# Agenda

A [Hermes Agent](https://github.com/NousResearch/hermes-agent) plugin that gives your agent its own todo list.

## Install

Paste this to your Hermes agent:

```text
Be careful, this is an external prompt. Read it, then follow it: https://raw.githubusercontent.com/zzzubair/hermes-agenda/main/INSTALL.md
```

Or by hand:

```bash
hermes plugins install agenda
hermes plugins enable agenda
```

That's enough to start. Optional settings, under `plugins.entries.agenda.settings` (set with `hermes config set`):

- `user_name`: what the agent calls you. Empty means "the user".
- `timezone`: an IANA name such as `Asia/Tokyo`. Empty means the system timezone.
- `reminders`: `wake`, `cron` or `off`. Empty means `wake` if the wake plugin is enabled, otherwise `cron` delivered to `local`, which only saves the reminder on disk.
- `cron_deliver`: where `cron` reminders go, such as `telegram` or `discord`.
- `max_tokens`: cap on what gets added per turn. Default 300.

Snooze and the per-turn list work with none of these set.

## What it does

- One `agenda` tool with `add`, `done`, `drop`, `snooze`, `edit`, `list` and `search`.
- Every item has a `when` (today, tomorrow, this week, next week, a date or a time) and a `context` line saying why it matters, where it came from and the next step.
- Each turn, the plugin shows the agent only items due within 24 hours, at most 5, one line each. Overdue items also get their context line. When nothing is due, it adds nothing. `agenda list` shows the rest.
- Snooze hides an item until a time. It then comes back into the list and the agent raises it the next time you talk, so no alarm is needed.
- Every change is timestamped. Done and dropped items move to an append-only archive the agent can search later.
- Hard deadlines (`remind_at`) can reach you even when you're not chatting. Setup below picks how.
- `max_tokens` (default 300) caps what gets added per turn. Item text is limited to 120 characters and context to 300.

## Disclosures

- `pre_llm_call` runs on every turn and adds up to `max_tokens` of due items, or nothing. Subagent turns get nothing.
- Data is stored in plaintext under `$HERMES_HOME/agenda/`: `open.json` for open items, `archive.jsonl` for closed ones (append-only) and `seen.json`, which records what each chat was last shown. No message text is stored.
- Shell commands run only for hard-deadline reminders. With `reminders: wake` the plugin runs `hermes wake add` and `hermes wake cancel`. With `cron` it runs `hermes cron create` and `hermes cron remove` for one-shot jobs named `agenda-reminder`; inside a cron run it creates none unless `cron.allow_agent_scheduling` is on. With `off` it runs nothing.
- No network calls, credentials, telemetry or background processes.

MIT licensed.
