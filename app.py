from flask import Flask, render_template, jsonify, request, redirect, url_for, session
from datetime import timedelta
from werkzeug.middleware.proxy_fix import ProxyFix
import json
import logging.config
import os
import structlog
import datetime

from middleware import HealthCheckMiddleware


# ---------------------------------------------------------------------------
# Environment variables
# ---------------------------------------------------------------------------

LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO').upper()
LOG_FORMAT = os.environ.get('LOG_FORMAT', 'plain').lower()  # "json" for production, "plain" for local dev
TRUSTED_HOSTS = os.environ.get('TRUSTED_HOSTS', 'localhost:5000,127.0.0.1:5000')
SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-change-me')
MAGIC_LINK_TOKEN = os.environ.get('MAGIC_LINK_TOKEN', '')
SESSION_LIFETIME_DAYS = int(os.environ.get('SESSION_LIFETIME_DAYS', '30'))


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

if LOG_FORMAT == 'json':
    log_renderer = structlog.processors.JSONRenderer()
else:
    log_renderer = structlog.dev.ConsoleRenderer()

logging.config.dictConfig({
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'structlog': {
            '()': structlog.stdlib.ProcessorFormatter,
            'processors': [
                structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                log_renderer,
            ],
        },
    },
    'handlers': {
        'stdout': {
            'class': 'logging.StreamHandler',
            'stream': 'ext://sys.stdout',
            'formatter': 'structlog',
        },
    },
    'root': {
        'level': LOG_LEVEL,
        'handlers': ['stdout'],
    },
})

structlog.configure(
    processors=[
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt='iso'),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
    ],
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
)


# ---------------------------------------------------------------------------
# App creation
# ---------------------------------------------------------------------------

app = Flask(__name__)
DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')

# ---- Middleware ----
# Trust one level of proxy headers so request.remote_addr, request.scheme, etc.
# reflect the real client values when running behind an AWS ALB.
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1)
# Handle health checks at the WSGI layer before Werkzeug's TRUSTED_HOSTS
# validation, which rejects ALB probes that use the container IP as Host.
app.wsgi_app = HealthCheckMiddleware(app.wsgi_app)

# ---- Security & auth ----
app.config['TRUSTED_HOSTS'] = [h.strip() for h in TRUSTED_HOSTS.split(',') if h.strip()]
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=SESSION_LIFETIME_DAYS)
app.secret_key = SECRET_KEY

# ---- Startup logging ----
if MAGIC_LINK_TOKEN:
    app.logger.info('Magic link auth enabled')
else:
    app.logger.warning('MAGIC_LINK_TOKEN not set - app is in open access mode')
