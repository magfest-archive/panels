import math
import pytz
import re
import string

from collections import OrderedDict, defaultdict
from datetime import datetime, timedelta

from sideboard.lib import listify
from sideboard.lib.sa import JSON, CoerceUTF8 as UnicodeText, UTCDateTime, UUID
from sqlalchemy import and_, exists, func, or_, select, text, union, not_, cast, alias
from sqlalchemy.ext.associationproxy import association_proxy
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import backref
from sqlalchemy.orm.query import Query
from sqlalchemy.schema import ForeignKey, ForeignKeyConstraint, Index, \
    UniqueConstraint
from sqlalchemy.sql import text
from sqlalchemy.sql.expression import bindparam
from sqlalchemy.types import Boolean, Integer

from uber.config import c
from uber.custom_tags import humanize_timedelta, location_event_name, \
    location_room_name
from uber.decorators import presave_adjustment, validation
from uber.models import MagModel, Session
from uber.models.types import default_relationship as relationship, Choice, \
    DefaultColumn as Column, utcmin, utcnow
from uber.utils import noon_datetime, evening_datetime


__all__ = [
    'Attraction', 'AttractionFeature', 'AttractionEvent', 'AttractionSignup',
    'AttractionNotification', 'AttractionNotificationReply', 'filename_safe',
    'groupify', 'sluggify']


def groupify(items, keys, val_key=None):
    """
    Groups a list of items into nested OrderedDicts based on the given keys.

    `keys` may be a string, a callable, or a list thereof.

    `val_key` may be `None`, a string, or a callable. Defaults to `None`.

    Examples::

        >>> from json import dumps
        >>>
        >>> class Reminder:
        ...   def __init__(self, when, where, what):
        ...     self.when = when
        ...     self.where = where
        ...     self.what = what
        ...   def __repr__(self):
        ...     return 'Reminder({0.when}, {0.where}, {0.what})'.format(self)
        ...
        >>> reminders = [
        ...   Reminder('Fri', 'Home', 'Eat cereal'),
        ...   Reminder('Fri', 'Work', 'Feed Ivan'),
        ...   Reminder('Sat', 'Home', 'Sleep in'),
        ...   Reminder('Sat', 'Home', 'Play Zelda'),
        ...   Reminder('Sun', 'Home', 'Sleep in'),
        ...   Reminder('Sun', 'Work', 'Reset database')]
        >>>
        >>> print(dumps(groupify(reminders, None), indent=2, default=repr))
        ... [
        ...   "Reminder(Fri, Home, Eat cereal)",
        ...   "Reminder(Fri, Work, Feed Ivan)",
        ...   "Reminder(Sat, Home, Sleep in)",
        ...   "Reminder(Sat, Home, Play Zelda)",
        ...   "Reminder(Sun, Home, Sleep in)",
        ...   "Reminder(Sun, Work, Reset database)"
        ... ]
        >>>
        >>> print(dumps(groupify(reminders, 'when'), indent=2, default=repr))
        ... {
        ...   "Fri": [
        ...     "Reminder(Fri, Home, Eat cereal)",
        ...     "Reminder(Fri, Work, Feed Ivan)"
        ...   ],
        ...   "Sat": [
        ...     "Reminder(Sat, Home, Sleep in)",
        ...     "Reminder(Sat, Home, Play Zelda)"
        ...   ],
        ...   "Sun": [
        ...     "Reminder(Sun, Home, Sleep in)",
        ...     "Reminder(Sun, Work, Reset database)"
        ...   ]
        ... }
        >>>
        >>> print(dumps(groupify(reminders, ['when', 'where']),
        ...             indent=2, default=repr))
        ... {
        ...   "Fri": {
        ...     "Home": [
        ...       "Reminder(Fri, Home, Eat cereal)"
        ...     ],
        ...     "Work": [
        ...       "Reminder(Fri, Work, Feed Ivan)"
        ...     ]
        ...   },
        ...   "Sat": {
        ...     "Home": [
        ...       "Reminder(Sat, Home, Sleep in)",
        ...       "Reminder(Sat, Home, Play Zelda)"
        ...     ]
        ...   },
        ...   "Sun": {
        ...     "Home": [
        ...       "Reminder(Sun, Home, Sleep in)"
        ...     ],
        ...     "Work": [
        ...       "Reminder(Sun, Work, Reset database)"
        ...     ]
        ...   }
        ... }
        >>>
        >>> print(dumps(groupify(reminders, ['when', 'where'], 'what'),
        ...             indent=2))
        ... {
        ...   "Fri": {
        ...     "Home": [
        ...       "Eat cereal"
        ...     ],
        ...     "Work": [
        ...       "Feed Ivan"
        ...     ]
        ...   },
        ...   "Sat": {
        ...     "Home": [
        ...       "Sleep in",
        ...       "Play Zelda"
        ...     ]
        ...   },
        ...   "Sun": {
        ...     "Home": [
        ...       "Sleep in"
        ...     ],
        ...     "Work": [
        ...       "Reset database"
        ...     ]
        ...   }
        ... }
        >>>
        >>> print(dumps(groupify(reminders,
        ...                      lambda r: '{0.when} - {0.where}'.format(r),
        ...                      'what'), indent=2))
        ... {
        ...   "Fri - Home": [
        ...     "Eat cereal"
        ...   ],
        ...   "Fri - Work": [
        ...     "Feed Ivan"
        ...   ],
        ...   "Sat - Home": [
        ...     "Sleep in",
        ...     "Play Zelda"
        ...   ],
        ...   "Sun - Home": [
        ...     "Sleep in"
        ...   ],
        ...   "Sun - Work": [
        ...     "Reset database"
        ...   ]
        ... }
        >>>

    """
    if not keys:
        return items
    keys = listify(keys)
    last_key = keys[-1]
    call_val_key = callable(val_key)
    groupified = OrderedDict()
    for item in items:
        current = groupified
        for key in keys:
            attr = key(item) if callable(key) else getattr(item, key)
            if attr not in current:
                current[attr] = [] if key is last_key else OrderedDict()
            current = current[attr]
        if val_key:
            value = val_key(item) if call_val_key else getattr(item, val_key)
        else:
            value = item
        current.append(value)
    return groupified


