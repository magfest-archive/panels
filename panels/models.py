from panels import *
from panels.config import panels_config as config


def url_domain(url):
    url = url.strip().replace('//', '/')
    url = re.sub(r'^https?:/', '', url)
    url = re.sub(r'^www\.', '', url)
    return url.split('/', 1)[0].strip('@#?=. ')


@Session.model_mixin
class SessionMixin:
    def panel_apps(self):
        return self.query(PanelApplication).order_by('applied').all()

    def panel_applicants(self):
        return self.query(PanelApplicant).options(joinedload(PanelApplicant.application)).order_by('first_name', 'last_name')


class SocialMediaMixin(JSONColumnMixin('social_media', c.SOCIAL_MEDIA)):
    _social_media_urls = config.get('social_media_urls', {})
    _social_media_placeholders = config.get('social_media_placeholders', {})

    @classmethod
    def get_placeholder(cls, name):
        name = cls.unqualify(name)
        return cls._social_media_placeholders.get(name, '')

    @property
    def has_social_media(self):
        return any(getattr(self, f) for f in self._social_media_fields.keys())

    def __getattr__(self, name):
        if name.endswith('_url'):
            field_name = self.unqualify(name[:-4])
            if field_name in self._social_media_fields:
                attr = super(SocialMediaMixin, self).__getattr__(field_name)
                attr = attr.strip('@#?=. ') if attr else ''
                if attr:
                    if attr.startswith('http:') or attr.startswith('https:'):
                        return attr
                    else:
                        url = self._social_media_urls.get(field_name, '{}')
                        if url_domain(url.format('')) in url_domain(attr):
                            return attr
                        return url.format(attr)
                return ''
            else:
                return super(SocialMediaMixin, self).__getattr__(name)
        elif name.endswith('_placeholder'):
            return self.get_placeholder(name[:-12])
        else:
            return super(SocialMediaMixin, self).__getattr__(name)


@Session.model_mixin
class Attendee:
    assigned_panelists = relationship('AssignedPanelist', backref='attendee')
    panel_applicants = relationship('PanelApplicant', backref='attendee')
    panel_applications = relationship('PanelApplication', backref='poc')
    panel_feedback = relationship('EventFeedback', backref='attendee')


class Event(MagModel):
    location    = Column(Choice(c.EVENT_LOCATION_OPTS))
    start_time  = Column(UTCDateTime)
    duration    = Column(Integer)   # half-hour increments
    name        = Column(UnicodeText, nullable=False)
    description = Column(UnicodeText)

    assigned_panelists = relationship('AssignedPanelist', backref='event')
    applications = relationship('PanelApplication', backref='event')
    panel_feedback = relationship('EventFeedback', backref='event')

    @property
    def half_hours(self):
        half_hours = set()
        for i in range(self.duration):
            half_hours.add(self.start_time + timedelta(minutes=30 * i))
        return half_hours

    @property
    def minutes(self):
        return (self.duration or 0) * 30

    @property
    def start_slot(self):
        if self.start_time:
            return int((self.start_time_local - c.EPOCH).total_seconds() / (60 * 30))

    @property
    def end_time(self):
        return self.start_time + timedelta(minutes=self.minutes)


class AssignedPanelist(MagModel):
    attendee_id = Column(UUID, ForeignKey('attendee.id', ondelete='cascade'))
    event_id    = Column(UUID, ForeignKey('event.id', ondelete='cascade'))

    def __repr__(self):
        return '<{self.attendee.full_name} panelisting {self.event.name}>'.format(self=self)


class PanelApplication(MagModel):
    event_id = Column(UUID, ForeignKey('event.id', ondelete='SET NULL'), nullable=True)
    poc_id = Column(UUID, ForeignKey('attendee.id', ondelete='SET NULL'), nullable=True)

    name = Column(UnicodeText)
    length = Column(Choice(c.PANEL_LENGTH_OPTS), default=c.SIXTY_MIN)
    length_text = Column(UnicodeText)
    length_reason = Column(UnicodeText)
    description = Column(UnicodeText)
    unavailable = Column(UnicodeText)
    available = Column(UnicodeText)
    affiliations = Column(UnicodeText)
    past_attendance = Column(UnicodeText)

    presentation = Column(Choice(c.PRESENTATION_OPTS))
    other_presentation = Column(UnicodeText)
    tech_needs = Column(MultiChoice(c.TECH_NEED_OPTS))
    other_tech_needs = Column(UnicodeText)
    need_tables = Column(Boolean, default=False)
    tables_desc = Column(UnicodeText)
    has_cost = Column(Boolean, default=False)
    cost_desc = Column(UnicodeText)
    livestream = Column(Choice(c.LIVESTREAM_OPTS), default=c.DONT_CARE)
    panelist_bringing = Column(UnicodeText)
    extra_info = Column(UnicodeText)

    applied = Column(UTCDateTime, server_default=utcnow())

    status = Column(Choice(c.PANEL_APP_STATUS_OPTS), default=c.PENDING, admin_only=True)
    comments = Column(UnicodeText, admin_only=True)

    applicants = relationship('PanelApplicant', backref='application')

    email_model_name = 'app'

    @property
    def email(self):
        return self.submitter and self.submitter.email

    @property
    def submitter(self):
        for a in self.applicants:
            if a.submitter:
                return a
        return None

    @property
    def other_panelists(self):
        return [a for a in self.applicants if not a.submitter]

    @property
    def matched_attendees(self):
        return [a.attendee for a in self.applicants if a.attendee_id]

    @property
    def unmatched_applicants(self):
        return [a for a in self.applicants if not a.attendee_id]


class PanelApplicant(SocialMediaMixin, MagModel):
    app_id = Column(UUID, ForeignKey('panel_application.id', ondelete='cascade'))
    attendee_id = Column(UUID, ForeignKey('attendee.id', ondelete='cascade'), nullable=True)

    submitter  = Column(Boolean, default=False)
    first_name = Column(UnicodeText)
    last_name  = Column(UnicodeText)
    email      = Column(UnicodeText)
    cellphone  = Column(UnicodeText)
    communication_pref = Column(MultiChoice(c.COMMUNICATION_PREF_OPTS))
    other_communication_pref = Column(UnicodeText)

    occupation = Column(UnicodeText)
    website = Column(UnicodeText)
    other_credentials = Column(UnicodeText)

    @property
    def has_credentials(self):
        return any([self.occupation, self.website, self.other_credentials])

    @property
    def full_name(self):
        return self.first_name + ' ' + self.last_name


class EventFeedback(MagModel):
    event_id = Column(UUID, ForeignKey('event.id'))
    attendee_id = Column(UUID, ForeignKey('attendee.id', ondelete='cascade'))
    headcount_starting = Column(Integer, default=0)
    headcount_during = Column(Integer, default=0)
    comments = Column(UnicodeText)
    rating = Column(Choice(c.PANEL_RATING_OPTS), default=c.UNRATED)
