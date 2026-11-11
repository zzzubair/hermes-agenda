# agenda

A Hermes plugin that gives your agent its own running todo list, raised in conversation when things are due.

- Per turn, only items due within 24 hours (max 5) are injected, one line each; overdue ones carry their context. Nothing due means nothing injected, so the model's context stays clean. `agenda list` shows everything.
- One `agenda` tool: `add`, `done`, `drop`, `snooze`, `edit`, `list`, `search`.
- Every item needs a `when` (today, tomorrow, this week, next week, a date or a time) and `context` (why, source, next step).
- Snooze hides an item until a time, then it comes back into the list. No alarm needed: the agent raises it next time you talk.
- Every change is timestamped. Ticked or dropped items move to an append-only archive you can search later.
- Hard deadlines (`remind_at`) can fire even when you're silent. Pick how in setup, below.
- `max_tokens` (default 300) caps the injection. Item text is capped at 120 chars, context at 300.

## Install: paste this to your Hermes agent

```text
Install the agenda plugin for me: https://github.com/zzzubair/hermes-agenda

1. Clone it into $HERMES_HOME/plugins/agenda (default ~/.hermes/plugins/agenda) and run `hermes plugins enable agenda`.
2. Ask me what name to use for me, and set plugins.entries.agenda.settings.user_name with `hermes config set`.
3. Check that Hermes's top-level `timezone` is set; if not, ask me for mine and set it.
4. Ask me how hard-deadline reminders should reach me when I'm not chatting. Explain the three options in one line each:
   - wake: install the wake plugin (https://github.com/zzzubair/hermes-wake). You (the agent) get woken at that time and message me yourself, with context. Best experience, one extra plugin.
   - cron: no extra plugin. A one-shot Hermes cron job posts the reminder to a channel I choose (telegram, discord, bot-chat, local...). Ask which, and set plugins.entries.agenda.settings.cron_deliver.
   - off: no alarms. Items still come up when I next talk to you.
   Set plugins.entries.agenda.settings.reminders to my choice. If I pick wake, install it and follow its README setup.
5. Tell me to start a new chat (the tool loads in new sessions), then in that chat add one test item due today, list it, and drop it.
```

## Install by hand

```bash
git clone https://github.com/zzzubair/hermes-agenda ~/.hermes/plugins/agenda
hermes plugins enable agenda
hermes config set plugins.entries.agenda.settings.user_name Alex
hermes config set plugins.entries.agenda.settings.reminders cron   # wake | cron | off
hermes config set plugins.entries.agenda.settings.cron_deliver telegram   # only for cron
```

Without the setting, reminders use `wake` if the wake plugin's `wake` command is installed, otherwise `cron` to `local` (saved on disk, not pushed anywhere). Snooze and the per-turn list never need either.

Times use Hermes's top-level `timezone`. Data lives in `$HERMES_HOME/agenda/` (`open.json`, `archive.jsonl`), never in this repo.

MIT licensed.
