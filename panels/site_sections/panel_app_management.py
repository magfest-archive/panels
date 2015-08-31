from panels import *


@all_renderable(c.STUFF)
class Root:
    def index(self, session):
        return {'apps': session.query(PanelApplication).order_by('applied').all()}
