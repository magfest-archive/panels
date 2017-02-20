from panels import *


Event.required = [('name', 'Event Name')]


@validation.Event
def overlapping_events(event, other_event_id=None):
    existing = {}
    for e in event.session.query(Event).filter(Event.location == event.location,
                                               Event.id != event.id,
                                               Event.id != other_event_id).all():
        for hh in e.half_hours:
            existing[hh] = e.name

    for hh in event.half_hours:
        if hh in existing:
            return '"{}" overlaps with the time/duration you specified for "{}"'.format(existing[hh], event.name)


PanelApplication.required = [
    ('name', 'Panel Name'),
    ('description', 'Panel Description'),
    ('length', 'Panel Length'),
    ('unavailable', 'Your unavailability'),
]
PanelApplicant.required = [
    ('first_name', 'First Name'),
    ('last_name', 'Last Name'),
    ('email', 'Email'),
]


@validation.PanelApplicant
def pa_email(pa):
    if not re.match(c.EMAIL_RE, pa.email):
        return 'Please enter a valid email address'


@validation.PanelApplicant
def pa_phone(pa):
    from uber.model_checks import _invalid_phone_number
    if (pa.submitter or pa.cellphone) and _invalid_phone_number(pa.cellphone):
        return 'Please enter a valid phone number'


@validation.PanelApplication
def pa_other(pa):
    if pa.presentation == c.OTHER and not pa.other_presentation:
        return 'Since you selected "Other" for your type of panel, please describe it'


@validation.PanelApplication
def pa_deadline(pa):
    if localized_now() > c.PANEL_APP_DEADLINE and not c.HAS_PANEL_APPS_ACCESS:
        return 'We are now past the deadline and are no longer accepting panel applications'
