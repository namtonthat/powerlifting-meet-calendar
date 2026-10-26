"""Build subscribable .ics feeds of upcoming powerlifting meets."""

import html
import logging
import re
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse

import requests
from icalendar import Calendar, Event
from requests.adapters import HTTPAdapter
from urllib3.util import Retry

log = logging.getLogger(__name__)

OUT = Path("public")
SESSION = requests.Session()
SESSION.headers["User-Agent"] = "powerlifting-meet-calendar (+https://github.com/namtonthat/powerlifting-meet-calendar)"
SESSION.mount("https://", HTTPAdapter(max_retries=Retry(total=3, backoff_factor=2, status_forcelist=(502, 503, 504))))
# LiftingCast 429s after about 100 quick requests and stays blocked for a long while, so pace it instead of retrying.
LIFTINGCAST_PAUSE = 3

# ponytail: Russia/Belarus left out on purpose; add them here if wanted
EUROPE = {
    "Austria", "Belgium", "Bulgaria", "Croatia", "Cyprus", "Czech Republic", "Czechia", "Denmark", "Estonia", "Finland",
    "France", "Georgia", "Germany", "Greece", "Hungary", "Iceland", "Ireland", "Italy", "Latvia", "Lithuania", "Luxembourg",
    "Malta", "Moldova", "Netherlands", "Norway", "Poland", "Portugal", "Romania", "Serbia", "Slovakia", "Slovenia", "Spain",
    "Sweden", "Switzerland", "Ukraine", "United Kingdom",
}  # fmt: skip
NOT_OPEN = ("SOLD OUT", "CLOSED", "CANCELLED")
# powerlifting.com's sport categories are patchy, so drop the other sports and non-meets instead
NOT_A_MEET = re.compile(r"strongman|weightlifting|\bIWF\b|strongfirst|kettlebell|highland games|clinic|certification|seminar|mock meet", re.IGNORECASE)


@dataclass
class Meet:
    uid: str
    name: str
    start: date
    end: date
    federation: str
    location: str
    country: str
    link: str
    listing: str
    added: date
    status: str | None = None


FEEDS: dict[str, Callable[[Meet], bool]] = {
    "all": lambda _: True,
    "au": lambda m: m.country == "Australia",
    "us": lambda m: m.country in {"USA", "United States"},
    "europe": lambda m: m.country in EUROPE,
    "mx": lambda m: m.country == "Mexico",
    "open": lambda m: bool(m.status) and not m.status.startswith(NOT_OPEN),
}


def get(url: str, **kwargs) -> requests.Response:
    time.sleep(0.2)
    response = SESSION.get(url, timeout=30, **kwargs)
    response.raise_for_status()
    return response


def powerlifting_com() -> list[Meet]:
    meets, page = [], 1
    while True:
        params = {"per_page": 50, "page": page, "start_date": date.today().isoformat()}
        data = get("https://powerlifting.com/wp-json/tribe/events/v1/events", params=params).json()
        for e in data["events"]:
            name = html.unescape(e["title"])
            organizers = [html.unescape(o["organizer"]) for o in e["organizer"]]
            if NOT_A_MEET.search(" ".join([name, *organizers])):
                continue
            venue = e["venue"] if isinstance(e["venue"], dict) else {}
            place = [venue.get(k) for k in ("venue", "city", "stateprovince", "country")]
            meets.append(
                Meet(
                    uid=f"plcom-{e['id']}",
                    name=name,
                    start=date.fromisoformat(e["start_date"][:10]),
                    end=date.fromisoformat(e["end_date"][:10]),
                    federation=", ".join(o for o in organizers if not o.startswith("*")),
                    location=html.unescape(", ".join(p for p in place if p)),
                    country=venue.get("country") or "",
                    link=e["website"] or e["url"],
                    listing=e["url"],
                    added=date.fromisoformat(e["date"][:10]),
                )
            )
        if page >= data["total_pages"]:
            return meets
        page += 1


def femepo() -> list[Meet]:
    # ponytail: single page of 300; follow nextPageToken if FEMEPO ever lists more
    url = "https://firestore.googleapis.com/v1/projects/femepo-web/databases/(default)/documents/events"
    meets = []
    for doc in get(url, params={"pageSize": 300}).json().get("documents", []):
        f = {k: next(iter(v.values())) for k, v in doc["fields"].items()}
        start = datetime.strptime(f["startDate"][:10].replace("-", "/"), "%Y/%m/%d").date()
        if start < date.today():
            continue
        meets.append(
            Meet(
                uid=f"femepo-{doc['name'].rsplit('/', 1)[1]}",
                name=f["title"].strip(),
                start=start,
                end=start,
                federation="FEMEPO",
                location=", ".join(p for p in (f.get("address"), f.get("state")) if p),
                country="Mexico",
                link=f.get("url") or "https://femepo.com.mx/calendar.html",
                listing="https://femepo.com.mx/calendar.html",
                added=date.fromisoformat(doc["createTime"][:10]),
            )
        )
    return meets