def mask(s, mask_char='*', min_unmask=1, max_unmask=2):
    """
    Masks the trailing portion of the given string with asterisks.

    The number of unmasked characters will never be less than `min_unmask` or
    greater than `max_unmask`. Within those bounds, the number of unmasked
    characters always be smaller than half the length of `s`.

    Example::

        >>> for i in range(0, 12):
        ...     mask('A' * i, min_unmask=1, max_unmask=4)
        ... ''
        ... 'A'
        ... 'A*'
        ... 'A**'
        ... 'A***'
        ... 'AA***'
        ... 'AA****'
        ... 'AAA****'
        ... 'AAA*****'
        ... 'AAAA*****'
        ... 'AAAA******'
        ... 'AAAA*******'
        >>>

    Arguments:
        s (str): The string to be masked.
        mask_char (str): The character that should be used as the mask.
            Defaults to an asterisk "*".
        min_unmask (int): Defines the minimum number of characters that are
            allowed to be unmasked. If the length of `s` is less than or equal
            to `min_unmask`, then `s` is returned unmodified. Defaults to 1.
        max_unmask (int): Defines the maximum number of characters that are
            allowed to be unmasked. Defaults to 2.

    Returns:
        str: A copy of `s` with a portion of the string masked by `mask_char`.
    """
    s_len = len(s)
    if s_len <= min_unmask:
        return s
    elif s_len <= (2 * max_unmask):
        unmask = max(min_unmask, math.ceil(s_len / 2) - 1)
        return s[:unmask] + (mask_char * (s_len - unmask))
    return s[:max_unmask] + (mask_char * (s_len - max_unmask))


RE_NONDIGIT = re.compile(r'\D+')
RE_SLUG = re.compile(r'[\W_]+')


def sluggify(s):
    return RE_SLUG.sub('-', s).lower().strip('-')


