# powerlifting-meet-calendar

Upcoming powerlifting meets as calendar feeds you can subscribe to. Rebuilt daily.

| Feed | What's in it |
|---|---|
| [all.ics](https://namtonthat.github.io/powerlifting-meet-calendar/all.ics) | Every meet, worldwide |
| [au.ics](https://namtonthat.github.io/powerlifting-meet-calendar/au.ics) | Australia |
| [us.ics](https://namtonthat.github.io/powerlifting-meet-calendar/us.ics) | United States |
| [europe.ics](https://namtonthat.github.io/powerlifting-meet-calendar/europe.ics) | Europe (excludes Russia and Belarus) |
| [mx.ics](https://namtonthat.github.io/powerlifting-meet-calendar/mx.ics) | Mexico (FEMEPO) |
| [open.ics](https://namtonthat.github.io/powerlifting-meet-calendar/open.ics) | Meets with a sign-up page confirmed live |

Subscribe in Google Calendar via **Other calendars → From URL**, or in Apple Calendar via **File → New Calendar Subscription**. Google re-reads subscribed feeds only every 12 to 24 hours.

## Sources

- [powerlifting.com](https://powerlifting.com/events/) events API: US, Australia, Europe and most other countries, including APA, APL and Powerlifting Australia meets.
- [FEMEPO](https://femepo.com.mx/calendar.html) calendar: Mexico.

## Sign-up status

The event title starts with a status when the meet's sign-up page reveals one:

| Sign-up page | Status shown |
|---|---|
| APA (Revolutionise) | `OPEN · cap N`, `SOLD OUT`, `CLOSED`, `CANCELLED` |
| JotForm (most USAPL meets) | `OPEN · cap N` (cap from "LIMITED TO N"), `SOLD OUT`, `CLOSED` |
| LiftingCast | `N entered` (the cap isn't public) |
| Any source | `SOLD OUT` or `CANCELLED` when the meet title says so |

Not covered yet: uspa.net, wrpf.pro, ironpodium.com, aplpowerlifting.com, JustGo (Powerlifting Australia) and StrengthHub (FEMEPO) sign-up pages.

## Run locally

```bash
uv run pytest -q
uv run python build_feeds.py   # writes public/*.ics
```
