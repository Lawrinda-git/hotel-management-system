# Deploying StayHub on AWS EC2

This guide deploys StayHub (Django + PostgreSQL) on an EC2 instance running
**Ubuntu 24.04** with **nginx + gunicorn** and **Let's Encrypt** HTTPS.
It assumes you already have an EC2 instance running.

---

## 0. Prerequisites (one-time)

- Your instance is reachable via SSH, e.g. `ssh -i your-key.pem ubuntu@<PUBLIC_IP>`
- **Security Group** must allow inbound:
  - `22` (SSH, your IP only)
  - `80` (HTTP) and `443` (HTTPS) from `0.0.0.0/0`
- A domain name pointing to the instance's **Elastic IP** (so HTTPS works).
  If you have no domain yet, you can deploy on the raw IP over HTTP first
  (skip Step 5), then add a domain + HTTPS later.

Replace `<PUBLIC_IP>` / `your-domain.com` with your values throughout.

---

## 1. Copy the project to the instance

From your local machine:

```bash
cd "C:/Users/akyea/Desktop/Year 3/SEM 2/Software Engineering/project"
scp -i your-key.pem -r . ubuntu@<PUBLIC_IP>:~/stayhub
```

> Tip: exclude junk — `rsync -av --exclude venv --exclude .git --exclude media --exclude db.sqlite3 . ubuntu@<PUBLIC_IP>:~/stayhub/`

---

## 2. Install system packages + Python 3.12

```bash
ssh -i your-key.pem ubuntu@<PUBLIC_IP>
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3.12 python3.12-venv python3-pip \
  nginx postgresql postgresql-contrib libpq-dev certbot python3-certbot-nginx git
```

## 3. Set up PostgreSQL

```bash
sudo -u postgres psql
CREATE USER stayhub WITH PASSWORD 'CHANGE_ME_STRONG_PASSWORD';
CREATE DATABASE stayhub OWNER stayhub;
GRANT ALL PRIVILEGES ON DATABASE stayhub TO stayhub;
\q
```

## 4. Create the venv, install deps, configure `.env`

```bash
cd ~/stayhub
python3.12 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt   # gunicorn is pinned in requirements.txt — no separate install needed
```

Create `~/stayhub/.env` (copy the shape of your local `.env`):

```bash
nano ~/stayhub/.env
```

```env
# ── Production critical ──
SECRET_KEY=REPLACE_WITH_RANDOM_50_CHAR_STRING
DEBUG=False
ALLOWED_HOSTS=your-domain.com,<PUBLIC_IP>
DB_ENGINE=postgres
DB_NAME=stayhub
DB_USER=stayhub
DB_PASSWORD=CHANGE_ME_STRONG_PASSWORD
DB_HOST=127.0.0.1
DB_PORT=5432
CSRF_TRUSTED_ORIGINS=https://your-domain.com,http://<PUBLIC_IP>

# ── Email (already working via Gmail SMTP) ──
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=officialstayhub@gmail.com
SMTP_PASSWORD=YOUR_GMAIL_APP_PASSWORD
SMTP_USE_TLS=True
DEFAULT_FROM_EMAIL=StayHub <officialstayhub@gmail.com>

# ── Google OAuth (optional; set the deployed callback too) ──
GOOGLE_OAUTH_CLIENT_ID=...
GOOGLE_OAUTH_CLIENT_SECRET=...
GOOGLE_OAUTH_REDIRECT_URI=https://your-domain.com/api/auth/google/callback/
GOOGLE_OAUTH_REDIRECT_URIS=https://your-domain.com/api/auth/google/callback/

# ── Payments ──
PAYSTACK_SECRET_KEY=...
PAYSTACK_PUBLIC_KEY=...
PAYSTACK_RETURN_URL=https://your-domain.com/booking/
```

> Generate a secret key with: `python3 -c "import secrets; print(secrets.token_urlsafe(50))"`
> Gmail note: if SMTP auth is the app's `EMAIL_HOST_PASSWORD`, it must be a
> **Gmail App Password** (2FA enabled), not the account password.

Then run Django checks, migrations, seed, and collect static:

