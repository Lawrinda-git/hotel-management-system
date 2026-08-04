#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════════
#  StayHub — EC2 deploy script (Ubuntu 24.04, ubuntu user)
# ═══════════════════════════════════════════════════════════════════════════
#  USAGE:
#      bash ~/stayhub/deploy/deploy.sh
#
#  This script performs an UPDATE deploy: pull → pip → checks → migrate →
#  collectstatic → restart. The one-time server setup (system packages,
#  PostgreSQL, .env, nginx, certbot) is documented in DEPLOY_AWS_EC2.md.
#
#  Override the app directory with STAYHUB_DIR=/path/to/stayhub if needed.
# ═══════════════════════════════════════════════════════════════════════════
set -euo pipefail

APP_DIR="${STAYHUB_DIR:-$HOME/stayhub}"
ENV_FILE="${APP_DIR}/.env"

# ── Guards: fail fast with a clear message instead of a cryptic stack trace ──
if [[ ! -d "${APP_DIR}" ]]; then
    echo "ERROR: ${APP_DIR} does not exist. Set up the instance first (see DEPLOY_AWS_EC2.md)." >&2
    exit 1
fi
cd "${APP_DIR}"

if [[ ! -f "${ENV_FILE}" ]]; then
    echo "ERROR: ${ENV_FILE} is missing. Copy .env.example and fill in production values." >&2
    exit 1
fi

# ── 1) Pull the latest code ────────────────────────────────────────────────
# Skipped automatically when the tree was copied via scp/rsync (no .git).
if [[ -d .git ]]; then
    echo "==> Pulling latest code"
    if ! git pull --ff-only; then
        echo "ERROR: 'git pull --ff-only' failed. Commit or stash local changes,"
        echo "       or resolve the divergence, then re-run the deploy." >&2
        exit 1
    fi
else
    echo "==> No .git directory found — skipping git pull (code copied via scp/rsync)"
fi

# ── 2) Install Python dependencies (gunicorn is pinned in requirements.txt) ─
echo "==> Installing Python dependencies"
source venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

# ── 3) Django checks, migrations, static files ─────────────────────────────
echo "==> Running Django system checks"
python manage.py check

echo "==> Running migrations"
python manage.py migrate --noinput

echo "==> Collecting static files"
python manage.py collectstatic --noinput

# ── 4) Restart the services ────────────────────────────────────────────────
echo "==> Restarting gunicorn"
sudo systemctl restart stayhub-gunicorn

echo "==> Reloading nginx"
sudo systemctl reload nginx

# ── 5) Report the result ───────────────────────────────────────────────────
echo "==> Deploy complete."
sudo systemctl status stayhub-gunicorn --no-pager | head -5 || true
