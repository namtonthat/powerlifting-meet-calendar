from datetime import date

from icalendar import Calendar

import build_feeds as b


def meet(**overrides) -> b.Meet:
    fields = {
        "uid": "plcom-1",
        "name": "Test Open",
        "start": date(2027, 1, 30),
        "end": date(2027, 1, 31),
        "federation": "USA Powerlifting",
        "location": "Boston, MA, USA",
        "country": "USA",
        "link": "https://form.jotform.com/1",
        "listing": "https://powerlifting.com/event/test-open/",
        "added": date(2026, 10, 1),
    }
    return b.Meet(**(fields | overrides))


def test_apa_status():
    open_page = "<strong>Maximum number of entrants:</strong> 28 <a>Register</a>"
    assert b.apa_status(open_page) == "OPEN · cap 28"
    assert b.apa_status('<meta property="og:title" content="City Open - SOLD OUT!" /><a>Register</a>') == "SOLD OUT"
    assert b.apa_status('<meta property="og:title" content="Unity Games II - CANCELLED BY MEET DIRECTOR" />') == "CANCELLED"
    assert b.apa_status("Registrations for this event are closed") == "CLOSED"


def test_jotform_status():
    assert b.jotform_status('<form class="jotform-form"><p>LIMITED TO 70 LIFTERS</p>') == "OPEN · cap 70"
    assert b.jotform_status("<title>Sorry, this competition is now full</title>") == "SOLD OUT"
    assert b.jotform_status("<title>Registration is closed for this event</title>") == "CLOSED"


def test_liftingcast_status():
    assert b.liftingcast_status([{"_id": "m1"}, {"_id": "l1"}, {"_id": "l2"}, {"_id": "d1"}]) == "2 entered"


def test_feeds():
    assert b.FEEDS["us"](meet())
    assert not b.FEEDS["europe"](meet())
    assert b.FEEDS["open"](meet(status="OPEN · cap 70"))
    assert b.FEEDS["open"](meet(status="12 entered"))
    assert not b.FEEDS["open"](meet(status="SOLD OUT"))
    assert not b.FEEDS["open"](meet())


def test_write_feed(tmp_path, monkeypatch):
    monkeypatch.setattr(b, "OUT", tmp_path)
    b.write_feed("us", [meet(status="OPEN · cap 70", name="Señor, Open; Classic")])
    event = Calendar.from_ical((tmp_path / "us.ics").read_bytes()).walk("VEVENT")[0]
    assert str(event["summary"]) == "[OPEN · cap 70] Señor, Open; Classic"
    assert event.decoded("dtend") == date(2027, 2, 1)
