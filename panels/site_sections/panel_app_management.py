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

    def mark(self, session, status, **params):
        app = session.panel_application(params)
        if app.status != c.PENDING:
            raise HTTPRedirect('index?message={}{}', 'That panel was already marked as ', app.status_label)

        app.status = int(status)
        create_group = len(app.applicants) - len(app.matching_attendees) > 1 and not getattr(app.submitter.matching_attendee, 'group_id', None)
        if cherrypy.request.method == 'POST':
            if app.status == c.ACCEPTED:
                leader = None
                group = Group(name='Panelists for ' + app.name, cost=0, auto_recalc=False) if create_group else None
                for applicant in app.applicants:
                    if applicant.matching_attendee:
                        if applicant.matching_attendee.ribbon == c.NO_RIBBON:
                            applicant.matching_attendee.ribbon = c.PANELIST_RIBBON
                        if group and not applicant.matching_attendee.group_id:
                            applicant.matching_attendee.group = group
                    else:
                        attendee = Attendee(
                            group=group,
                            placeholder=True,
                            ribbon=c.PANELIST_RIBBON,
                            badge_type=c.ATTENDEE_BADGE,
                            paid=c.PAID_BY_GROUP if group else c.NEED_NOT_PAY,
                            first_name=applicant.first_name,
                            last_name=applicant.last_name,
                            cellphone=applicant.cellphone,
                            email=applicant.email
                        )
                        if group and applicant.submitter:
                            leader = attendee
                        session.add(attendee)

                if group:
                    session.add(group)
                    session.commit()
                    group.leader_id = leader.id
                    session.commit()

            raise HTTPRedirect('index?message={}{}{}', app.name, ' was marked as ', app.status_label)

        return {
            'app': app,
            'group': create_group
        }

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
