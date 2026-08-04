# Deploying StayHub for Testing — Complete Step-by-Step Guide (Debian + ngrok)

Follow every step in order. Each step has a **✓ Check** so you know you can move on.

**Target box:**
- Distro / user: Debian, `admin`
- App directory: `~/StayHub/hotel-management-system`
- Public URL: `https://npc0sh6x-8000.euw.devtunnels.ms` (VS Code Dev Tunnel)
- Stack: gunicorn (systemd) + WhiteNoise (static) + PostgreSQL — **no nginx, no certbot**
- `.env`: your project's current `.env` is used as-is (Postgres `hotel_db`/`hotel_user` already on the server)

> `.env` doesn't set `ALLOWED_HOSTS`/`DEBUG` → defaults `*` and `True` (fine for
> testing). `CSRF_TRUSTED_ORIGINS` already has `https://*.devtunnels.ms`.

---

## Step 0 — Commit & push your local changes (YOUR MACHINE, required!)

The server deploys from git, so nothing you changed locally exists on the box
until it's pushed. Run in the project folder:

```bash
git add -A
git commit -m "ngrok test-deploy setup + whitenoise + missing templates"
git push
```

**✓ Check:** `git status` shows a clean tree, and `git log --oneline -1` shows
your new commit.

---

## Step 1 — Copy the project + `.env` to the server (YOUR MACHINE, one time)

> `admin@ip-172-31-16-251` is the **private** IP. Use the **public** IP from the
> AWS console for SSH/rsync.

```bash
rsync -av --exclude venv --exclude .git --exclude media --exclude db.sqlite3 \
  . admin@<PUBLIC_IP>:~/StayHub/hotel-management-system/

scp -i your-key.pem .env admin@<PUBLIC_IP>:~/StayHub/hotel-management-system/.env
```

**✓ Check:** on the server, `ls ~/StayHub/hotel-management-system/.env` exists and
`ls ~/StayHub/hotel-management-system/deploy/` shows all 3 `.service`/`.sh` files.

---

## Step 2 — SSH in + update packages (SERVER, one time)

```bash
ssh admin@<PUBLIC_IP>
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3-venv python3-pip git unzip
```

**✓ Check:** `python3 --version` → see Step 3.

---

## Step 3 — Python version check (SERVER, CRITICAL)

Django 6.0 needs **Python 3.12+**.

```bash
python3 --version
```

- **`3.12` / `3.13` / `3.14`** → you're fine, skip the fallback below.
- **`3.11` or older (Debian 12 "bookworm" default)** → `pip install` will fail
  with "Requires-Python >=3.12". Install a newer Python from source:

```bash
sudo apt install -y build-essential zlib1g-dev libncurses-dev libgdbm-dev \
  libssl-dev libsqlite3-dev libreadline-dev libffi-dev libbz2-dev liblzma-dev wget
wget https://www.python.org/ftp/python/3.13.0/Python-3.13.0.tar.xz
tar -xf Python-3.13.0.tar.xz && cd Python-3.13.0
./configure --enable-optimizations --prefix=/usr/local
make -j$(nproc)
sudo make altinstall
cd ~ && python3.13 --version
```

  (`altinstall` keeps the system `python3` untouched; `python3.13` is the new one.)

**✓ Check:** `python3.13 --version` (or `python3 --version`) reports `3.12.x`+.
`deploy/deploy.sh` auto-picks `python3.13` → `python3.12` → `python3`, so this
is the only place the version matters.

---

## Step 4 — venv + dependencies (SERVER, one time)

```bash
cd ~/StayHub/hotel-management-system
python3.13 -m venv venv        # use python3.12 or python3 if that's your 3.12+
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt    # includes gunicorn + whitenoise
```

**✓ Check:** `pip show Django gunicorn whitenoise | grep -E "Name|Version"` lists
all three. If Django fails to install, your Python is < 3.12 — redo Step 3.

---

## Step 5 — Database + Django (SERVER, one time)

Postgres `hotel_db`/`hotel_user` already exist. Migrate and seed:

```bash
python manage.py check
python manage.py migrate --noinput
python manage.py create_sample_accounts    # optional sample staff
python manage.py seed_full_demo            # optional demo data
python manage.py collectstatic --noinput   # WhiteNoise serves these via gunicorn
```

**✓ Check:** `check` prints "System check identified no issues." and `migrate`
ends with "OK" (no "No migrations to apply" errors that suggest a broken DB user).

---

## Step 6 — Gunicorn as a systemd service (SERVER, one time)

