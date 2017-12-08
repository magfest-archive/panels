from uber.common import *
from uber.site_sections.preregistration import check_post_con

from panels.models import *


def _first_name_and_badge_num(session, badge_num):
    first_name = ''
    if badge_num:
        attendee = session.query(Attendee).filter_by(badge_num=badge_num).first()
        first_name = attendee.first_name if attendee else ''

    if not first_name:
        badge_num = ''

    return (first_name, badge_num)


@all_renderable()
@check_post_con
class Root:

    def index(self, session, badge_num=''):
        attractions = session.query(Attraction).options(
            subqueryload(Attraction.features)).order_by(Attraction.name).all()
        first_name, badge_num = _first_name_and_badge_num(session, badge_num)
        return {
            'attractions': attractions,
            'badge_num': badge_num,
            'first_name': first_name
        }

    def features(self, session, id=None, badge_num=''):
        try:
            uuid.UUID(id)
        except Exception as ex:
            attraction = None
        else:
            attraction = session.query(Attraction).filter_by(id=id).first()

        if attraction:
            first_name, badge_num = _first_name_and_badge_num(session, badge_num)
            return {
                'attraction': attraction,
                'badge_num': badge_num,
                'first_name': first_name
            }
        else:
            raise HTTPRedirect('index')

    def events(self, session, id=None, badge_num=''):
        try:
            uuid.UUID(id)
        except Exception as ex:
            feature = None
        else:
            feature = session.query(AttractionFeature).filter_by(id=id).first()

        if feature and badge_num:
            first_name, badge_num = _first_name_and_badge_num(session, badge_num)
            return {
                'feature': feature,
                'badge_num': badge_num,
                'first_name': first_name
            }
        else:
            raise HTTPRedirect('index')

    @ajax
    def is_badge_num_valid(self, session, badge_num):
        attendee = session.query(Attendee).filter_by(badge_num=badge_num).first()
        return {'result': bool(attendee)}

    @ajax
    def signup_for_event(self, session, badge_num, id):
        attendee = session.query(Attendee).filter_by(badge_num=badge_num).first()
        try:
            uuid.UUID(id)
        except Exception as ex:
            event = None
        else:
            event = session.query(AttractionEvent).filter_by(id=id).first()
        if attendee and event:
            event.attendees.append(attendee)
            session.commit()
            return {'result': True}
        return {'result': False}
