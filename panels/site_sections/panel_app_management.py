from panels import *


@all_renderable(c.PANEL_APPS)
class Root:
    def index(self, session, message=''):
        curr_admin_votes = {pv.application: pv for pv in session.admin_attendee().admin_account.panel_votes}
        apps = session.panel_apps()
        for app in apps:
            app.curr_admin_vote = curr_admin_votes.get(app)

        return {
            'apps': apps,
            'message': message,
            'vote_count': len(curr_admin_votes)
        }

    def app(self, session, id, message='', csrf_token='', vote=None, explanation=None):
        app = session.panel_application(id)
        account = session.admin_attendee().admin_account
        panel_vote = session.query(PanelVote).filter_by(account_id=account.id, app_id=app.id).first()
        if not panel_vote:
            panel_vote = PanelVote(account_id=account.id, app_id=app.id)

        if vote is not None:
            check_csrf(csrf_token)
            panel_vote.vote = int(vote or 0)
            panel_vote.explanation = explanation.strip()
            if not panel_vote.vote:
                message = 'You did not indicate your vote'
            elif not panel_vote.explanation:
                message = 'You must provide an explanation of your vote'
            else:
                session.add(panel_vote)
                raise HTTPRedirect('index?message={}{}', 'Vote cast for ', app.name)

        return {
            'app': app,
            'message': message,
            'panel_vote': panel_vote
        }

    def mark(self, session, status, **params):
        app = session.panel_application(params)
        if app.status != c.PENDING:
            raise HTTPRedirect('index?message={}{}', 'That panel was already marked as ', app.status_label)

        app.status = int(status)
        create_group = len(app.applicants) - len(app.matching_attendees) > 1 and not getattr(app.submitter.matching_attendee, 'group_id', None)
        if cherrypy.request.method == 'POST':
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
