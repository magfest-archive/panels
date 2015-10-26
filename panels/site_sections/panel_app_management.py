from panels import *


@all_renderable(c.PANEL_APPS)
class Root:
    def index(self, session, message=''):
        curr_admin_votes = {pv.application: pv for pv in session.admin_attendee().admin_account.panel_votes}
        apps = session.query(PanelApplication).order_by('applied').all()
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
