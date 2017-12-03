from panels import *

AutomatedEmail.queries[PanelApplication] = lambda session: session.query(PanelApplication) \
    .options(subqueryload(PanelApplication.applicants).subqueryload(PanelApplicant.attendee))

_attendee_query = AutomatedEmail.queries[Attendee]
AutomatedEmail.queries[Attendee] = lambda session: _attendee_query(session) \
    .options(subqueryload(Attendee.assigned_panelists))


class PanelAppEmail(AutomatedEmail):
    def __init__(self, subject, template, filter, ident, **kwargs):
        AutomatedEmail.__init__(
            self,
            PanelApplication,
            subject,
            template,
            lambda app: filter(app) and (
                not app.submitter or
                not app.submitter.attendee_id or
                app.submitter.attendee.badge_type != c.GUEST_BADGE),
            ident,
            sender=c.PANELS_EMAIL,
            **kwargs)

    def computed_subject(self, x):
        return self.subject.replace('<PANEL_NAME>', x.name)


PanelAppEmail('Your {EVENT_NAME} Panel Application Has Been Received: <PANEL_NAME>', 'panel_app_confirmation.txt',
              lambda a: True,
              needs_approval=False,
              ident='panel_received')

PanelAppEmail('Your {EVENT_NAME} Panel Application Has Been Accepted: <PANEL_NAME>', 'panel_app_accepted.txt',
              lambda app: app.status == c.ACCEPTED,
              ident='panel_accepted')

PanelAppEmail('Your {EVENT_NAME} Panel Application Has Been Declined: <PANEL_NAME>', 'panel_app_declined.txt',
              lambda app: app.status == c.DECLINED,
              ident='panel_declined')

PanelAppEmail('Your {EVENT_NAME} Panel Application Has Been Waitlisted: <PANEL_NAME>', 'panel_app_waitlisted.txt',
              lambda app: app.status == c.WAITLISTED,
              ident='panel_waitlisted')

PanelAppEmail('Your {EVENT_NAME} Panel Has Been Scheduled: <PANEL_NAME>', 'panel_app_scheduled.txt',
              lambda app: app.event_id,
              ident='panel_scheduled')

AutomatedEmail(Attendee, 'Your {EVENT_NAME} Event Schedule', 'panelist_schedule.txt',
               lambda a: a.badge_type != c.GUEST_BADGE and a.assigned_panelists,
               ident='event_schedule',
               sender=c.PANELS_EMAIL)
