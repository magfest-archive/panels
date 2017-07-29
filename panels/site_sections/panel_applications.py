from panels import *


def check_ops(other_panelists):
    for i, op in enumerate(other_panelists):
        message = check(op)
        if message:
            return '{} (for Other Panelist #{})'.format(message, i + 1)


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
        app = session.panel_application(params, checkgroups={'tech_needs'}, restricted=True)
        panelist = session.panel_applicant(params, restricted=True)
        panelist.application = app
        other_panelists = []
        for i in range(int(params.get('other_panelists', 0))):
            applicant = {attr: params.get('{}_{}'.format(attr, i)) for attr in ['first_name', 'last_name', 'email']}
            other_panelists.append(PanelApplicant(application=app, **applicant))

        if cherrypy.request.method == 'POST':
            message = check(panelist) or check(app) or check_ops(other_panelists)
            if not message:
                if 'verify_unavailable' not in params:
                    message = 'You must check the box to confirm that you are only unavailable at the specified times'
                elif 'verify_waiting' not in params:
                    message = 'You must check the box to verify you understand that you will not hear back until {}'.format(c.EXPECTED_RESPONSE)
                elif 'verify_tos' not in params:
                    message = 'You must accept our Terms of Accomodation'
                elif other_panelists and 'verify_poc' not in params:
                    message = 'You must agree to being the point of contact for your group'
                else:
                    session.add_all([app, panelist] + other_panelists)
                    raise HTTPRedirect('index?message={}', 'Your panel application has been submitted')

        return {
            'app': app,
            'message': message,
            'panelist': panelist,
            'ops_count': len(other_panelists),
            'other_panelists': other_panelists,
            'verify_tos': params.get('verify_tos'),
            'verify_poc': params.get('verify_pos'),
            'verify_waiting': params.get('verify_waiting'),
            'verify_unavailable': params.get('verify_unavailable')
        }
