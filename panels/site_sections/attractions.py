from uber.common import *
from uber.site_sections.preregistration import check_post_con

from panels.models import *


@all_renderable()
@check_post_con
class Root:

    def index(self, session):
        attractions = session.query(Attraction).order_by(Attraction.name).all()
        return {'attractions': attractions}

    def features(self, session, id=None):
        try:
            uuid.UUID(id)
        except Exception as ex:
            attraction = None
        else:
            attraction = session.query(Attraction).filter_by(id=id).first()

        if attraction:
            return {'attraction': attraction}
        else:
            raise HTTPRedirect('index')

    @ajax
    def is_badge_num_valid(self, session, badge_num):
        attendee = session.query(Attendee).filter_by(badge_num=badge_num).first()
        return {'result': bool(attendee)}
