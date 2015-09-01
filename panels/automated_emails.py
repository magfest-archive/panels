from panels import *

AutomatedEmail.extra_models[PanelApplication] = lambda session: session.query(PanelApplication).all()

AutomatedEmail(PanelApplication, 'Your {EVENT_NAME} Panel Application Has Been Received', 'panel_app_confirmation.txt',
               lambda app: True)