```bash
cd ~/stayhub
source venv/bin/activate
python manage.py check                 # catches config errors (e.g. DEBUG=False without SECRET_KEY) before they hit the server
python manage.py migrate --noinput
python manage.py create_sample_accounts      # optional sample staff
python manage.py seed_full_demo              # optional full demo dataset (hotels, rooms, reservations, billing…)
# python manage.py seed_demo_data            # smaller legacy demo (superseded by seed_full_demo)
python manage.py collectstatic --noinput
```

## 5. Gunicorn + systemd

Install the service unit and start it:

```bash
sudo cp ~/stayhub/deploy/stayhub-gunicorn.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now stayhub-gunicorn
sudo systemctl status stayhub-gunicorn   # should show active (running)
```

Quick sanity check on the server itself:

```bash
curl -H "Host: your-domain.com" http://127.0.0.1:8000/api/health/database/   # → {"status":"ok","database":"postgresql"}
curl http://127.0.0.1:8000/   # splash page also returns 200
```

## 6. nginx

```bash
sudo cp ~/stayhub/deploy/nginx-stayhub.conf /etc/nginx/sites-available/stayhub
sudo ln -s /etc/nginx/sites-available/stayhub /etc/nginx/sites-enabled/
sudo nginx -t        # test config
sudo systemctl reload nginx
```

> If the file was edited, replace `your-domain.com` and `/home/ubuntu/stayhub`
> with your real values first.

## 7. HTTPS with Let's Encrypt (if you have a domain)

```bash
sudo certbot --nginx -d your-domain.com
sudo certbot renew --dry-run
```

## 8. Deploying updates later

The bundled script does the same thing as the manual steps below — pull → pip → checks → migrate → collectstatic → restart:

```bash
cd ~/stayhub && git pull
source venv/bin/activate
pip install -r requirements.txt
python manage.py check
python manage.py migrate --noinput
python manage.py collectstatic --noinput
sudo systemctl restart stayhub-gunicorn
sudo systemctl reload nginx
```

Or run the bundled script:

```bash
sudo chmod +x ~/stayhub/deploy/deploy.sh
~/stayhub/deploy/deploy.sh
```

> The script fails fast: it aborts with a clear message if `~/stayhub` or `~/stayhub/.env` is
> missing, stops if `git pull --ff-only` fails (commit/stash local changes first), checks that
> every template referenced in `frontend/views.py` / `frontend/urls.py` actually exists on disk
> (so uncommitted templates can't 500 a page in production), and runs `python manage.py check`
> before migrating. Override the app directory with
> `STAYHUB_DIR=/path/to/stayhub bash ~/stayhub/deploy/deploy.sh` if needed.

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| 502 Bad Gateway | `sudo journalctl -u stayhub-gunicorn -n 50` — usually missing `gunicorn` or a `.env` value |
| 400 Bad Request (Invalid HTTP_HOST) | `ALLOWED_HOSTS` doesn't include the host/domain used |
| 403 CSRF | Add the exact origin (with `https://`) to `CSRF_TRUSTED_ORIGINS` |
| Static files 404 | `collectstatic` not run, or nginx `alias` path wrong |
| Media uploads 404 | Check `/home/ubuntu/stayhub/media` exists & `media/` is owned by the `ubuntu` user |
| Email fails on server | SMTP port 587 must be allowed; Gmail App Password required |

---

## What the deploy/ files do

- `deploy/stayhub-gunicorn.service` — systemd unit running gunicorn on `127.0.0.1:8000`, auto-restarts on crash/boot.
- `deploy/nginx-stayhub.conf` — nginx reverse proxy: serves `/static/` and `/media/` directly, proxies everything else to gunicorn, gzip on.
- `deploy/deploy.sh` — update deploy: `git pull --ff-only` → `pip install -r requirements.txt` (gunicorn included) → `manage.py check` → `migrate` → `collectstatic` → restart gunicorn/nginx. Fails fast if `.env` is missing and prints clear errors.

> ✅ The `deploy/` files are **tracked in git** (commit `1cb9c98`), so a `git clone` on a
> fresh instance includes them — no manual copy needed. The `scp -r .` / `rsync` step in
> section 1 is still how you get the full project onto the box before the first deploy.
