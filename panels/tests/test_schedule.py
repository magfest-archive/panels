import pytest
import pytz
from panels import *
from panels.site_sections import schedule


UTCNOW = datetime.utcnow().replace(tzinfo=pytz.UTC)
UTC20DAYSLATER = UTCNOW + timedelta(days=20)


@pytest.fixture()
def admin_attendee():
    with Session() as session:
        session.insert_test_admin_account()

    with Session() as session:
        attendee = session.query(Attendee).filter(
            Attendee.email == 'magfest@example.com').one()
        cherrypy.session['account_id'] = attendee.admin_account.id
        yield attendee
        cherrypy.session['account_id'] = None
        session.delete(attendee)


@pytest.fixture()
def create_events():
    with Session() as session:
        for index, (loc, desc) in enumerate(c.EVENT_LOCATION_OPTS):
            session.add(Event(
                location=loc,
                start_time=UTC20DAYSLATER,
                duration=1,
                name='Event {}'.format(index),
                description=desc))

    with Session() as session:
        events = session.query(Event).all()
        yield events
        for event in events:
            session.delete(event)


def test_csv(create_events, admin_attendee):
    response = schedule.Root().csv()
    if isinstance(response, bytes):
        response = response.decode('utf-8')

    lines = response.split('\n')
    assert len(lines) == 41
    assert lines[0].strip() == 'Session Title,Date,Time Start,Time End,Room/Location,Schedule Track (Optional),Description (Optional),Allow Checkin (Optional),Checkin Begin (Optional),Limit Spaces? (Optional),Allow Waitlist (Optional)'


def test_schedule_tsv(create_events):
    response = schedule.Root().schedule_tsv()
    if isinstance(response, bytes):
        response = response.decode('utf-8')

    lines = response.split('\n')
    assert len(lines) == 41
    assert lines[0].strip() == 'Session Title\tDate\tTime Start\tTime End\tRoom/Location\tSchedule Track (Optional)\tDescription (Optional)'
