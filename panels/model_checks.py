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
    ('length', 'Panel Length')
]
PanelApplicant.required = [
    ('first_name', 'First Name'),
    ('last_name', 'Last Name'),
    ('email', 'Email'),
]


@validation.PanelApplicant
def pa_email(pa):
    if not pa.email or not re.match(c.EMAIL_RE, pa.email):
        return 'Please enter a valid email address'


@validation.PanelApplicant
def pa_phone(pa):
    from uber.model_checks import _invalid_phone_number
    if (pa.submitter or pa.cellphone) and _invalid_phone_number(pa.cellphone):
        return 'Please enter a valid phone number'


@validation.PanelApplication
def unavailability(app):
    if not app.unavailable and not app.poc_id:
        return 'Your unavailability is required.'


@validation.PanelApplication
def availability(app):
    if not app.available and app.poc_id:
        return 'Please list the times you are available to hold this panel!'


@validation.PanelApplication
def panel_other(app):
    if app.presentation == c.OTHER and not app.other_presentation:
        return 'Since you selected "Other" for your type of panel, please describe it'


@validation.PanelApplication
def app_deadline(app):
    if localized_now() > c.PANEL_APP_DEADLINE and not c.HAS_PANEL_APPS_ACCESS and not app.poc_id:
        return 'We are now past the deadline and are no longer accepting panel applications'


@validation.PanelApplication
def specify_other_time(app):
    if app.length == c.OTHER and not app.length_text:
        return 'Please specify how long your panel will be.'


@validation.PanelApplication
def specify_nonstandard_time(app):
    if app.length != c.SIXTY_MIN and not app.length_reason and not app.poc_id:
        return 'Please explain why your panel needs to be longer than sixty minutes.'


@validation.PanelApplication
def specify_table_needs(app):
    if app.need_tables and not app.tables_desc:
        return 'Please describe how you need tables set up for your panel.'


@validation.PanelApplication
def specify_cost_details(app):
    if app.has_cost and not app.cost_desc:
        return 'Please describe the materials you will provide and how much you will charge attendees for them.'


Attraction.required = [('name', 'Name'), ('description', 'Description')]
AttractionFeature.required = [('name', 'Name'), ('description', 'Description')]


@validation.AttractionEvent
def at_least_one_slot(event):
    if event.slots < 1:
        return 'Events must have at least one slot.'
