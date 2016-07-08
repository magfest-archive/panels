from panels import *

AutomatedEmail.queries[PanelApplication] = lambda session: session.query(PanelApplication).all()


# TODO: check to make sure this still works, length of args may have changed with date_filter addition
class PanelAppEmail(AutomatedEmail):
    def __init__(self, *args, **kwargs):
        if len(args) < 3 and 'filter' not in kwargs:
            kwargs['filter'] = lambda x: True
        AutomatedEmail.__init__(self, PanelApplication, *args, sender=c.PANELS_EMAIL, **kwargs)

PanelAppEmail('Your {EVENT_NAME} Panel Application Has Been Received', 'panel_app_confirmation.txt')

PanelAppEmail('Your {EVENT_NAME} Panel Application Has Been Accepted', 'panel_app_accepted.txt',
              lambda app: app.status == c.ACCEPTED)

PanelAppEmail('Your {EVENT_NAME} Panel Application Has Been Declined', 'panel_app_declined.txt',
              lambda app: app.status == c.DECLINED)

PanelAppEmail('Your {EVENT_NAME} Panel Application Has Been Waitlisted', 'panel_app_waitlisted.txt',
              lambda app: app.status == c.WAITLISTED)

PanelAppEmail('Your {EVENT_NAME} Panel Has Been Scheduled', 'panel_app_scheduled.txt',
              lambda app: app.event_id)
