from panels import *


@all_renderable(c.PANEL_APPS)
class Root:
    def index(self, session, message=''):
        return {
            'message': message,
            'apps': session.panel_apps()
        }

    def app(self, session, id, message='', csrf_token='', explanation=None):
        return {
            'message': message,
            'app': session.panel_application(id)
        }

    def form(self, session, message='', **params):
        app = session.panel_application(params)
        if cherrypy.request.method == 'POST':
            message = check(app)
            if not message:
                raise HTTPRedirect('app?id={}&message={}', app.id, 'Application updated')

        return {
            'app': app,
            'message': message
        }

    def email_statuses(self):
        return {}

    @csrf_protected
    def update_comments(self, session, id, comments):
        session.panel_application(id).comments = comments
        raise HTTPRedirect('app?id={}&message={}', id, 'Comments updated')

    @csrf_protected
    def mark(self, session, status, **params):
        app = session.panel_application(params)
        app.status = int(status)
        if not app.poc:
            app.poc_id = session.admin_attendee().id
        raise HTTPRedirect('index?message={}{}{}', app.name, ' was marked as ', app.status_label)

    @csrf_protected
    def set_poc(self, session, app_id, poc_id):
        app = session.panel_application(app_id)
        app.poc = session.attendee(poc_id)
        raise HTTPRedirect('app?id={}&message={}{}', app.id, 'Point of contact was updated to ', app.poc.full_name)

    def associate(self, session, message='', **params):
        app = session.panel_application(params)
        if app.status != c.ACCEPTED:
            raise HTTPRedirect('index?message={}', 'You cannot associate a non-accepted panel application with an event')
        elif app.event_id and cherrypy.request.method == 'GET':
            raise HTTPRedirect('index?message={}{}', 'This panel application is already associated with the event ', app.event.name)

        if cherrypy.request.method == 'POST':
            if not app.event_id:
                message = 'You must select an event'
            else:
                for attendee in app.matching_attendees:
                    if not session.query(AssignedPanelist).filter_by(event_id=app.event_id, attendee_id=attendee.id).first():
                        app.event.assigned_panelists.append(AssignedPanelist(attendee=attendee))
                raise HTTPRedirect('index?message={}{}{}', app.name, ' was associated with ', app.event.name)

        return {
            'app': app,
            'message': message,
            'panels': [e for e in session.query(Event).filter(Event.location.in_(c.PANEL_ROOMS)).order_by('name').all()]
        }

    @csv_file
    def everything(self, out, session):
        out.writerow(['Panel Name', 'Description', 'Expected Length', 'Unavailability', 'Past Attendance', 'Affiliations', 'Type of Panel', 'Technical Needs', 'Applied', 'Panelists'])
        for app in session.panel_apps():
            panelists = []
            for panelist in app.applicants:
                panelists.extend([
                    panelist.full_name,
                    panelist.email,
                    panelist.cellphone
                ])
            out.writerow([
                app.name,
                app.description,
                app.length,
                app.unavailable,
                app.past_attendance,
                app.affiliations,
                app.other_presentation if app.presentation == c.OTHER else app.presentation_label,
                ' / '.join(app.tech_needs_labels) + (' / ' if app.other_tech_needs else '') + app.other_tech_needs,
                app.applied.strftime('%Y-%m-%d')
            ] + panelists)
