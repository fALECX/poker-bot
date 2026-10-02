# rules

Source: https://docs.poker.monashcoding.com/rules/

Rules | macpoker docs- - - - - Skip to content
Teams
Section titled “Teams”
- Teams have 1 to 4 members, and each person belongs to one team.
- Every member holds their own ticket for the event.
Building your bot
Section titled “Building your bot”
- All bot code is written during the 48-hour hackathon. Nothing is written
beforehand.
- Submissions use the provided template: a zip with main.py at its root.
- Python standard library plus numpy only.
- AI tools are allowed for development: writing code, debugging and
brainstorming. They are not allowed at runtime. Your bot’s decisions come
from code your team wrote, not from a call to an AI model or any other
service during a game.
During a game
Section titled “During a game”
- No network access of any kind. The sandbox has none.
- Compute only on your own turn. Your bot works inside act() and the
observer hooks, and nowhere else. No background threads, no extra
processes, and no work scheduled to run while opponents are acting.
- No teaming. Your bot plays for itself alone. It must not recognise,
signal to, soft-play or pass chips to another team’s bot, and teams must
not agree on strategies that help each other.
- No interference. Do not try to read anything outside your own bot,
exhaust shared resources, or recover hidden information such as unseen
cards or the deck order by any means other than playing the game.
Review
Section titled “Review”
Every final submission is read by the organisers before the tournament
runs, for code quality and for compliance with these rules. A submission
that breaks a rule is removed from the tournament and the team is
disqualified. The organisers’ decision is final.