def flag(text: str) -> str | None:
    if re.search(r"SOLD OUT", text, re.IGNORECASE):
        return "SOLD OUT"
    if re.search(r"CANCELL?ED", text, re.IGNORECASE):
        return "CANCELLED"
    return None


def apa_status(page: str) -> str | None:
    title = re.search(r'<meta property="og:title" content="([^"]*)"', page)
    if title and (flagged := flag(title[1])):
        return flagged
    if "Registrations for this event are closed" in page:
        return "CLOSED"
    cap = re.search(r"Maximum number of entrants:</strong>\s*(\d+)", page)
    if ">Register<" in page:
        return f"OPEN · cap {cap[1]}" if cap else "OPEN"
    return None


def jotform_status(page: str) -> str:
    # A closed form drops the form markup and puts the director's message in <title>.
    if "jotform-form" not in page:
        title = re.search(r"<title>([^<]*)", page)
        return "SOLD OUT" if title and re.search(r"sold out|\bfull\b", title[1], re.IGNORECASE) else "CLOSED"
    cap = re.search(r"LIMITED TO (\d+)", page, re.IGNORECASE)
    return f"OPEN · cap {cap[1]}" if cap else "OPEN"


def liftingcast_status(docs: list[dict]) -> str:
    return f"{sum(d['_id'].startswith('l') for d in docs)} entered"


def status(meet: Meet) -> str | None:
    if flagged := flag(meet.name):
        return flagged
    url = meet.link.split("?")[0]
    host = urlparse(url).hostname or ""
    try:
        if host.endswith("powerliftingalliance.org.au"):
            return apa_status(get(url).text)
        if host.endswith("jotform.com"):
            return jotform_status(get(url).text)
        # ponytail: LiftingCast only for meets in the next 90 days to stay under its limit; widen if the 429s stop
        soon = meet.start <= date.today() + timedelta(days=90)
        if host.endswith("liftingcast.com") and soon and (m := re.search(r"/meets/([a-z0-9]+)", url)):
            time.sleep(LIFTINGCAST_PAUSE)
            return liftingcast_status(get(f"https://liftingcast.com/api/meets/{m[1]}").json()["docs"])
    except requests.RequestException as err:
        log.warning("status lookup failed for %s: %s", url, err)
    return None


def write_feed(name: str, meets: list[Meet]) -> None:
    cal = Calendar()
    cal.add("prodid", "-//powerlifting-meet-calendar//EN")
    cal.add("version", "2.0")
    cal.add("x-wr-calname", f"Powerlifting meets ({name})")
    stamp = datetime.now(UTC)
    for m in meets:
        event = Event()
        event.add("uid", f"{m.uid}@powerlifting-meet-calendar")
        event.add("summary", f"[{m.status}] {m.name}" if m.status else m.name)
        event.add("dtstart", m.start)
        event.add("dtend", m.end + timedelta(days=1))
        event.add("dtstamp", stamp)
        event.add("location", m.location)
        event.add("url", m.link)
        lines = [f"Federation: {m.federation or 'unknown'}", f"Status: {m.status or 'unknown'}", f"Sign up / info: {m.link}"]
        if m.listing != m.link:
            lines.append(f"Listing: {m.listing}")
        lines.append(f"Added: {m.added}")
        event.add("description", "\n".join(lines))
        cal.add_component(event)
    (OUT / f"{name}.ics").write_bytes(cal.to_ical())


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    meets = powerlifting_com() + femepo()
    # An empty or truncated pull would wipe subscribers' calendars; fail and keep the last deploy instead.
    if len(meets) < 200:
        raise SystemExit(f"only {len(meets)} meets pulled; not publishing")
    for m in meets:
        m.status = status(m)
    OUT.mkdir(exist_ok=True)
    for name, keep in FEEDS.items():
        selected = [m for m in meets if keep(m)]
        write_feed(name, selected)
        log.info("%s.ics: %d meets", name, len(selected))


if __name__ == "__main__":
    main()
