import uuid

import phonenumbers
from phonenumbers import PhoneNumberFormat
from twilio.rest import Client as TwilioRestClient

from uber.models.types import utcmin
from uber.custom_tags import humanize_timedelta
from panels.config import panels_config
from panels.models import *


TASK_INTERVAL = 180  # Check every three minutes

TEXT_TPL = (
    'Checkin for {signup.event.name} {checkin}, '
    '{signup.event.location_room_name}. '
    'Reply N to drop out')


twilio_client = None
try:
    twilio_sid = panels_config['secret']['panels_twilio_sid']
    twilio_token = panels_config['secret']['panels_twilio_token']

    if twilio_sid and twilio_token:
        twilio_client = TwilioRestClient(twilio_sid, twilio_token)
    else:
        log.debug('Twilio SID and/or TOKEN is not in INI, not going to try to start Twilio for SMS messaging')
except:
    log.error('Twilio: unable to initialize twilio REST client', exc_info=True)
    twilio_client = None


def normalize(phone_number):
    return phonenumbers.format_number(phonenumbers.parse(phone_number, 'US'), PhoneNumberFormat.E164)


def send_sms(to, body, from_=c.PANELS_TWILIO_NUMBER):
    message = None
    sid = 'Unable to send sms'
    try:
        to = normalize(to)
        if not twilio_client:
            log.error('no twilio client configured')
        elif c.DEV_BOX and to not in c.TESTING_PHONE_NUMBERS:
            log.info('We are in dev box mode, so we are not sending {!r} to {!r}', body, to)
        else:
            message = twilio_client.messages.create(to=to, from_=normalize(from_), body=body)
            sleep(0.1)  # Avoid hitting rate limit, the send_email() implementation already does this
        if message:
            sid = message.sid if not message.error_code else message.error_text
    except TwilioRestException as e:
        if e.code == 21211:  # https://www.twilio.com/docs/api/errors/21211
            log.error('Invalid cellphone number', exc_info=True)
        else:
            log.error('Unable to send SMS notification', exc_info=True)
            raise
    except:
        log.error('Unexpected error sending SMS', exc_info=True)
        raise
    return sid