```bash
sudo cp ~/StayHub/hotel-management-system/deploy/stayhub-gunicorn.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now stayhub-gunicorn
sudo systemctl status stayhub-gunicorn   # active (running)
```

Sanity check on the server (before ngrok):

```bash
curl http://127.0.0.1:8000/api/health/database/
# → {"status":"ok","database":"postgresql"}
curl -I http://127.0.0.1:8000/static/frontend/css/base.css
# → HTTP/1.1 200 OK   (WhiteNoise serving static)
```

**✓ Check:** both curl commands succeed. If not, `sudo journalctl -u stayhub-gunicorn -n 50`.

---

## Step 7 — ngrok tunnel (auto-starting service) (SERVER, one time)

```bash
curl -sSL https://ngrok-agent.s3.amazonaws.com/ngrok.asc | sudo tee /etc/apt/trusted.gpg.d/ngrok.asc >/dev/null
echo "deb https://ngrok-agent.s3.amazonaws.com bookworm main" | sudo tee /etc/apt/sources.list.d/ngrok.list
sudo apt update && sudo apt install -y ngrok

ngrok config add-authtoken YOUR_NGROK_AUTHTOKEN   # WITHOUT sudo!  → dashboard.ngrok.com

sudo cp ~/StayHub/hotel-management-system/deploy/stayhub-ngrok.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now stayhub-ngrok
sudo systemctl status stayhub-ngrok    # active (running)
```

**✓ Check:** `curl -I https://npc0sh6x-8000.euw.devtunnels.ms/` returns
`200 OK` from your laptop.

> If the domain errors with "reserved for another account": the authtoken must
> belong to the account that owns the domain. Or edit the unit's `ExecStart` to
> plain `ngrok http 8000`, then `sudo systemctl daemon-reload && sudo systemctl restart stayhub-ngrok`
> (CSRF wildcard `https://*.devtunnels.ms` still covers a random URL).

---

## Step 8 — Final verification (YOUR MACHINE)

Open in a browser: **https://npc0sh6x-8000.euw.devtunnels.ms**

- Splash page loads **with full styling** (fonts/CSS) → WhiteNoise ✓
- `/api/health/database/` → `{"status":"ok","database":"postgresql"}` ✓
- Try a sign-in / explore page → no 400/403/500 ✓

---

## Step 9 — Deploying updates later (SERVER)

```bash
cd ~/StayHub/hotel-management-system
bash deploy/deploy.sh
```

Script: `git pull --ff-only` → template check → `pip install -r requirements.txt`
(creates `venv` with a modern Python if missing) → `check` → `migrate` →
`collectstatic` → restart gunicorn. The ngrok tunnel restarts itself; kick it with:

```bash
sudo systemctl restart stayhub-ngrok
```

> On the box, `git pull` only works if the code was cloned (Step 1's rsync
> excludes `.git`). After a fresh rsync copy, `deploy.sh` prints "No .git — skipping
> git pull" and deploys the copied tree — that's expected. For pull-based updates
> later, either clone the repo on the server or keep using rsync + `deploy.sh`.

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `pip install` fails on Django | Python < 3.12 — do Step 3 (install `python3.13`) and recreate venv |
| 502 / connection refused | `sudo journalctl -u stayhub-gunicorn -n 50` — check `.env`, DB reachable |
| 400 Invalid HTTP_HOST | `ALLOWED_HOSTS` unset → default `*` works; only matters if you add it later |
| 403 CSRF | Exact origin (`https://…devtunnels.ms`) must be in `CSRF_TRUSTED_ORIGINS` |
| Pages unstyled (404 on /static/) | `collectstatic` not run, or WhiteNoise missing from `MIDDLEWARE` |
| ngrok tunnel errors | `ngrok config check`; domain owned by the account in the authtoken |

## ⚠️ Test-box caveats

- **Media uploads** (`/media/`) are served by Django only while `DEBUG=True`
  (default). Before production: `DEBUG=False` + nginx for `/media/` (or WhiteNoise
  media config), or uploads will 404.
- The URL is **public**: `DEBUG=True` + `ALLOWED_HOSTS=*` exposes Django debug
  pages to anyone with the link. Fine for testing — no real customer data.

## Notes vs the old AWS guide

- `DEPLOY_AWS_EC2.md` (Ubuntu 24.04 / `ubuntu` / `~/stayhub` / nginx + certbot) is
  the **production** path, not this test box.
- `deploy/nginx-stayhub.conf` is unused here; ngrok replaces it.
- `deploy/deploy.sh`, `deploy/stayhub-gunicorn.service`, `deploy/stayhub-ngrok.service`
  target Debian + `admin` + `~/StayHub/hotel-management-system`.