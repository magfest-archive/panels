from panels import *


@Session.model_mixin
class Attendee:
    assigned_panelists = relationship('AssignedPanelist', backref='attendee')


@Session.model_mixin
class AdminAccount:
    panel_votes = relationship('PanelVote', backref='account')


class Event(MagModel):
    location    = Column(Choice(c.EVENT_LOCATION_OPTS))
    start_time  = Column(UTCDateTime)
    duration    = Column(Integer)   # half-hour increments
    name        = Column(UnicodeText, nullable=False)
    description = Column(UnicodeText)

    assigned_panelists = relationship('AssignedPanelist', backref='event')

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
    name = Column(UnicodeText)
    length = Column(UnicodeText)
    description = Column(UnicodeText)
    unavailable = Column(UnicodeText)
    affiliations = Column(UnicodeText)
    past_attendance = Column(UnicodeText)

    presentation = Column(Choice(c.PRESENTATION_OPTS))
    other_presentation = Column(UnicodeText)
    tech_needs = Column(MultiChoice(c.TECH_NEED_OPTS))
    other_tech_needs = Column(UnicodeText)

    applied = Column(UTCDateTime, server_default=utcnow())

    votes = relationship('PanelVote', backref='application')
    applicants = relationship('PanelApplicant', backref='application')

    @property
    def email(self):
        return self.submitter and self.submitter.email

    @property
    def submitter(self):
        try:
            [submitter] = [a for a in self.applicants if a.submitter]
        except:
            return None
        else:
            return submitter

    @cached_property
    def vote_counts(self):
        counts = defaultdict(int)
        for vote in self.votes:
            for var in c.PANEL_VOTE_VARS:
                if vote.vote == getattr(c, var):
                    counts[var.lower()] += 1
        return counts


class PanelApplicant(MagModel):
    app_id = Column(UUID, ForeignKey('panel_application.id', ondelete='cascade'))

    submitter  = Column(Boolean, default=False)
    first_name = Column(UnicodeText)
    last_name  = Column(UnicodeText)
    email      = Column(UnicodeText)
    cellphone  = Column(UnicodeText)


class PanelVote(MagModel):
    app_id = Column(UUID, ForeignKey('panel_application.id', ondelete='cascade'))
    account_id = Column(UUID, ForeignKey('admin_account.id', ondelete='cascade'))
    vote = Column(Choice(c.PANEL_VOTE_OPTS))
