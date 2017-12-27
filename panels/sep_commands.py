import uuid

from panels.models import *


# =============================================================================
# DEVELOPMENT TOOLS - DEVELOPMENT TOOLS - DEVELOPMENT TOOLS - DEVELOPMENT TOOLS
# vvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvv

from sqlalchemy.engine.default import DefaultDialect
from sqlalchemy.sql.sqltypes import String, DateTime, NullType

# python2/3 compatible.
PY3 = str is not bytes
text = str if PY3 else unicode
int_type = int if PY3 else (int, long)
str_type = str if PY3 else (str, unicode)


class StringLiteral(String):
    """Teach SA how to literalize various things."""
    def literal_processor(self, dialect):
        super_processor = super(StringLiteral, self).literal_processor(dialect)

        def process(value):
            if isinstance(value, int_type):
                return text(value)
            if not isinstance(value, str_type):
                value = text(value)
            result = super_processor(value)
            if isinstance(result, bytes):
                result = result.decode(dialect.encoding)
            return result
        return process


class LiteralDialect(DefaultDialect):
    colspecs = {
        # prevent various encoding explosions
        String: StringLiteral,
        # teach SA about how to literalize a datetime
        DateTime: StringLiteral,
        # don't format py2 long integers to NULL
        NullType: StringLiteral,
    }

RE_INTERVAL = re.compile(r'\'interval "(\d+) seconds"\'')


def literalquery(statement):
    """
    NOTE: This is entirely insecure. DO NOT execute the resulting strings.

    USAGE: literalquery(session.query(Attendee))
    """
    import sqlalchemy.orm
    if isinstance(statement, sqlalchemy.orm.Query):
        statement = statement.statement
    s = statement.compile(
        dialect=LiteralDialect(),
        compile_kwargs={'literal_binds': True},
    ).string
    return RE_INTERVAL.sub(r"interval '\1 seconds'", s)

# ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
# DEVELOPMENT TOOLS - DEVELOPMENT TOOLS - DEVELOPMENT TOOLS - DEVELOPMENT TOOLS
# =============================================================================


if c.DEV_BOX:
    @entry_point
    def drop_attractions():
        assert c.DEV_BOX, 'drop_attractions is only available on dev boxes'
        Session.initialize_db(initialize=True)
        with Session() as session:
            for model in [
                    AttractionNotification,
                    AttractionSignup,
                    AttractionEvent,
                    AttractionFeature,
                    Attraction]:
                try:
                    session.query(model).delete()
                except Exception as ex:
                    print(ex)
                    session.rollback()


if c.DEV_BOX:
    @entry_point
    def generate_attractions():
        assert c.DEV_BOX, 'generate_attractions is only available on dev boxes'
        Session.initialize_db(initialize=True)
        with Session() as session:
            now = datetime.now(pytz.UTC) + timedelta(minutes=15)

            owners = session.query(AdminAccount.id).all()
            owner_index = 0
            owner_count = len(owners)

            attendees = session.query(Attendee).filter(
                Attendee.first_name != '',
                Attendee.paid != c.NOT_PAID).all()
            attendee_index = 0
            attendee_count = len(attendees)

            MAGNITUDE = 1

            attractions = []
            for a_i in range(0, MAGNITUDE):
                attraction = Attraction(
                    name='Attraction {}'.format(a_i),
                    description='Attraction {} description'.format(a_i),
                    is_public=True,
                    owner_id=owners[owner_index][0],
                    advance_notices=[0, 300, 900, 1800])
                attractions.append(attraction)
                owner_index = (owner_index + 1) % owner_count

                for f_i in range(0, MAGNITUDE * 2):
                    feature = AttractionFeature(
                        name='Feature {}.{}'.format(a_i, f_i),
                        description='Feature {}.{} description'.format(a_i, f_i),
                        is_public=True)
                    attraction.features.append(feature)

                    for e_i in range(0, MAGNITUDE * 4):
                        event = AttractionEvent(
                            attraction_id=attraction.id,
                            location=c.EVENT_LOCATION_OPTS[f_i % len(c.EVENT_LOCATION_OPTS)][0],
                            start_time=(now + timedelta(hours=e_i)),
                            duration=2700,
                            slots=MAGNITUDE * 2)
                        feature.events.append(event)

                        for i in range(attendee_index, attendee_index + max(1, event.slots - 2)):
                            i = i % attendee_count
                            signup = AttractionSignup(
                                attraction_id=attraction.id,
                                attendee_id=attendees[i].id)
                            event.signups.append(signup)
                            # print('.'.join(map(str, [a_i, f_i, e_i, i])))

                        # Uncomment to generate some fake notifications
                        # for n in attraction.advance_notices[2:]:
                        #     for i in range(attendee_index, attendee_index + (event.slots // 2)):
                        #         i = i % attendee_count
                        #         notification = AttractionNotification(
                        #             attraction_event_id=event.id,
                        #             attraction_id=attraction.id,
                        #             attendee_id=attendees[i].id,
                        #             notification_type = Attendee.NOTIFICATION_TEXT,
                        #             ident=AttractionEvent.get_ident(event.id, n),
                        #             sid=uuid.uuid4().hex,
                        #             sent_time = datetime.now(pytz.UTC),
                        #             subject='',
                        #             body='{} - {}: {}'.format(attraction.name, feature.name, event.time_span_label))
                        #         event.notifications.append(notification)

                        attendee_index = (attendee_index + event.slots) % attendee_count

            session.add_all(attractions)


if c.DEV_BOX:
    from panels.notifications import send_attraction_notifications
    @entry_point
    def attraction_notifications():
        assert c.DEV_BOX, 'attraction_notifications is only available on dev boxes'
        Session.initialize_db(initialize=True)
        with Session() as session:
            send_attraction_notifications(session)
