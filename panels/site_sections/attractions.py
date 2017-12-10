from uber.common import *
from uber.site_sections.preregistration import check_post_con

from panels.models import *


def _attendee_for_badge_num(session, badge_num):
    if badge_num:
        return session.query(Attendee).filter_by(badge_num=badge_num).first()
    return None


@all_renderable()
@check_post_con
class Root:

    def index(self, session, badge_num=''):
        attractions = session.query(Attraction).options(
            subqueryload(Attraction.features)).order_by(Attraction.name).all()
        attendee = _attendee_for_badge_num(session, badge_num)
        return {
            'attractions': attractions,
            'attendee': attendee}

    def features(self, session, id=None, badge_num=''):
        try:
            uuid.UUID(id)
        except Exception as ex:
            attraction = None
        else:
            attraction = session.query(Attraction).filter_by(id=id).first()

        if attraction:
            attendee = _attendee_for_badge_num(session, badge_num)
            return {
                'attraction': attraction,
                'attendee': attendee}
        raise HTTPRedirect('index')

    def events(self, session, id=None, badge_num=''):
        try:
            uuid.UUID(id)
        except Exception as ex:
            feature = None
        else:
            feature = session.query(AttractionFeature).filter_by(id=id).first()

        if feature and badge_num:
            attendee = _attendee_for_badge_num(session, badge_num)
            return {
                'feature': feature,
                'attendee': attendee}
        raise HTTPRedirect('index')

    @ajax
    def is_badge_num_valid(self, session, badge_num):
        attendee = session.query(Attendee).filter_by(badge_num=badge_num).first()
        if not attendee:
            return {'error': 'Unrecognized badge number: {}'.format(badge_num)}

        return {
            'first_name': attendee.first_name,
            'badge_num': attendee.badge_num}

    @ajax
    def signup_for_event(self, session, badge_num, id):
        attendee = session.query(Attendee).filter_by(badge_num=badge_num).first()
        if not attendee:
            return {'error': 'Unrecognized badge number: {}'.format(badge_num)}

        try:
            uuid.UUID(id)
        except Exception as ex:
            return {'error': 'Invalid event id: {}'.format(id)}

        event = session.query(AttractionEvent).filter_by(id=id).first()
        if not event:
            return {'error': 'Unrecognized event id: {}'.format(id)}

        event.attendees.append(attendee)
        session.commit()
        return {
            'result': True,
            'remaining_slots': event.remaining_slots}
