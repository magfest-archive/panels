from panels import *

panels_config = parse_config(__file__)
c.include_plugin_config(panels_config)

c.EVENT_START_TIME_OPTS = [(dt, dt.strftime('%I %p %a') if not dt.minute else dt.strftime('%I:%M %a'))
                           for dt in [c.EPOCH + timedelta(minutes=i * 30) for i in range(2 * c.CON_LENGTH)]]
c.EVENT_DURATION_OPTS = [(i, '%.1f hour%s' % (i/2, 's' if i != 2 else '')) for i in range(1, 19)]

c.ORDERED_EVENT_LOCS = [loc for loc, desc in c.EVENT_LOCATION_OPTS]
c.EVENT_BOOKED = {'colspan': 0}
c.EVENT_OPEN   = {'colspan': 1}

c.PANEL_ROOMS = [getattr(c, room.upper()) for room in c.PANEL_ROOMS]

# This can go away if/when we implement plugin enum merging
c.ACCESS.update(c.PANEL_ACCESS_LEVELS)
c.ACCESS_OPTS.extend(c.PANEL_ACCESS_LEVEL_OPTS)
c.ACCESS_VARS.extend(c.PANEL_ACCESS_LEVEL_VARS)
