import pytz

from collections import OrderedDict
from datetime import datetime, timedelta

from sideboard.lib.sa import JSON, CoerceUTF8 as UnicodeText, UTCDateTime, UUID
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import backref
from sqlalchemy.schema import ForeignKey, UniqueConstraint
from sqlalchemy.sql import text
from sqlalchemy.types import Integer

from uber.config import c
from uber.custom_tags import humanize_timedelta
from uber.decorators import validation
from uber.models import MagModel, Session
from uber.models.types import default_relationship as relationship, Choice, \
    DefaultColumn as Column, utcnow
from uber.utils import ceil_datetime, floor_datetime, noon_datetime, \
    evening_datetime


__all__ = [
    'Attraction', 'AttractionFeature', 'AttractionEvent', 'AttractionSignup']


@Session.model_mixin
class Attendee:
    attraction_signups = relationship(
        'AttractionSignup',
        backref='attendee',
        order_by='AttractionSignup.signup_time')

    @property
    def attraction_features(self):
        return list({e.feature for e in self.attraction_events})

    @property
    def attractions(self):
        return list({e.feature.attraction for e in self.attraction_events})

    def is_signed_up_for_attraction(self, attraction):
        return attraction in self.attractions

    def is_signed_up_for_attraction_feature(self, feature):
        return feature in self.attraction_features

    def can_admin_attraction(self, attraction):
        if not self.admin_account:
            return False
        return self.admin_account.id == attraction.owner_id \
            or self.can_admin_dept_for(attraction.department_id)


class Attraction(MagModel):
    NONE = 0
    PER_FEATURE = 1
    PER_ATTRACTION = 2
    RESTRICTION_OPTS = [(
        NONE,
        'None – '
        'Attendees can attend as many events as they wish '
        '(least restrictive)'
    ), (
        PER_FEATURE,
        'Once Per Feature – '
        'Attendees can only attend each feature once'
    ), (
        PER_ATTRACTION,
        'Once Per Attraction – '
        'Attendees can only attend this attraction once '
        '(most restrictive)'
    )]
    RESTRICTIONS = dict(RESTRICTION_OPTS)

    REQUIRED_CHECKIN_OPTS = [
        (-1, 'Anytime during event'),
        (0, 'When the event starts'),
        (300, '5 minutes before'),
        (600, '10 minutes before'),
        (900, '15 minutes before'),
        (1200, '20 minutes before'),
        (1800, '30 minutes before'),
        (2700, '45 minutes before'),
        (3600, '1 hour before')]

    NOTIFICATIONS_OPTS = [
        ('', 'Never'),
        (0, 'When the event starts'),
        (300, '5 minutes before'),
        (900, '15 minutes before'),
        (1800, '30 minutes before'),
        (3600, '1 hour before'),
        (7200, '2 hours before'),
        (86400, '1 day before')]

    name = Column(UnicodeText, unique=True)
    description = Column(UnicodeText)
    notifications = Column(JSON, default=[], server_default='[]')
    required_checkin = Column(Integer, default=0)  # In seconds
    restriction = Column(Choice(RESTRICTION_OPTS), default=NONE)
    department_id = Column(UUID, ForeignKey('department.id'), nullable=True)
    owner_id = Column(UUID, ForeignKey('admin_account.id'))

    owner = relationship(
        'AdminAccount',
        cascade='save-update,merge',
        backref=backref(
            'attractions',
            cascade='all,delete-orphan',
            uselist=True,
            order_by='Attraction.name'))
    department = relationship(
        'Department',
        cascade='save-update,merge',
        backref=backref(
            'attractions',
            cascade='save-update,merge',
            uselist=True),
        order_by='Department.name')
    features = relationship(
        'AttractionFeature',
        backref='attraction',
        order_by='[AttractionFeature.name, AttractionFeature.id]')
    events = relationship(
        'AttractionEvent',
        cascade='save-update,merge',
        secondary='attraction_feature',
        viewonly=True,
        order_by='[AttractionEvent.start_time, AttractionEvent.id]')

    @property
    def feature_opts(self):
        return [(f.id, f.name) for f in self.features]

    @property
    def feature_names_by_id(self):
        return OrderedDict(self.feature_opts)

    @property
    def used_location_opts(self):
        locs = set(e.location for e in self.events)
        sorted_locs = sorted(locs, key=lambda l: c.EVENT_LOCATIONS[l])
        return [(l, c.EVENT_LOCATIONS[l]) for l in sorted_locs]

    @property
    def unused_location_opts(self):
        locs = set(e.location for e in self.events)
        return [(l, s) for l, s in c.EVENT_LOCATION_OPTS if l not in locs]

    @property
    def required_checkin_label(self):
        if self.required_checkin < 0:
            return 'anytime during the event'
        return humanize_timedelta(
            seconds=self.required_checkin,
            separator=' ',
            now='by the time the event starts',
            prefix='at least ',
            suffix=' before the event starts')

    @property
    def location_opts(self):
        locations = map(
            lambda e: (e.location, c.EVENT_LOCATIONS[e.location]), self.events)
        return [(l, s) for l, s in sorted(locations, key=lambda l: l[1])]

    @property
    def locations(self):
        return OrderedDict(self.location_opts)

    @property
    def locations_by_feature_id(self):
        locations_by_feature_id = OrderedDict()
        for feature in self.features:
            locations_by_feature_id[feature.id] = feature.locations
        return locations_by_feature_id

    @property
    def events_by_feature(self):
        events_by_feature = OrderedDict()
        for feature in self.features:
            events_by_feature[feature] = feature.events_by_location
        return events_by_feature


