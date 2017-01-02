from panels import *

AutomatedEmail.queries[PanelApplication] = lambda session: session.query(PanelApplication).all()


# TODO: check to make sure this still works, length of args may have changed with date_filter addition
class PanelAppEmail(AutomatedEmail):
    def __init__(self, *args, **kwargs):
        if len(args) < 3 and 'filter' not in kwargs:
            kwargs['filter'] = lambda x: True
        AutomatedEmail.__init__(self, PanelApplication, *args, sender=c.PANELS_EMAIL, **kwargs)

    def computed_subject(self, x):
        return self.subject.replace('<PANEL_NAME>', x.name)


PanelAppEmail('Your {EVENT_NAME} Panel Application Has Been Received: <PANEL_NAME>', 'panel_app_confirmation.txt')

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
               lambda a: a.assigned_panelists,
               ident='event_schedule',
               sender=c.PANELS_EMAIL)
