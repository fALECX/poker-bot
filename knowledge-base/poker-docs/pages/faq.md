# faq

Source: https://docs.poker.monashcoding.com/faq/

FAQ | macpoker docs- - - - - Skip to content
How do teams work?
Teams of 1 to 4 people share one account. First, every member buys their
own ticket on Humanitix (MAC members get member pricing there). Then register
at poker.monashcoding.com with a team
name, each member’s name and the email they used on Humanitix, plus a login
email and a password your whole team can use. Registration checks that every
member holds a valid ticket. Add or remove teammates later from the Team page;
anyone you add needs their own Humanitix ticket, checked against the email
you enter.
What do I upload?
A zip with main.py at its root. A single .py file also works. Upload as
many versions as you like before the deadline; each is validated by playing
a short game against the house call-bot.
What is a “main” submission?
Your tournament entry. After a submission passes validation you can mark it
as main from your feed. Your first passing upload becomes main
automatically. You can change it any time until the deadline, and never
after.
Can I use numpy? Can I use requests?
numpy yes, requests no. The sandbox has the standard library, numpy and the
SDK, and no network. An import that isn’t available fails validation, which
you will see in your feed.
Can I use ChatGPT or Claude to write my bot?
For development, yes. At runtime, no. Your bot cannot call anything outside
the sandbox during a match; there is no network, and submissions are read
by humans. Getting caught smuggling means disqualification.
Can we work with another team?
No. Bots play for themselves alone, and teams must not coordinate. See the
rules.
Can my bot keep thinking while opponents act?
No. Your bot computes only inside act() and the observer hooks, with no
background threads or extra processes. The time bank covers all of your
thinking.
How long does my bot get to think?
A 30-second time bank per game plus 0.1 seconds every hand,
exactly like a chess clock. Blow it and the bot check-folds the rest of the
game with a TLE verdict.
Can my bot tell opponents apart?
Yes, within a game. Each opponent has a player id that stays fixed for the
whole game, and every message maps seats to player ids, so you can learn how
each bot plays. You are never told which team is behind an id, and ids
reset between games.
Why did my bot lose chips against the call bot but still pass validation?
Validation checks that your bot speaks the protocol and survives, not that
it wins. Ratings and tournament results are a different matter.
My upload was rejected. Where do I see why?
Your feed at poker.monashcoding.com/app
shows the verdict, the error and your bot’s own output for every submission.
What happens at the closing ceremony?
The tournament has already been judged by then. The ceremony replays the
games table by table on the big screens, all hole cards face up, with the
points and standings revealed round by round.
Where do I ask questions?
The hackathon Discord.
