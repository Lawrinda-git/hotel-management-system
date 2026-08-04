#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════════
#  StayHub — ngrok test-deploy script (Debian, admin user)
# ═══════════════════════════════════════════════════════════════════════════
#  USAGE:
#      bash ~/StayHub/hotel-management-system/deploy/deploy.sh
#
#  This script performs an UPDATE deploy: pull → template check → pip → checks →
#  migrate → collectstatic → restart gunicorn. The app is exposed over the
#  internet with ngrok (no nginx, no certbot) — see DEPLOY_NGROK_TESTING.md.
#  It uses the .env already present in the app directory (your current .env).
#
#  Override the app directory with STAYHUB_DIR=/path/to/app if needed.
# ═══════════════════════════════════════════════════════════════════════════
set -euo pipefail

APP_DIR="${STAYHUB_DIR:-$HOME/StayHub/hotel-management-system}"
ENV_FILE="${APP_DIR}/.env"

# ── Guards: fail fast with a clear message instead of a cryptic stack trace ──
if [[ ! -d "${APP_DIR}" ]]; then
    echo "ERROR: ${APP_DIR} does not exist. Set up the instance first (see DEPLOY_NGROK_TESTING.md)." >&2
    exit 1
fi
cd "${APP_DIR}"

if [[ ! -f "${ENV_FILE}" ]]; then
    echo "ERROR: ${ENV_FILE} is missing. Copy your current local .env to the server." >&2
    exit 1
fi

# ── 1) Pull the latest code ────────────────────────────────────────────────
# Skipped automatically when the tree was copied via scp/rsync (no .git).
if [[ -d .git ]]; then
    echo "==> Pulling latest code"
    if ! git pull --ff-only; then
        echo "ERROR: 'git pull --ff-only' failed. Commit or stash local changes," >&2
        echo "       or resolve the divergence, then re-run the deploy." >&2
        exit 1
    fi
else
    echo "==> No .git directory found — skipping git pull (code copied via scp/rsync)"
fi

# ── 2) Verify every template referenced in code exists on disk ────────────
# A page whose template is missing (e.g. added locally but never committed)
# would 500 in production. Fail fast with a clear message instead.
# Note: checks literal "frontend/*.html" strings in frontend/views.py and
# frontend/urls.py only (commented-out render() calls would be a false alarm).
echo "==> Verifying referenced templates exist"
template_list="$(grep -hoP 'frontend/[A-Za-z0-9_/.-]+\.html' frontend/views.py frontend/urls.py | sort -u)" || true
if [[ -z "${template_list}" ]]; then
    echo "ERROR: No templates detected — the grep pattern in deploy.sh may be broken." >&2
    exit 1
fi
missing=0
while IFS= read -r tpl; do
    if [[ ! -f "frontend/templates/${tpl}" ]]; then
        echo "ERROR: Template referenced in code but missing on disk: ${tpl}" >&2
        echo "       It was probably added to the repo but never committed." >&2
        echo "       Commit it (git add + git commit + git push), then re-run the deploy." >&2
        missing=1
    fi
done <<< "${template_list}"
if (( missing )); then
    exit 1
fi

# ── 3) Install Python dependencies (gunicorn pinned in requirements.txt) ───
echo "==> Installing Python dependencies"
if [[ ! -d venv ]]; then
    echo "==> Creating virtualenv (python3 -m venv venv)"
    python3 -m venv venv
fi
source venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

# ── 4) Django checks, migrations, static files ─────────────────────────────
echo "==> Running Django system checks"
python manage.py check

echo "==> Running migrations"
python manage.py migrate --noinput

echo "==> Collecting static files"
python manage.py collectstatic --noinput

# ── 5) Restart gunicorn ────────────────────────────────────────────────────
echo "==> Restarting gunicorn"
sudo systemctl restart stayhub-gunicorn

# ── 6) Report the result ───────────────────────────────────────────────────
echo "==> Deploy complete."
sudo systemctl status stayhub-gunicorn --no-pager | head -5 || true
sudo systemctl status stayhub-ngrok --no-pager | head -5 || true
