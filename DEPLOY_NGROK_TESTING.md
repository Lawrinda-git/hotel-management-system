# Deploying StayHub for Testing (Debian + ngrok)

Quick, simplified test deployment on the EC2 Debian box:

- **Distro / user:** Debian, `admin`
- **App directory:** `~/StayHub/hotel-management-system`
- **Public URL:** `https://contrapuntal-aliyah-nontropic.ngrok-free.dev` (static ngrok domain)
- **Stack:** gunicorn (systemd) + WhiteNoise (static files) + PostgreSQL — **no nginx, no certbot**
- **`.env`:** uses the project's current `.env` as-is (Postgres `hotel_db`/`hotel_user` already set up on the server)

`ALLOWED_HOSTS` / `DEBUG` are not set in `.env`, so Django defaults apply:
`ALLOWED_HOSTS=*` and `DEBUG=True` — fine for testing. `CSRF_TRUSTED_ORIGINS`
already includes `https://*.ngrok-free.dev`, and `PAYSTACK_RETURN_URL` already
points at the static domain.

---

## 1. Copy the project + `.env` to the server (one time)

From your local machine:

```bash
rsync -av --exclude venv --exclude .git --exclude media --exclude db.sqlite3 \
  . admin@<PUBLIC_IP>:~/StayHub/hotel-management-system/

scp -i your-key.pem .env admin@<PUBLIC_IP>:~/StayHub/hotel-management-system/.env
```

(Your instance's public IP — from the AWS console. The `admin@ip-172-31-16-251`
you see is the **private** IP; use the public one for SSH.)

## 2. System packages + ngrok (one time)

```bash
ssh admin@<PUBLIC_IP>
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3-venv python3-pip git unzip   # postgres already installed

# ngrok (free tier is fine; static domain needs an account)
curl -sSL https://ngrok-agent.s3.amazonaws.com/ngrok.asc | sudo tee /etc/apt/trusted.gpg.d/ngrok.asc >/dev/null
echo "deb https://ngrok-agent.s3.amazonaws.com buster main" | sudo tee /etc/apt/sources.list.d/ngrok.list
sudo apt update && sudo apt install -y ngrok

ngrok config add-authtoken YOUR_NGROK_AUTHTOKEN   # from https://dashboard.ngrok.com/get-started/your-authtoken
```

## 3. venv + dependencies (one time)

```bash
cd ~/StayHub/hotel-management-system
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt     # includes gunicorn + whitenoise
```

## 4. DB + Django (one time)

Postgres `hotel_db` / `hotel_user` already exist — just migrate and seed:

```bash
python manage.py check
python manage.py migrate --noinput
python manage.py create_sample_accounts    # optional sample staff
python manage.py seed_full_demo            # optional demo data
python manage.py collectstatic --noinput   # WhiteNoise serves these via gunicorn
```

## 5. Gunicorn as a systemd service (one time)

```bash
sudo cp ~/StayHub/hotel-management-system/deploy/stayhub-gunicorn.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now stayhub-gunicorn
sudo systemctl status stayhub-gunicorn   # should show active (running)
```

Sanity check on the server:

```bash
curl http://127.0.0.1:8000/api/health/database/   # → {"status":"ok","database":"postgresql"}
curl -I http://127.0.0.1:8000/static/frontend/css/base.css   # → 200 (WhiteNoise serving static)
```

## 6. Expose it with ngrok (auto-starting service)

Install the ngrok systemd service so the tunnel starts automatically at boot
and comes back if it drops:

```bash
sudo cp ~/StayHub/hotel-management-system/deploy/stayhub-ngrok.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now stayhub-ngrok
sudo systemctl status stayhub-ngrok   # should show active (running)
```

> It runs `ngrok http 8000 --url=https://contrapuntal-aliyah-nontropic.ngrok-free.dev`
> as the `admin` user, so it picks up the authtoken you saved in step 2. If the
> static domain errors with "reserved for another account", verify the authtoken
> belongs to the account that owns the domain — or switch the `ExecStart` line in
> the unit to plain `ngrok http 8000` and use the random URL (the CSRF wildcard
> already covers it), then `sudo systemctl daemon-reload && sudo systemctl restart stayhub-ngrok`.

Then open **https://contrapuntal-aliyah-nontropic.ngrok-free.dev** — you should
see the splash page with full styling.

> ⚠️ Two notes on this test setup:
> - **Media uploads** (`/media/`, hotel images, profile pictures) are served by
>   Django itself only while `DEBUG=True` (the default, since `.env` doesn't set it).
>   Before any production cut-over, set `DEBUG=False` and either bring back nginx
>   for `/media/` or add WhiteNoise media serving — otherwise uploads 404.
> - The URL is **public**: `DEBUG=True` + `ALLOWED_HOSTS=*` means anyone with the
>   link sees Django debug pages. Fine for testing; don't put real customer data
>   on this box.

## 7. Deploying updates later

```bash
cd ~/StayHub/hotel-management-system
./deploy/deploy.sh    # or: bash deploy/deploy.sh
```

The script: `git pull --ff-only` (skipped if no `.git`) → template existence
check → `pip install -r requirements.txt` (creates `venv` if missing) →
`manage.py check` → `migrate` → `collectstatic` → restart gunicorn.
It uses the `.env` already on the server. The ngrok tunnel restarts itself via
its systemd service — if it ever needs a manual kick:

```bash
sudo systemctl restart stayhub-ngrok
```

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| 502 / connection refused | `sudo journalctl -u stayhub-gunicorn -n 50` — check `.env` values, DB reachable |
| 400 Invalid HTTP_HOST | `ALLOWED_HOSTS` unset → default `*` works; only matters if you add it later |
| 403 CSRF | Ensure the exact origin (`https://…ngrok-free.dev`) is in `CSRF_TRUSTED_ORIGINS` |
| Pages unstyled (404 on /static/) | `collectstatic` not run, or WhiteNoise missing from `MIDDLEWARE` |
| ngrok tunnel errors | `ngrok config check`; domain owned by the account in the authtoken |

## Notes vs the old AWS guide

- `DEPLOY_AWS_EC2.md` (Ubuntu 24.04 / `ubuntu` user / `~/stayhub` / nginx +
  certbot) is the **production** path — not what this test box uses.
- `deploy/nginx-stayhub.conf` is unused here; ngrok replaces it.
- `deploy/deploy.sh`, `deploy/stayhub-gunicorn.service`, and the new
  `deploy/stayhub-ngrok.service` target Debian + `admin` + `~/StayHub/hotel-management-system`.
