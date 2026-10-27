"""Escaped infrastructure details for the generated research dashboard."""
import html
import config
import infrastructure


def infrastructure_panel(raw):
    data = raw.get('infrastructure', {})
    route = data.get('route', {})
    delivery = raw.get('protocols', {}).get('ch_route', {})
    backhaul = data.get('backhaul', {})
    analytics = infrastructure.analytics(config.RESULTS_DIR)
    escape = lambda value: html.escape(str(value))
    path = ' → '.join(route.get('vehicle_ids', [])) or 'No trusted CH route available'
    rows = ''.join('<tr>' + ''.join(f'<td>{escape(value)}</td>' for value in (
        item['cluster_head'], ', '.join(item['votes_received']) or 'None',
        'Accepted' if item['accepted'] else 'No quorum', item['reason'])) + '</tr>'
        for item in delivery.get('cluster_consensus', []))
    updates = ''.join(f"<tr><td>{escape(item['vehicle_id'])}</td><td>{item['before']:.3f}</td>"
                      f"<td>{item['after']:.3f}</td><td>{escape(item['observation'])}</td></tr>"
                      for item in data.get('trust_updates', []) if item['observation'] != 'unobserved')
    event = delivery.get('rsu_event')
    status = 'RSU registered the alert' if event else 'No RSU registration in this run'
    return f'''<section class="infrastructure" id="infrastructure">
<div class="eyebrow">INFRASTRUCTURE PIPELINE</div><h2>From the incident to a trusted endpoint</h2>
<div class="pipeline"><span>Incident</span><span>Signed votes</span><span>Cluster heads</span><span>RSU</span><span>Dispatch outbox</span></div>
<div class="route"><b>{escape(status)}</b><p>{escape(path)}</p>
<small>Shortest available distance through trusted heads, up to 10 hops. Planning uses the incident snapshot; radio collisions and insufficient votes can prevent delivery.</small></div>
<div class="tiles"><div class="tile"><div class="big">{escape(route.get('hops') if route.get('hops') is not None else '—')}</div><div class="lbl">planned route hops</div></div>
<div class="tile"><div class="big">{escape(route.get('distance_m') if route.get('distance_m') is not None else '—')}</div><div class="lbl">planned distance in metres</div></div>
<div class="tile"><div class="big">{escape(analytics['cloud'])}</div><div class="lbl">{analytics['events']} stored events · {analytics['pending_dispatch']} queued requests</div></div>
<div class="tile"><div class="big">{escape(backhaul.get('dispatch', 'Unavailable'))}</div><div class="lbl">simulated emergency-service dispatch</div></div></div>
<h3>Collective voting at relay heads</h3><div class="table-wrap"><table><thead><tr><th>Head</th><th>Received votes</th><th>Decision</th><th>Reason</th></tr></thead>
<tbody>{rows or '<tr><td colspan="4">No intermediate relay head required or reachable.</td></tr>'}</tbody></table></div>
<h3>Trust after verified forwarding</h3><div class="table-wrap"><table><thead><tr><th>Vehicle</th><th>Before</th><th>After</th><th>Observation</th></tr></thead>
<tbody>{updates or '<tr><td colspan="4">No verified forwarding observation to credit.</td></tr>'}</tbody></table></div>
<p class="sub">Trust updates are simulated watchdog observations. Batch processing verifies each event’s aggregate BLS certificate; no multi-message cryptographic speedup is claimed.</p></section>'''
