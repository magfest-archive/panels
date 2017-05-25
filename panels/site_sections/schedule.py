from uber.custom_tags import normalize_newlines
from panels import *


@all_renderable(c.STUFF)
class Root:
    @unrestricted
    def index(self, session, message=''):
        if c.ALT_SCHEDULE_URL:
            raise HTTPRedirect(c.ALT_SCHEDULE_URL)
        else:
            raise HTTPRedirect("internal")

    @cached
    def internal(self, session, message=''):
        if c.HIDE_SCHEDULE and not AdminAccount.access_set() and not cherrypy.session.get('staffer_id'):
            return "The " + c.EVENT_NAME + " schedule is being developed and will be made public when it's closer to being finalized."

        schedule = defaultdict(lambda: defaultdict(list))
        for event in session.query(Event).all():
            schedule[event.start_time_local][event.location].append(event)
            for i in range(1, event.duration):
                half_hour = event.start_time_local + timedelta(minutes=30 * i)
                schedule[half_hour][event.location].append(c.EVENT_BOOKED)

        max_simul = {}
        for id, name in c.EVENT_LOCATION_OPTS:
            max_events = 1
            for i in range(2 * c.CON_LENGTH):
                half_hour = c.EPOCH + timedelta(minutes=30 * i)
                max_events = max(max_events, len(schedule[half_hour][id]))
            max_simul[id] = max_events

        for half_hour in schedule:
            for location in schedule[half_hour]:
                for event in schedule[half_hour][location]:
                    if isinstance(event, Event):
                        simul = max(len(schedule[half_hour][event.location]) for half_hour in event.half_hours)
                        event.colspan = 1 if simul > 1 else max_simul[event.location]
                        for i in range(1, event.duration):
                            schedule[half_hour + timedelta(minutes=30*i)][event.location].remove(c.EVENT_BOOKED)
                            schedule[half_hour + timedelta(minutes=30*i)][event.location].append(event.colspan)

        for half_hour in schedule:
            for id, name in c.EVENT_LOCATION_OPTS:
                span_sum = sum(getattr(e, 'colspan', e) for e in schedule[half_hour][id])
                for i in range(max_simul[id] - span_sum):
                    schedule[half_hour][id].append(c.EVENT_OPEN)

            schedule[half_hour] = sorted(schedule[half_hour].items(), key=lambda tup: c.ORDERED_EVENT_LOCS.index(tup[0]))

        max_simul = [(id, c.EVENT_LOCATIONS[id], colspan) for id, colspan in max_simul.items()]
        return {
            'message':   message,
            'schedule':  sorted(schedule.items()),
            'max_simul': sorted(max_simul, key=lambda tup: c.ORDERED_EVENT_LOCS.index(tup[0]))
        }

    @unrestricted
    @csv_file
    def time_ordered(self, out, session):
        for event in session.query(Event).order_by('start_time', 'duration', 'location').all():
            out.writerow([event.timespan(30), event.name, event.location_label])

    @unrestricted
    def xml(self, session):
        cherrypy.response.headers['Content-type'] = 'text/xml'
        schedule = defaultdict(list)
        for event in session.query(Event).order_by('start_time').all():
            schedule[event.location_label].append(event)
        return render('schedule/schedule.xml', {
            'schedule': sorted(schedule.items(), key=lambda tup: c.ORDERED_EVENT_LOCS.index(tup[1][0].location))
        })

    @unrestricted
    def schedule_tsv(self, session):
        cherrypy.response.headers['Content-Type'] = 'text/tsv'
        cherrypy.response.headers['Content-Disposition'] = 'attachment;filename=Schedule-{}.tsv'.format(int(localized_now().timestamp()))
        schedule = defaultdict(list)
        for event in session.query(Event).order_by('start_time').all():
            schedule[event.location_label].append(dict(event.to_dict(), **{
                'date': event.start_time_local.strftime('%m/%d/%Y'),
                'start_time': event.start_time_local.strftime('%I:%M:%S %p'),
                'end_time': (event.start_time_local + timedelta(minutes=event.minutes)).strftime('%I:%M:%S %p'),
                'description': normalize_newlines(event.description).replace('\n', ' ')
            }))

        return render('schedule/schedule.tsv', {
            'schedule': sorted(schedule.items(), key=lambda tup: c.ORDERED_EVENT_LOCS.index(tup[1][0]['location']))
        })

    @csv_file
    def csv(self, out, session):
        out.writerow(['Session Title', 'Date', 'Time Start', 'Time End', 'Room/Location',
                      'Schedule Track (Optional)', 'Description (Optional)', 'Allow Checkin (Optional)',
                      'Checkin Begin (Optional)', 'Limit Spaces? (Optional)', 'Allow Waitlist (Optional)'])
        rows = []
        for event in session.query(Event).order_by('start_time').all():
            rows.append([
                event.name,
                event.start_time_local.strftime('%m/%d/%Y'),
                event.start_time_local.strftime('%I:%M:%S %p'),
                (event.start_time_local + timedelta(minutes=event.minutes)).strftime('%I:%M:%S %p'),
                event.location_label,
                '',
                normalize_newlines(event.description).replace('\n', ' '),
                '', '', '', ''
            ])
        for r in sorted(rows, key=lambda tup: tup[4]):
            out.writerow(r)

    @csv_file
    def panels(self, out, session):
        out.writerow(['Panel', 'Time', 'Duration', 'Room', 'Description', 'Panelists'])
        for event in sorted(session.query(Event).all(), key=lambda e: [e.start_time, e.location_label]):
            if 'Panel' in event.location_label or 'Autograph' in event.location_label:
                out.writerow([event.name,
                              event.start_time_local.strftime('%I%p %a').lstrip('0'),
                              '{} minutes'.format(event.minutes),
                              event.location_label,
                              event.description,
                              ' / '.join(ap.attendee.full_name for ap in sorted(event.assigned_panelists, key=lambda ap: ap.attendee.full_name))])

    @unrestricted
    def panels_json(self, session):
        cherrypy.response.headers['Content-Type'] = 'application/json'
        return json.dumps([
            {
                'name': event.name,
                'location': event.location_label,
                'start': event.start_time_local.strftime('%I%p %a').lstrip('0'),
                'end': event.end_time_local.strftime('%I%p %a').lstrip('0'),
                'start_unix': int(mktime(event.start_time.utctimetuple())),
                'end_unix': int(mktime(event.end_time.utctimetuple())),
                'duration': event.minutes,
                'description': event.description,
                'panelists': [panelist.attendee.full_name for panelist in event.assigned_panelists]
            }
            for event in sorted(session.query(Event).all(), key=lambda e: [e.start_time, e.location_label])
        ], indent=4).encode('utf-8')

    @unrestricted
    def now(self, session, when=None):
        if when:
            now = c.EVENT_TIMEZONE.localize(datetime(*map(int, when.split(','))))
        else:
            now = c.EVENT_TIMEZONE.localize(datetime.combine(localized_now().date(), time(localized_now().hour)))

        current, upcoming = [], []
        for loc, desc in c.EVENT_LOCATION_OPTS:
            approx = session.query(Event).filter(Event.location == loc,
                                                 Event.start_time >= now - timedelta(hours=6),
                                                 Event.start_time <= now).all()
            for event in approx:
                if now in event.half_hours:
                    current.append(event)

            next = session.query(Event) \
                          .filter(Event.location == loc,
                                  Event.start_time >= now + timedelta(minutes=30),
                                  Event.start_time <= now + timedelta(hours=4)) \
                                .order_by('start_time').all()
            if next:
                upcoming.extend(event for event in next if event.start_time == next[0].start_time)

        return {
            'now':      now if when else localized_now(),
            'current':  current,
            'upcoming': upcoming
        }

    def form(self, session, message='', panelists=(), **params):
        event = session.event(params, allowed=['location', 'start_time'])
        if 'name' in params:
            session.add(event)
            message = check(event)
            if not message:
                new_panelist_ids = set(listify(panelists))
                old_panelist_ids = {ap.attendee_id for ap in event.assigned_panelists}
                for ap in event.assigned_panelists:
                    if ap.attendee_id not in new_panelist_ids:
                        session.delete(ap)
                for attendee_id in new_panelist_ids:
                    if attendee_id not in old_panelist_ids:
                        attendee = session.attendee(id=attendee_id)
                        session.add(AssignedPanelist(event=event, attendee=attendee))
                raise HTTPRedirect('edit#{}', event.start_slot and (event.start_slot - 1))

        return {
            'message': message,
            'event':   event,
            'assigned': [ap.attendee_id for ap in sorted(event.assigned_panelists, reverse=True, key=lambda a: a.attendee.first_name)],
            'panelists': [(a.id, a.full_name)
                          for a in session.query(Attendee)
                                          .filter(or_(Attendee.ribbon == c.PANELIST_RIBBON,
                                                      Attendee.badge_type == c.GUEST_BADGE))
                                          .order_by(Attendee.full_name).all()]
        }

    @csrf_protected
    def delete(self, session, id):
        event = session.delete(session.event(id))
        raise HTTPRedirect('edit?message={}', 'Event successfully deleted')

    @ajax
    def move(self, session, id, location, start_slot):
        event = session.event(id)
        event.location = int(location)
        event.start_time = c.EPOCH + timedelta(minutes=30 * int(start_slot))
        resp = {'error': check(event)}
        if not resp['error']:
            session.commit()
        return resp

    @ajax
    def swap(self, session, id1, id2):
        from panels.model_checks import overlapping_events
        e1, e2 = session.event(id1), session.event(id2)
        (e1.location, e1.start_time), (e2.location, e2.start_time) = (e2.location, e2.start_time), (e1.location, e1.start_time)
        resp = {'error': overlapping_events(e1, e2.id) or overlapping_events(e2, e1.id)}
        if not resp['error']:
            session.commit()
        return resp

    def edit(self, session, message=''):
        panelists = defaultdict(dict)
        for ap in session.query(AssignedPanelist) \
                         .options(joinedload(AssignedPanelist.event), joinedload(AssignedPanelist.attendee)).all():
            panelists[ap.event.id][ap.attendee.id] = ap.attendee.full_name

        events = []
        for e in session.query(Event).order_by('start_time').all():
            d = {attr: getattr(e, attr) for attr in ['id', 'name', 'duration', 'start_slot', 'location', 'description']}
            d['panelists'] = panelists[e.id]
            events.append(d)

        return {
            'events':  events,
            'message': message
        }

    def panelists_owed_refunds(self, session):
        return {
            'panelists': [a for a in session.query(Attendee)
                                            .filter_by(ribbon=c.PANELIST_RIBBON)
                                            .options(joinedload(Attendee.group))
                                            .order_by(Attendee.full_name).all()
                          if a.paid == c.HAS_PAID or a.paid == c.PAID_BY_GROUP and a.group and a.group.amount_paid]
        }

    @unrestricted
    def panelist_schedule(self, session, id):
        attendee = session.attendee(id)
        events = defaultdict(lambda: defaultdict(lambda: (1, '')))
        for ap in attendee.assigned_panelists:
            for timeslot in ap.event.half_hours:
                rowspan = ap.event.duration if timeslot == ap.event.start_time else 0
                events[timeslot][ap.event.location_label] = (rowspan, ap.event.name)

        schedule = []
        when = min(events)
        locations = sorted(set(sum([list(locations) for locations in events.values()], [])))
        while when <= max(events):
            schedule.append([when, [events[when][where] for where in locations]])
            when += timedelta(minutes=30)

        return {
            'attendee': attendee,
            'schedule': schedule,
            'locations': locations
        }

    @unrestricted
    @csv_file
    def panel_tech_needs(self, out, session):
        panels = defaultdict(dict)
        for panel in session.query(PanelApplication).filter(PanelApplication.event_id == Event.id, Event.location.in_(c.PANEL_ROOMS)):
            panels[panel.event.start_time][panel.event.location] = panel

        curr_time, last_time = min(panels), max(panels)
        out.writerow(['Panel Starts'] + [c.EVENT_LOCATIONS[room] for room in c.PANEL_ROOMS])
        while curr_time <= last_time:
            row = [curr_time.strftime('%H:%M %a')]
            for room in c.PANEL_ROOMS:
                p = panels[curr_time].get(room)
                row.append('' if not p else '{}\n{}\n{}\n{}'.format(
                    p.event.name,
                    ' / '.join(p.tech_needs_labels),
                    p.other_tech_needs,
                    'Panelists are bringing themselves: {}'.format(p.panelist_bringing) if p.panelist_bringing else ''
                ).strip())
            out.writerow(row)
            curr_time += timedelta(minutes=30)