app.logger.info('Application starting, data_dir=%s, log_level=%s, trusted_hosts=%s', DATA_DIR, LOG_LEVEL, app.config['TRUSTED_HOSTS'])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_json(filename):
    filepath = os.path.join(DATA_DIR, filename)
    try:
        with open(filepath, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        app.logger.error('Data file not found: %s', filepath)
        raise
    except json.JSONDecodeError:
        app.logger.error('Invalid JSON in file: %s', filepath)
        raise


def save_json(filename, data):
    filepath = os.path.join(DATA_DIR, filename)
    try:
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
    except (OSError, TypeError, ValueError) as exc:
        app.logger.error('Failed to write JSON file %s: %s', filepath, exc)
        raise


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

@app.before_request
def require_auth():
    if not MAGIC_LINK_TOKEN:
        return None
    if request.endpoint in ('auth', 'static'):
        return None
    if session.get('authenticated'):
        return None
    # When the Host header isn't in TRUSTED_HOSTS (e.g. ALB probes using the
    # container IP), Flask sets url_adapter to None.  Rendering a template that
    # calls url_for() would crash with AttributeError, so fall back to a
    # plain-text 403.
    try:
        return render_template('access_required.html'), 403
    except AttributeError:
        return 'Forbidden', 403


@app.route('/auth/<token>')
def auth(token):
    if not MAGIC_LINK_TOKEN or token != MAGIC_LINK_TOKEN:
        app.logger.warning('Failed auth attempt from %s', request.remote_addr)
        return render_template('access_required.html'), 403
    session.permanent = True  # Use PERMANENT_SESSION_LIFETIME (30 days) instead of browser-session cookie
    session['authenticated'] = True
    app.logger.info('User authenticated via magic link')
    return redirect(url_for('index'))


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route('/')
def index():
    gems = load_json('gems.json')
    gems = [g for g in gems if not g.get('pending')]
    saved = load_json('saved.json')
    saved_ids = [item['id'] for item in saved]

    return render_template('index.html',
                         gems=gems,
                         saved=saved,
                         saved_ids=saved_ids)


@app.route('/api/save/<gem_id>', methods=['POST'])
def save_gem(gem_id):
    gems = load_json('gems.json')
    saved = load_json('saved.json')

    # Find the gem
    gem = next((g for g in gems if g['id'] == gem_id), None)
    if not gem:
        return jsonify({'error': 'Gem not found'}), 404

    # Check if already saved
    if any(s['id'] == gem_id for s in saved):
        return jsonify({'error': 'Already saved'}), 400

    saved.append(gem)
    save_json('saved.json', saved)

    return jsonify({'success': True, 'gem': gem})


@app.route('/api/unsave/<gem_id>', methods=['POST'])
def unsave_gem(gem_id):
    saved = load_json('saved.json')

    # Remove the gem
    saved = [s for s in saved if s['id'] != gem_id]
    save_json('saved.json', saved)

    return jsonify({'success': True})


@app.route('/api/saved')
def get_saved():
    saved = load_json('saved.json')
    return jsonify(saved)


@app.route('/admin')
def admin():
    gems = load_json('gems.json')
    pending = [g for g in gems if g.get('pending')]
    active = [g for g in gems if not g.get('pending')]
    access_requests = load_json('access_requests.json')
    pending_access_count = len([r for r in access_requests if r.get('status') == 'pending'])
    reports = load_json('reports.json')
    pending_reports_count = len([r for r in reports if r.get('status') == 'pending'])
    return render_template('admin.html', pending=pending, active=active, pending_access_count=pending_access_count, pending_reports_count=pending_reports_count)


@app.route('/admin/gem', methods=['GET', 'POST'])
@app.route('/admin/gem/<gem_id>', methods=['GET', 'POST'])
def admin_form(gem_id=None):
    gems = load_json('gems.json')

    if request.method == 'POST':
        gem_data = {
            'id': gem_id or request.form['name'].lower().replace(' ', '-'),
            'name': request.form['name'],
            'category': request.form['category'],
            'description': request.form['description'],
            'url': request.form['url'],
            'requester_name': request.form.get('requester_name', ''),
            'requester_email': request.form.get('requester_email', ''),
            'school': request.form.get('school', ''),
            'role': request.form.get('role', ''),
            'bot_type': request.form.get('bot_type', ''),
            'pending': 'pending' in request.form,
            'restricted': 'restricted' in request.form
        }

        if gem_id:
            # Update existing gem
            gems = [gem_data if g['id'] == gem_id else g for g in gems]
        else:
            # Add new gem
            gems.append(gem_data)

        save_json('gems.json', gems)
        return redirect(url_for('admin'))

    schools = load_json('schools.json')
    gem = next((g for g in gems if g['id'] == gem_id), None) if gem_id else None
    return render_template('admin_form.html', gem=gem, schools=schools)


@app.route('/admin/delete/<gem_id>', methods=['POST'])
def admin_delete(gem_id):
    gems = load_json('gems.json')
    gems = [g for g in gems if g['id'] != gem_id]
    save_json('gems.json', gems)

    # Also remove from saved if present
    saved = load_json('saved.json')
    saved = [s for s in saved if s['id'] != gem_id]
    save_json('saved.json', saved)

    return jsonify({'success': True})


@app.route('/request', methods=['GET', 'POST'])
def request_form():
    schools = load_json('schools.json')

    if request.method == 'POST':
        gems = load_json('gems.json')
        new_gem = {
            'id': request.form['bot_name'].lower().replace(' ', '-'),
            'name': request.form['bot_name'],
            'category': request.form['category'],
            'description': request.form['bot_description'],
            'url': request.form['bot_url'],
            'requester_name': request.form['requester_name'],
            'requester_email': request.form['requester_email'],
            'school': request.form['school'],
            'role': request.form['role'],
            'bot_type': request.form['bot_type'],
            'pending': True
        }
        gems.append(new_gem)
        save_json('gems.json', gems)
        return redirect(url_for('request_success'))

    return render_template('request_form.html', schools=schools)


@app.route('/request/success')
def request_success():
    return render_template('request_success.html')


@app.route('/access-request/success')
def access_request_success():
    return render_template('access_request_success.html')


@app.route('/access-request/<gem_id>', methods=['GET', 'POST'])
def access_request_form(gem_id):
    gems = load_json('gems.json')
    gem = next((g for g in gems if g['id'] == gem_id), None)
    if not gem:
        return 'Bot not found', 404

    schools = load_json('schools.json')

    if request.method == 'POST':
        access_requests = load_json('access_requests.json')
        new_request = {
            'id': 'ar-' + str(int(datetime.datetime.now().timestamp())),
            'gem_id': gem_id,
            'gem_name': gem['name'],
            'name': request.form['name'],
            'email': request.form['email'],
            'position': request.form.get('position', ''),
            'role': request.form.get('role', ''),
            'department': request.form.get('department', ''),
            'school': request.form.get('school', ''),
            'reason': request.form.get('reason', ''),
            'status': 'pending',
            'submitted_at': datetime.datetime.now().isoformat()
        }
        access_requests.append(new_request)
        save_json('access_requests.json', access_requests)
        return redirect(url_for('access_request_success'))

    return render_template('access_request_form.html', gem=gem, schools=schools)


@app.route('/admin/access-requests')
def admin_access_requests():
    access_requests = load_json('access_requests.json')
    pending = [r for r in access_requests if r.get('status') == 'pending']
    resolved = [r for r in access_requests if r.get('status') != 'pending']
    return render_template('admin_access_requests.html', pending=pending, resolved=resolved)


@app.route('/admin/access-requests/<request_id>/approve', methods=['POST'])
def approve_access_request(request_id):
    access_requests = load_json('access_requests.json')
    for r in access_requests:
        if r['id'] == request_id:
            r['status'] = 'approved'
            break
    save_json('access_requests.json', access_requests)
    return redirect(url_for('admin_access_requests'))


@app.route('/admin/access-requests/<request_id>/reject', methods=['POST'])
def reject_access_request(request_id):
    access_requests = load_json('access_requests.json')
    for r in access_requests:
        if r['id'] == request_id:
            r['status'] = 'rejected'
            break
    save_json('access_requests.json', access_requests)
    return redirect(url_for('admin_access_requests'))


@app.route('/report/success')
def report_success():
    return render_template('report_success.html')


@app.route('/report/<gem_id>', methods=['GET', 'POST'])
def report_form_page(gem_id):
    gems = load_json('gems.json')
    gem = next((g for g in gems if g['id'] == gem_id), None)
    if not gem:
        return 'Bot not found', 404

    if request.method == 'POST':
        reports = load_json('reports.json')
        new_report = {
            'id': 'rpt-' + str(int(datetime.datetime.now().timestamp())),
            'gem_id': gem_id,
            'gem_name': gem['name'],
            'reporter_name': request.form['reporter_name'],
            'reporter_email': request.form['reporter_email'],
            'issue_type': request.form['issue_type'],
            'description': request.form['description'],
            'status': 'pending',
            'submitted_at': datetime.datetime.now().isoformat()
        }
        reports.append(new_report)
        save_json('reports.json', reports)
        return redirect(url_for('report_success'))

    return render_template('report_form.html', gem=gem)


@app.route('/admin/reports')
def admin_reports():
    reports = load_json('reports.json')
    pending = [r for r in reports if r.get('status') == 'pending']
    resolved = [r for r in reports if r.get('status') != 'pending']
    return render_template('admin_reports.html', pending=pending, resolved=resolved)


@app.route('/admin/reports/<report_id>/resolve', methods=['POST'])
def resolve_report(report_id):
    reports = load_json('reports.json')
    for r in reports:
        if r['id'] == report_id:
            r['status'] = 'resolved'
            break
    save_json('reports.json', reports)
    return redirect(url_for('admin_reports'))


@app.route('/admin/reports/<report_id>/dismiss', methods=['POST'])
def dismiss_report(report_id):
    reports = load_json('reports.json')
    for r in reports:
        if r['id'] == report_id:
            r['status'] = 'dismissed'
            break
    save_json('reports.json', reports)
    return redirect(url_for('admin_reports'))


if __name__ == '__main__':
    app.run(debug=True, port=5000)
