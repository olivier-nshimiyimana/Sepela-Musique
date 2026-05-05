# Sepela Musique

Sepela Musique is a Django web app for publishing songs/videos, collecting email-confirmed votes, and moderating content through an admin workspace.

## Features

- Public home feed with featured published tracks and artist leaderboard.
- Email-confirmed voting flow (`vote_view` -> confirmation email -> token confirmation).
- Artist accounts with upload/edit/delete song management.
- Admin workspace for:
  - site settings (title/contact/outbound email),
  - moderation queue (publish/reject),
  - recent songs moderation (hide/unhide/reset votes),
  - vote management per song.
- Bilingual UI (`fr` / `en`) using `ui_i18n` template tags.

## Stack

- Backend: Python, Django
- Frontend: Django templates, Bootstrap + custom CSS/JS
- DB: SQLite (default), can be switched for production
- Media: local filesystem (`/media`)

## Local Development

### 1) Create environment and install dependencies

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### 2) Configure environment

Copy `.env.example` to `.env` and set values.

```bash
copy .env.example .env
```

### 3) Run migrations and start server

```bash
python manage.py migrate
python manage.py runserver
```

App runs at `http://127.0.0.1:8000/`.

## Important Environment Variables

Core:

- `DJANGO_SECRET_KEY`
- `DJANGO_DEBUG`
- `DJANGO_ALLOWED_HOSTS` (comma-separated)
- `CSRF_TRUSTED_ORIGINS` (comma-separated full origins)

Security / HTTPS:

- `SECURE_SSL_REDIRECT`
- `SESSION_COOKIE_SECURE`
- `CSRF_COOKIE_SECURE`
- `SECURE_HSTS_SECONDS`
- `SECURE_HSTS_INCLUDE_SUBDOMAINS`
- `SECURE_HSTS_PRELOAD`
- `USE_X_FORWARDED_PROTO` (set `true` behind reverse proxy)

Email:

- `DJANGO_EMAIL_BACKEND`
- `EMAIL_HOST`
- `EMAIL_PORT`
- `EMAIL_HOST_USER`
- `EMAIL_HOST_PASSWORD`
- `EMAIL_USE_TLS`
- `DEFAULT_FROM_EMAIL`

## Moderation Statuses

Song `status` values currently used:

- `0` = pending
- `1` = accepted (still in moderation queue)
- `2` = published (visible on home)
- `3` = rejected
- `4` = hidden (admin-hidden from public feed)

## Render Deployment (Recommended)

### Build command

```bash
pip install -r requirements.txt && python manage.py migrate && python manage.py collectstatic --noinput
```

### Start command

```bash
gunicorn music.wsgi:application
```

### Minimum Render environment values

- `DJANGO_SECRET_KEY=<strong-secret>`
- `DJANGO_DEBUG=false`
- `DJANGO_ALLOWED_HOSTS=<your-render-host>`
- `CSRF_TRUSTED_ORIGINS=https://<your-render-host>`
- `SECURE_SSL_REDIRECT=true`
- `SESSION_COOKIE_SECURE=true`
- `CSRF_COOKIE_SECURE=true`
- `SECURE_HSTS_SECONDS=31536000`
- `SECURE_HSTS_INCLUDE_SUBDOMAINS=true`
- `SECURE_HSTS_PRELOAD=true`
- `USE_X_FORWARDED_PROTO=true`

Optional (no shell access admin bootstrap):

- `DJANGO_CREATE_SUPERUSER=true`
- `DJANGO_SUPERUSER_EMAIL=<admin-email>`
- `DJANGO_SUPERUSER_PASSWORD=<strong-password>`
- `DJANGO_SUPERUSER_FIRST_NAME=Admin`
- `DJANGO_SUPERUSER_LAST_NAME=User`

## Static / Favicon Notes

- `STATIC_ROOT` is configured as `staticfiles` for `collectstatic`.
- Layouts include icon tags for modern and Apple clients.
- URL fallbacks are configured for:
  - `/favicon.ico`
  - `/favicon.png`
  - `/apple-touch-icon.png`
  - `/apple-touch-icon-precomposed.png`

These currently redirect to the existing brand image in `static/images/logos/sepelamusique.png`.

## Quick Health Checks

```bash
python manage.py check
python manage.py check --deploy
```
