from uber.common import *
from uber.site_sections.preregistration import check_post_con

from panels.models import *


def _attendee_for_badge_num(session, badge_num):
    if not badge_num:
        return None

    try:
        badge_num = int(badge_num)
    except Exception:
        return None
    return session.query(Attendee).filter_by(badge_num=badge_num).first()


def _model_for_id(session, model, id):
    if not id:
        return None

    try:
        uuid.UUID(id)
    except Exception:
        return None
    return session.query(model).filter_by(id=id).first()


@all_renderable()
@check_post_con
class Root:

    def index(self, session, **params):
        attractions = session.query(Attraction).options(
            subqueryload(Attraction.features)).order_by(Attraction.name).all()
        return {'attractions': attractions}

    def features(self, session, id=None, **params):
        attraction = _model_for_id(session, Attraction, id)
        if not attraction:
            raise HTTPRedirect('index')
        return {'attraction': attraction}

    def events(self, session, id=None, **params):
        feature = _model_for_id(session, AttractionFeature, id)
        if not feature:
            raise HTTPRedirect('index')
        return {'feature': feature}

    @ajax
    def verify_badge_num(self, session, badge_num, **params):
        attendee = _attendee_for_badge_num(session, badge_num)
        if not attendee:
            return {'error': 'Unrecognized badge number: {}'.format(badge_num)}

        return {
            'first_name': attendee.first_name,
            'badge_num': attendee.badge_num}

    @ajax
    def signup_for_event(self, session, badge_num, id, **params):
        attendee = _attendee_for_badge_num(session, badge_num)
        if not attendee:
            return {'error': 'Unrecognized badge number: {}'.format(badge_num)}

        event = _model_for_id(session, AttractionEvent, id)
        if not event:
            return {'error': 'Unrecognized event id: {}'.format(id)}

        old_remaining_slots = event.remaining_slots

        if event not in attendee.attraction_events:
            attraction = event.feature.attraction
            if attraction.restriction == Attraction.PER_ATTRACTION:
                if attraction in attendee.attractions:
                    return {
                        'error': '{} is already signed up for {}'.format(
                            attendee.first_name, attraction.name)}
            elif attraction.restriction == Attraction.PER_FEATURE:
                if event.feature in attendee.attraction_features:
                    return {
                        'error': '{} is already signed up for {}'.format(
                            attendee.first_name, event.feature.name)}

            if event.is_sold_out:
                return {'error': '{} is already sold out'.format(event.label)}

            event.attendees.append(attendee)
            session.commit()

        return {
            'first_name': attendee.first_name,
            'badge_num': attendee.badge_num,
            'event_id': event.id,
            'is_sold_out': event.is_sold_out,
            'remaining_slots': event.remaining_slots,
            'old_remaining_slots': old_remaining_slots}
