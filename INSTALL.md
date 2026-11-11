# Install agenda (prompt for a Hermes agent)

Install the agenda plugin for me: https://github.com/zzzubair/hermes-agenda

1. Run `hermes plugins install agenda` (if it isn't in the catalog on this Hermes, clone the repo into $HERMES_HOME/plugins/agenda), then `hermes plugins enable agenda`.
2. Ask me what to call me and set plugins.entries.agenda.settings.user_name.
3. Ask me for my timezone (IANA, e.g. Europe/London) and set plugins.entries.agenda.settings.timezone.
4. Ask me how hard-deadline reminders should reach me when I'm not chatting. Explain each option in one line:
   - wake: install the wake plugin (https://github.com/zzzubair/hermes-wake). At the deadline you get woken and message me yourself.
   - cron: no extra plugin. A one-shot Hermes cron job posts the reminder to a channel I pick (telegram, discord, bot-chat, local). Ask which and set plugins.entries.agenda.settings.cron_deliver.
   - off: no alarms. Items still come up the next time I talk to you.
   Set plugins.entries.agenda.settings.reminders to my choice. If I pick wake, install it and follow its README.
5. Tell me to start a new chat, since the tool loads in new sessions. In that chat, add a test item due today, list it, then drop it.