class AttractionFeature(MagModel):
    name = Column(UnicodeText)
    description = Column(UnicodeText)
    attraction_id = Column(UUID, ForeignKey('attraction.id'))

    events = relationship(
        'AttractionEvent',
        backref='feature',
        order_by='[AttractionEvent.start_time, AttractionEvent.id]')

    __table_args__ = (UniqueConstraint('name', 'attraction_id'),)

    @property
    def location_opts(self):
        locations = map(
            lambda e: (e.location, c.EVENT_LOCATIONS[e.location]), self.events)
        return [(l, s) for l, s in sorted(locations, key=lambda l: l[1])]

    @property
    def locations(self):
        return OrderedDict(self.location_opts)

    @property
    def events_by_location(self):
        events = sorted(
            self.events,
            key=lambda e: (c.EVENT_LOCATIONS[e.location], e.start_time))
        events_by_location = OrderedDict()
        for event in events:
            if event.location not in events_by_location:
                events_by_location[event.location] = []
            events_by_location[event.location].append(event)
        return events_by_location

    @property
    def available_events(self):
        return [
            e for e in self.events if not (e.is_started and e.is_checkin_over)]

    @property
    def available_events_summary(self):
        summary = OrderedDict()
        for event in self.available_events:
            start_time = event.start_time_local
            day = start_time.strftime('%A')
            if day not in summary:
                summary[day] = OrderedDict()

            time_of_day = 'Evening'
            if start_time < noon_datetime(start_time):
                time_of_day = 'Morning'
            elif start_time < evening_datetime(start_time):
                time_of_day = 'Afternoon'
            if time_of_day not in summary[day]:
                summary[day][time_of_day] = 0

            summary[day][time_of_day] += event.remaining_slots

        return summary

    @property
    def available_events_by_day(self):
        events_by_day = OrderedDict()
        for event in self.available_events:
            start_time = event.start_time_local
            day = start_time.strftime('%A')
            if day not in events_by_day:
                events_by_day[day] = []
            events_by_day[day].append(event)
        return events_by_day


