from panels import *

AutomatedEmail.extra_models[PanelApplication] = lambda session: session.query(PanelApplication).all()


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
