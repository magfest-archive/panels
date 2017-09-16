from panels import *


OTHER_PANELISTS_FIELDS = [
    'first_name', 'last_name', 'email', 'occupation', 'website',
    'other_credentials'] + list(PanelApplicant._social_media_fields.keys())


PANELISTS_FIELDS = OTHER_PANELISTS_FIELDS + [
    'cellphone', 'communication_pref', 'other_communication_pref']


def check_other_panelists(other_panelists):
    for i, op in enumerate(other_panelists):
        message = check(op)
        if message:
            return '{} (for Other Panelist #{})'.format(message, i + 1)


def check_extra_verifications(other_panelists=False, **params):
    """
    Panelists submitting an application not associated with an attendee have some extra checkboxes they have
    to tick, so we validate them all here.
    """
    if 'verify_waiting' not in params:
        return 'You must check the box to verify you understand that you will not hear back until {}'.format(
            c.EXPECTED_RESPONSE)
    elif 'verify_tos' not in params:
        return 'You must accept our Terms of Accommodation'
    elif other_panelists and 'verify_poc' not in params:
        return 'You must agree to being the point of contact for your group'


def other_panelists_from_params(app, **params):
    # Turns form fields into a list of dicts of extra panelists on a panel application.
    other_panelists = []
    for i in range(1, int(params.get('other_panelists', 0)) + 1):
        applicant = {attr: params.get('{}_{}'.format(attr, i)) for attr in OTHER_PANELISTS_FIELDS}
        other_panelists.append(PanelApplicant(application=app, **applicant))
    return other_panelists


@all_renderable()
class Root:
    @cherrypy.expose(['post_index'])
    def index(self, session, message='', **params):
        """
        Our production NGINX config caches the page at /panel_applications/index.
        Since it's cached, we CAN'T return a session cookie with the page. We
        must POST to a different URL in order to bypass the cache and get a
        valid session cookie. Thus, this page is also exposed as "post_index".
        """
        app = session.panel_application(params, checkgroups=PanelApplication.all_checkgroups, restricted=True, ignore_csrf=True)
        panelist_params = {attr: params.get('{}_0'.format(attr)) for attr in PANELISTS_FIELDS if params.get('{}_0'.format(attr))}
        panelist = session.panel_applicant(panelist_params, checkgroups=PanelApplicant.all_checkgroups, restricted=True, ignore_csrf=True)
        panelist.application = app
        panelist.submitter = True

        if cherrypy.request.method == 'POST':
            message = check(panelist) or check_extra_verifications(int(params.get('other_panelists', 0)), **params)
            if not message:
                message = process_panel_app(session, app, panelist, **params)
                if not message:
                    raise HTTPRedirect('guest?poc_id={}message={}', poc_id, 'Your panel application has been submitted')

        return {
            'app': app,
            'message': message,
            'panelist': panelist,
            'other_panelists': other_panelists_from_params(app, **params),
            'verify_tos': params.get('verify_tos'),
            'verify_poc': params.get('verify_poc'),
            'verify_waiting': params.get('verify_waiting'),
            'verify_unavailable': params.get('verify_unavailable')
        }

    def guest(self, session, poc_id, message='', **params):
        """
        In some cases, we want pre-existing attendees (e.g., guests) to submit panel ideas.
        This submission form bypasses the need to enter in one's personal and contact info
        in favor of having the panel application automatically associated with an attendee
        record, both as the submitter and as the Point of Contact.
        """

        app = session.panel_application(params, checkgroups=PanelApplication.all_checkgroups, restricted=True, ignore_csrf=True)
        app.poc_id = poc_id
        attendee = session.attendee(id=poc_id)
        panelist = PanelApplicant(
            app_id=app.id,
            attendee_id=attendee.id,
            submitter=True,
            first_name=attendee.first_name,
            last_name=attendee.last_name,
            email=attendee.email,
            cellphone=attendee.cellphone
        )

        if cherrypy.request.method == 'POST':
            message = process_panel_app(session, app, panelist, **params)
            if not message:
                raise HTTPRedirect('guest?poc_id={}&message={}', poc_id, 'Your panel application has been submitted')

        return {
            'app': app,
            'message': message,
            'attendee': attendee,
            'poc_id': poc_id,
            'other_panelists': other_panelists_from_params(app, **params),
            'verify_unavailable': params.get('verify_unavailable')
        }


def process_panel_app(session, app, panelist, **params):
    """
    Checks various parts of a new panel application, either submitted by guests or by non-attendees,
    and then adds them to a session.
    """
    other_panelists = other_panelists_from_params(app, **params)

    message = check(app) or check_other_panelists(other_panelists) or ''
    if not message and 'verify_unavailable' not in params:
        message = 'You must check the box to confirm that you are only unavailable at the specified times'
    elif not message:
        session.add_all([app, panelist] + other_panelists)

    return message