# =====================================================================
# TODO: This, along with the panels.models.Event class, should be
#       refactored into a more generic "SchedulableMixin". Any model
#       class that has a location, a start time, and a duration would
#       inherit from the SchedulableMixin. Unfortunately the
#       panels.models.Event stores its duration as an integer number
#       of whole minutes, thus is not usable by Attractions.
# =====================================================================
class AttractionEvent(MagModel):
    attraction_feature_id = Column(UUID, ForeignKey('attraction_feature.id'))
    location = Column(Choice(c.EVENT_LOCATION_OPTS))
    start_time = Column(UTCDateTime, default=c.EPOCH)
    duration = Column(Integer, default=900)  # In seconds
    slots = Column(Integer, default=1)

    signups = relationship(
        'AttractionSignup',
        backref='event',
        order_by='AttractionSignup.signup_time')

    attendees = relationship(
        'Attendee',
        backref='attraction_events',
        cascade='save-update,merge,refresh-expire,expunge',
        secondary='attraction_signup',
        order_by='attraction_signup.c.signup_time')

    @hybrid_property
    def end_time(self):
        return self.start_time + timedelta(seconds=self.duration)

    @end_time.expression
    def end_time(cls):
        return cls.start_time + (cls.duration * text("interval '1 second'"))

    @property
    def end_time_local(self):
        return self.end_time.astimezone(c.EVENT_TIMEZONE)

    @property
    def start_time_local(self):
        return self.start_time.astimezone(c.EVENT_TIMEZONE)

    @property
    def start_time_label(self):
        if self.start_time:
            return self.start_time_local.strftime('%-I:%M %p %A')
        return 'unknown start time'

    @property
    def checkin_time(self):
        required_checkin = self.attraction.required_checkin
        if required_checkin < 0:
            return self.end_time_local
        else:
            return self.start_time_local - timedelta(seconds=required_checkin)

    @property
    def is_checkin_over(self):
        return self.checkin_time < datetime.utcnow().replace(tzinfo=pytz.UTC)

    @property
    def is_sold_out(self):
        return self.slots <= len(self.attendees)

    @property
    def is_started(self):
        return self.start_time < datetime.utcnow().replace(tzinfo=pytz.UTC)

    @property
    def remaining_slots(self):
        return max(self.slots - len(self.attendees), 0)

    @property
    def time_span_label(self):
        if self.start_time:
            end_time = self.end_time.astimezone(c.EVENT_TIMEZONE)
            end_day = end_time.strftime('%A')
            start_time = self.start_time.astimezone(c.EVENT_TIMEZONE)
            start_day = start_time.strftime('%A')
            if start_day == end_day:
                return '{} – {} {}'.format(
                    start_time.strftime('%-I:%M %p'),
                    end_time.strftime('%-I:%M %p'),
                    end_day)
            return '{} – {}'.format(
                start_time.strftime('%-I:%M %p %A'),
                end_time.strftime('%-I:%M %p %A'))
        return 'unknown time span'

    @property
    def duration_label(self):
        if self.duration:
            return humanize_timedelta(seconds=self.duration, separator=' ')
        return 'unknown duration'

    @property
    def name(self):
        return self.feature.name

    @property
    def label(self):
        return '{} at {}'.format(self.name, self.start_time_label)

    def overlap(self, event):
        if not event:
            return 0
        latest_start = max(self.start_time, event.start_time)
        earliest_end = min(self.end_time, event.end_time)
        if earliest_end < latest_start:
            return -int((latest_start - earliest_end).total_seconds())
        elif self.start_time < event.start_time \
                and self.end_time > event.end_time:
            return int((self.end_time - event.start_time).total_seconds())
        elif self.start_time > event.start_time \
                and self.end_time < event.end_time:
            return int((event.end_time - self.start_time).total_seconds())
        else:
            return int((earliest_end - latest_start).total_seconds())


class AttractionSignup(MagModel):
    attraction_event_id = Column(UUID, ForeignKey('attraction_event.id'))
    attendee_id = Column(UUID, ForeignKey('attendee.id'))

    signup_time = Column(UTCDateTime, server_default=utcnow())
    checkin_time = Column(UTCDateTime, nullable=True)

    __mapper_args__ = {'confirm_deleted_rows': False}
    __table_args__ = (UniqueConstraint('attraction_event_id', 'attendee_id'),)


Attraction.required = [('name', 'Name'), ('description', 'Description')]
AttractionFeature.required = [('name', 'Name'), ('description', 'Description')]


@validation.AttractionEvent
def at_least_one_slot(event):
    if event.slots < 1:
        return 'Events must have at least one slot.'