def filename_safe(s):
    """
    Adapted from https://gist.github.com/seanh/93666

    Take a string and return a valid filename constructed from the string.
    Uses a whitelist approach: any characters not present in valid_chars are
    removed. Also spaces are replaced with underscores.

    Note: this method may produce invalid filenames such as ``, `.` or `..`
    When I use this method I prepend a date string like '2009_01_15_19_46_32_'
    and append a file extension like '.txt', so I avoid the potential of using
    an invalid filename.

    """
    valid_chars = '-_.() {}{}'.format(string.ascii_letters, string.digits)
    filename = ''.join(c for c in s if c in valid_chars)
    return filename.replace(' ', '_')


@Session.model_mixin
class Attendee:
    NOTIFICATION_EMAIL = 0
    NOTIFICATION_TEXT = 1
    NOTIFICATION_NONE = 2
    NOTIFICATION_PREF_OPTS = [
        (NOTIFICATION_EMAIL, 'Email'),
        (NOTIFICATION_TEXT, 'Text'),
        (NOTIFICATION_NONE, 'None')]

    notification_pref = Column(
        Choice(NOTIFICATION_PREF_OPTS), default=NOTIFICATION_EMAIL)

    attractions_opt_out = Column(Boolean, default=False)

    attraction_signups = relationship(
        'AttractionSignup',
        backref='attendee',
        order_by='AttractionSignup.signup_time')

    attraction_event_signups = association_proxy('attraction_signups', 'event')

    attraction_notifications = relationship(
        'AttractionNotification',
        backref='attendee',
        order_by='AttractionNotification.sent_time')

    @property
    def attraction_features(self):
        return list({e.feature for e in self.attraction_events})

    @property
    def attractions(self):
        return list({e.feature.attraction for e in self.attraction_events})

    @property
    def masked_email(self):
        name, _, domain = self.email.partition('@')
        sub_domain, _, tld = domain.rpartition('.')
        return '{}@{}.{}'.format(mask(name), mask(sub_domain), tld)

    @property
    def masked_cellphone(self):
        cellphone = RE_NONDIGIT.sub(' ', self.cellphone).strip()
        digits = cellphone.replace(' ', '')
        return '*' * (len(cellphone) - 4) + digits[-4:]

    @property
    def masked_notification_pref(self):
        if self.notification_pref == self.NOTIFICATION_EMAIL:
            return self.masked_email
        elif self.notification_pref == self.NOTIFICATION_TEXT:
            return self.masked_cellphone or self.masked_email
        return ''

    @property
    def signups_by_attraction_by_feature(self):
        signups = sorted(self.attraction_signups, key=lambda s: (
            s.event.feature.attraction.name,
            s.event.feature.name))
        return groupify(signups, [
            lambda s: s.event.feature.attraction,
            lambda s: s.event.feature])

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

    ADVANCE_CHECKIN_OPTS = [
        (-1, 'Anytime during event'),
        (0, 'When the event starts'),
        (300, '5 minutes before'),
        (600, '10 minutes before'),
        (900, '15 minutes before'),
        (1200, '20 minutes before'),
        (1800, '30 minutes before'),
        (2700, '45 minutes before'),
        (3600, '1 hour before')]

    ADVANCE_NOTICES_OPTS = [
        ('', 'Never'),
        (0, 'When checkin starts'),
        (300, '5 minutes before checkin'),
        (900, '15 minutes before checkin'),
        (1800, '30 minutes before checkin'),
        (3600, '1 hour before checkin'),
        (7200, '2 hours before checkin'),
        (86400, '1 day before checkin')]

    name = Column(UnicodeText, unique=True)
    slug = Column(UnicodeText, unique=True)
    description = Column(UnicodeText)
    is_public = Column(Boolean, default=False)
    advance_notices = Column(JSON, default=[], server_default='[]')
    advance_checkin = Column(Integer, default=0)  # In seconds
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
    owner_attendee = relationship(
        'Attendee',
        cascade='save-update,merge',
        secondary='admin_account',
        uselist=False,
        viewonly=True)
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
    public_features = relationship(
        'AttractionFeature',
        primaryjoin='and_('
                    'AttractionFeature.attraction_id == Attraction.id,'
                    'AttractionFeature.is_public == True)',
        viewonly=True,
        order_by='[AttractionFeature.name, AttractionFeature.id]')
    events = relationship(
        'AttractionEvent',
        backref='attraction',
        viewonly=True,
        order_by='[AttractionEvent.start_time, AttractionEvent.id]')
    signups = relationship(
        'AttractionSignup',
        backref='attraction',
        viewonly=True,
        order_by='[AttractionSignup.checkin_time, AttractionSignup.id]')

    @presave_adjustment
    def _sluggify_name(self):
        self.slug = sluggify(self.name)

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
    def advance_checkin_label(self):
        if self.advance_checkin < 0:
            return 'anytime during the event'
        return humanize_timedelta(
            seconds=self.advance_checkin,
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
        return groupify(self.features, 'id', lambda f: f.locations)

    def signups_requiring_notification(
            self, session, from_time, to_time, options=None):
        """
        Returns a dict of AttractionSignups that require notification.

        The keys of the returned dict are the amount of advanced notice, given
        in seconds. A key of -1 indicates confirmation notices after a signup.

        The query generated by this method looks horrific, but is surprisingly
        efficient.
        """
        advance_checkin = max(0, self.advance_checkin)
        subqueries = []
        for advance_notice in sorted(set([-1] + self.advance_notices)):
            event_filters = [AttractionEvent.attraction_id == self.id]
            if advance_notice == -1:
                notice_ident = cast(
                    AttractionSignup.attraction_event_id, UnicodeText)
                notice_param = bindparam(
                    'confirm_notice', advance_notice).label('advance_notice')
            else:
                advance_notice = max(0, advance_notice) + advance_checkin
                notice_delta = timedelta(seconds=advance_notice)
                event_filters += [
                    AttractionEvent.start_time >= from_time + notice_delta,
                    AttractionEvent.start_time < to_time + notice_delta]
                notice_ident = func.concat(
                    AttractionSignup.attraction_event_id,
                    '_{}'.format(advance_notice))
                notice_param = bindparam(
                    'advance_notice_{}'.format(advance_notice),
                    advance_notice).label('advance_notice')

            subquery = session.query(AttractionSignup, notice_param).filter(
                AttractionSignup.is_unchecked_in,
                AttractionSignup.attraction_event_id.in_(
                    session.query(AttractionEvent.id).filter(*event_filters)),
                not_(exists().where(and_(
                    AttractionNotification.ident == notice_ident,
                    AttractionNotification.attraction_event_id
                        == AttractionSignup.attraction_event_id,
                    AttractionNotification.attendee_id
                        == AttractionSignup.attendee_id)))).with_labels()
            subqueries.append(subquery)

        query = subqueries[0].union(*subqueries[1:])
        if options:
            query = query.options(*listify(options))
        query.order_by(AttractionSignup.id)
        return groupify(query, lambda x: x[0], lambda x: x[1])


class AttractionFeature(MagModel):
    name = Column(UnicodeText)
    slug = Column(UnicodeText)
    description = Column(UnicodeText)
    is_public = Column(Boolean, default=False)
    attraction_id = Column(UUID, ForeignKey('attraction.id'))

    events = relationship(
        'AttractionEvent',
        backref='feature',
        order_by='[AttractionEvent.start_time, AttractionEvent.id]')

    __table_args__ = (
        UniqueConstraint('name', 'attraction_id'),
        UniqueConstraint('slug', 'attraction_id'),
    )

    @presave_adjustment
    def _sluggify_name(self):
        self.slug = sluggify(self.name)

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
        return groupify(events, 'location')

    @property
    def events_by_location_by_day(self):
        events = sorted(
            self.events,
            key=lambda e: (c.EVENT_LOCATIONS[e.location], e.start_time))
        return groupify(events, ['location', 'start_day_local'])

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
        return groupify(self.available_events, 'start_day_local')


# =====================================================================
# TODO: This, along with the panels.models.Event class, should be
#       refactored into a more generic "SchedulableMixin". Any model
#       class that has a location, a start time, and a duration would
#       inherit from the SchedulableMixin. Unfortunately the
#       panels.models.Event stores its duration as an integer number
#       of half hours, thus is not usable by Attractions.
# =====================================================================
class AttractionEvent(MagModel):
    attraction_feature_id = Column(UUID, ForeignKey('attraction_feature.id'))
    attraction_id = Column(UUID, ForeignKey('attraction.id'), index=True)

    location = Column(Choice(c.EVENT_LOCATION_OPTS))
    start_time = Column(UTCDateTime, default=c.EPOCH)
    duration = Column(Integer, default=900)  # In seconds
    slots = Column(Integer, default=1)

    signups = relationship(
        'AttractionSignup',
        backref='event',
        order_by='AttractionSignup.checkin_time')

    attendee_signups = association_proxy('signups', 'attendee')

    notifications = relationship(
        'AttractionNotification',
        backref='event',
        order_by='AttractionNotification.sent_time')

    notification_replies = relationship(
        'AttractionNotificationReply',
        backref='event',
        order_by='AttractionNotificationReply.sid')

    attendees = relationship(
        'Attendee',
        backref='attraction_events',
        cascade='save-update,merge,refresh-expire,expunge',
        secondary='attraction_signup',
        order_by='attraction_signup.c.signup_time')

    @presave_adjustment
    def _fix_attraction_id(self):
        if not self.attraction_id and self.feature:
            self.attraction_id = self.feature.attraction_id

    @classmethod
    def get_ident(cls, id, advance_notice):
        if advance_notice == -1:
            return str(id)
        return '{}_{}'.format(id, advance_notice)

    @hybrid_property
    def end_time(self):
        return self.start_time + timedelta(seconds=self.duration)

    @end_time.expression
    def end_time(cls):
        return cls.start_time + (cls.duration * text("interval '1 second'"))

    @property
    def start_day_local(self):
        return self.start_time_local.strftime('%A')

    @property
    def start_time_label(self):
        if self.start_time:
            return self.start_time_local.strftime('%-I:%M %p %A')
        return 'unknown start time'

    @property
    def checkin_start_time(self):
        advance_checkin = self.attraction.advance_checkin
        if advance_checkin < 0:
            return self.start_time
        else:
            return self.start_time - timedelta(seconds=advance_checkin)

    @property
    def checkin_end_time(self):
        advance_checkin = self.attraction.advance_checkin
        if advance_checkin < 0:
            return self.end_time
        else:
            return self.start_time

    @property
    def checkin_start_time_label(self):
        checkin = self.checkin_start_time_local
        today = datetime.now(c.EVENT_TIMEZONE).date()
        if checkin.date() == today:
            return checkin.strftime('%-I:%M %p')
        return checkin.strftime('%-I:%M %p %a')

    @property
    def checkin_end_time_label(self):
        checkin = self.checkin_end_time_local
        today = datetime.now(c.EVENT_TIMEZONE).date()
        if checkin.date() == today:
            return checkin.strftime('%-I:%M %p')
        return checkin.strftime('%-I:%M %p %a')

    @property
    def time_remaining_to_checkin(self):
        return self.checkin_start_time - datetime.now(pytz.UTC)

    @property
    def time_remaining_to_checkin_label(self):
        return humanize_timedelta(self.time_remaining_to_checkin,
                                  granularity='minutes', separator=' ')

    @property
    def is_checkin_over(self):
        return self.checkin_end_time < datetime.now(pytz.UTC)

    @property
    def is_sold_out(self):
        return self.slots <= len(self.attendees)

    @property
    def is_started(self):
        return self.start_time < datetime.now(pytz.UTC)

    @property
    def remaining_slots(self):
        return max(self.slots - len(self.attendees), 0)

    @property
    def time_span_label(self):
        if self.start_time:
            end_time = self.end_time.astimezone(c.EVENT_TIMEZONE)
            start_time = self.start_time.astimezone(c.EVENT_TIMEZONE)
            if start_time.date() == end_time.date():
                return '{} – {}'.format(
                    start_time.strftime('%-I:%M %p'),
                    end_time.strftime('%-I:%M %p %A'))
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
    def location_event_name(self):
        return location_event_name(self.location)

    @property
    def location_room_name(self):
        return location_room_name(self.location)

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
    attraction_id = Column(UUID, ForeignKey('attraction.id'))
    attendee_id = Column(UUID, ForeignKey('attendee.id'))

    signup_time = Column(UTCDateTime, default=lambda: datetime.now(pytz.UTC))
    checkin_time = Column(
        UTCDateTime, default=lambda: utcmin.datetime, index=True)

    notifications = relationship(
        'AttractionNotification',
        cascade='save-update, merge, refresh-expire, expunge',
        backref=backref(
            'signup',
            cascade='save-update,merge',
            uselist=False,
            viewonly=True),
        primaryjoin='and_('
                    'AttractionSignup.attendee_id'
                    ' == foreign(AttractionNotification.attendee_id),'
                    'AttractionSignup.attraction_event_id'
                    ' == foreign(AttractionNotification.attraction_event_id))',
        order_by='AttractionNotification.sent_time',
        viewonly=True)

    __mapper_args__ = {'confirm_deleted_rows': False}
    __table_args__ = (UniqueConstraint('attraction_event_id', 'attendee_id'),)

    def __init__(self, attendee=None, event=None, **kwargs):
        super(AttractionSignup, self).__init__(**kwargs)
        if attendee:
            self.attendee = attendee
        if event:
            self.event = event
        if not self.attraction_id and self.event:
            self.attraction_id = self.event.attraction_id

    @presave_adjustment
    def _fix_attraction_id(self):
        if not self.attraction_id and self.event:
            self.attraction_id = self.event.attraction_id

    @property
    def checkin_time_local(self):
        if self.is_checked_in:
            return self.checkin_time.astimezone(c.EVENT_TIMEZONE)
        return None

    @property
    def checkin_time_label(self):
        if self.is_checked_in:
            return self.checkin_time_local.strftime('%-I:%M %p %A')
        return 'Not checked in'

    @property
    def signup_time_label(self):
        return self.signup_time_local.strftime('%-I:%M %p %A')

    @property
    def email(self):
        return self.attendee.email

    @property
    def email_model_name(self):
        return 'signup'

    @hybrid_property
    def is_checked_in(self):
        return self.checkin_time > utcmin.datetime

    @is_checked_in.expression
    def is_checked_in(cls):
        return cls.checkin_time > utcmin.datetime

    @hybrid_property
    def is_unchecked_in(self):
        return self.checkin_time <= utcmin.datetime

    @is_unchecked_in.expression
    def is_unchecked_in(cls):
        return cls.checkin_time <= utcmin.datetime


class AttractionNotification(MagModel):
    attraction_event_id = Column(UUID, ForeignKey('attraction_event.id'))
    attraction_id = Column(UUID, ForeignKey('attraction.id'))
    attendee_id = Column(UUID, ForeignKey('attendee.id'))

    notification_type = Column(Choice(Attendee.NOTIFICATION_PREF_OPTS))
    ident = Column(UnicodeText, index=True)
    sid = Column(UnicodeText)
    sent_time = Column(UTCDateTime, default=lambda: datetime.now(pytz.UTC))
    subject = Column(UnicodeText)
    body = Column(UnicodeText)

    @presave_adjustment
    def _fix_attraction_id(self):
        if not self.attraction_id and self.event:
            self.attraction_id = self.event.attraction_id


class AttractionNotificationReply(MagModel):
    attraction_event_id = Column(
        UUID, ForeignKey('attraction_event.id'), nullable=True)
    attraction_id = Column(UUID, ForeignKey('attraction.id'), nullable=True)
    attendee_id = Column(UUID, ForeignKey('attendee.id'), nullable=True)

    notification_type = Column(Choice(Attendee.NOTIFICATION_PREF_OPTS))
    from_phonenumber = Column(UnicodeText)
    to_phonenumber = Column(UnicodeText)
    sid = Column(UnicodeText, index=True)
    received_time = Column(UTCDateTime, default=lambda: datetime.now(pytz.UTC))
    sent_time = Column(UTCDateTime, default=lambda: datetime.now(pytz.UTC))
    body = Column(UnicodeText)

    @presave_adjustment
    def _fix_attraction_id(self):
        if not self.attraction_id and self.event:
            self.attraction_id = self.event.attraction_id