def send_attraction_notifications(session):
    for attraction in session.query(Attraction):
        now = datetime.now(pytz.UTC)
        from_time = now - timedelta(seconds=300)
        to_time = now + timedelta(seconds=300)
        signups = attraction.signups_requiring_notification(
            session, from_time, to_time, [
                subqueryload(AttractionSignup.attendee)
                    .subqueryload(Attendee.attraction_notifications),
                subqueryload(AttractionSignup.event)
                    .subqueryload(AttractionEvent.feature)])

        for signup, advance_notices in signups.items():
            attendee = signup.attendee

            is_first_signup = not(attendee.attraction_notifications)

            if not is_first_signup and \
                    attendee.notification_pref == Attendee.NOTIFICATION_NONE:
                continue

            use_text = not is_first_signup \
                and twilio_client \
                and attendee.cellphone \
                and attendee.notification_pref == Attendee.NOTIFICATION_TEXT

            event = signup.event

            # If we overlap multiple notices, we only want to send a single
            # notification. So if we have both "5 minutes before checkin" and
            # "when checkin starts", we only want to send the notification
            # for "when checkin starts".
            advance_notice = min(advance_notices)
            if advance_notice == -1 or advance_notice > 1800:
                checkin = 'is at {}'.format(event.checkin_time_label)
            else:
                checkin = humanize_timedelta(
                    event.time_remaining_to_checkin,
                    granularity='minutes',
                    separator=' ',
                    prefix='is in ',
                    now='is right now',
                    past_prefix='was ',
                    past_suffix=' ago')

            ident = AttractionEvent.get_ident(event.id, advance_notice)
            try:
                if use_text:
                    type_ = Attendee.NOTIFICATION_TEXT
                    type_str = 'TEXT'
                    from_ = c.PANELS_TWILIO_NUMBER
                    to_ = attendee.cellphone
                    body = TEXT_TPL.format(signup=signup, checkin=checkin)
                    subject = ''
                    sid = send_sms(to_, body, from_)
                else:
                    type_ = Attendee.NOTIFICATION_EMAIL
                    type_str = 'EMAIL'
                    from_ = c.ATTRACTIONS_EMAIL
                    to_ = attendee.email
                    if is_first_signup:
                        template = 'emails/attractions_welcome.html'
                        subject = 'Welcome to {} Attractions'.format(
                            c.EVENT_NAME)
                    else:
                        template = 'emails/attractions_notification.html'
                        subject = 'Checkin for {} is at {}'.format(
                            event.name, event.checkin_time_label)

                    body = render(template, {
                        'signup': signup,
                        'checkin': checkin,
                        'c': c}).decode('utf-8')
                    sid = ident
                    send_email(
                        from_,
                        to_,
                        subject=subject,
                        body=body,
                        format='html',
                        model=attendee,
                        ident=ident)
            except:
                log.error(
                    'Error sending notification\n'
                    '\tfrom: {}\n'
                    '\tto: {}\n'
                    '\tsubject: {}\n'
                    '\tbody: {}\n'
                    '\ttype: {}\n'
                    '\tattendee: {}\n'
                    '\tident: {}\n'.format(
                        from_,
                        to_,
                        subject,
                        body,
                        type_str,
                        attendee.id,
                        ident), exc_info=True)
            else:
                session.add(AttractionNotification(
                    attraction_event_id=event.id,
                    attraction_id=event.attraction_id,
                    attendee_id=attendee.id,
                    notification_type=type_,
                    ident=ident,
                    sid=sid,
                    sent_time=datetime.now(pytz.UTC),
                    subject=subject,
                    body=body))
                session.commit()


def check_attraction_notification_replies(session):
    messages = twilio_client.messages.list(to=c.PANELS_TWILIO_NUMBER)
    sids = set(m.sid for m in messages)
    existing_sids = set(
        sid for [sid] in session.query(AttractionNotificationReply.sid)
            .filter(AttractionNotificationReply.sid.in_(sids)))

    attendees = session.query(Attendee).filter(
        Attendee.cellphone != '',
        Attendee.attraction_notifications.any())
    attendees_by_phone = groupify(attendees, lambda a: normalize(a.cellphone))

    for message in filter(lambda m: m.sid not in existing_sids, messages):
        attraction_event_id = None
        attraction_id = None
        attendee_id = None
        attendees = attendees_by_phone.get(normalize(message.from_), [])
        for attendee in attendees:
            notifications = sorted(filter(
                lambda s: s.notification_type == Attendee.NOTIFICATION_TEXT,
                attendee.attraction_notifications),
                key=lambda s: s.sent_time)
            if notifications:
                notification = notifications[-1]
                attraction_event_id = notification.attraction_event_id
                attraction_id = notification.attraction_id
                attendee_id = notification.attendee_id
                if 'N' in message.body.upper() and notification.signup:
                    session.delete(notification.signup)
                break

        session.add(AttractionNotificationReply(
            attraction_event_id=attraction_event_id,
            attraction_id=attraction_id,
            attendee_id=attendee_id,
            notification_type=Attendee.NOTIFICATION_TEXT,
            from_phonenumber=message.from_,
            to_phonenumber=message.to,
            sid=message.sid,
            received_time=datetime.now(pytz.UTC),
            sent_time=message.date_sent.replace(tzinfo=pytz.UTC),
            body=message.body))
        session.commit()


def send_notifications():
    with Session() as session:
        send_attraction_notifications(session)


def check_notification_replies():
    with Session() as session:
        check_attraction_notification_replies(session)


DaemonTask(send_notifications, interval=TASK_INTERVAL,
           name='panels_send_notifications')
DaemonTask(check_notification_replies, interval=TASK_INTERVAL,
           name='panels_check_notification_replies')
