# Contributing to HSRS

This document is for all teammates working on the HSRS monorepo.
Read it once before making your first commit.

---

## Branch Strategy

- `main` — stable, demo-ready. Never push directly.
- `develop` — integration branch. All feature branches merge here.
- Feature branches: `feature/<app>/<description>` e.g. `feature/booking/approval-workflow`
- Bug fixes: `fix/<app>/<description>`

## One App per PR (critical rule)

Each pull request should change files only within **one Django app**.
This prevents merge conflicts in migrations.

✅ Good PR: Changes only in `booking/` (serializers, views, templates)
❌ Bad PR:  Changes in `booking/` AND `room_inventory/` in the same PR

## Migrations (read carefully)

- **Only run `makemigrations` for your own app**:
  ```bash
  python manage.py makemigrations booking       # booking module owner
  python manage.py makemigrations room_inventory # room_inventory owner
  python manage.py makemigrations housekeeping  # housekeeping owner
  python manage.py makemigrations accounts      # shared — coordinate with team
  ```
- **Never edit a teammate's migration file** — this causes conflicts.
- If you pull and `migrate` fails, run `makemigrations` then `migrate` again.
- If migration conflicts arise, discuss in the group chat before squashing.

## Code Style

- Follow PEP 8. Use descriptive variable names.
- Add docstrings to all models, views, and serializers.
- Don't import models from other apps directly inside model files — use
  `settings.AUTH_USER_MODEL` for the User reference pattern.
- Use `app_name` namespacing in all `urls.py` files.

## Integration Contract Rule

If you change the **shape** of any API response that another module depends on
(listed in `README.md § Integration Contracts`), you **must**:
1. Update `README.md`
2. Notify the dependent module owner in the group chat
3. Bump the API version comment in the view

## Running the Project Locally

See `README.md § Setup` for the full setup guide.

Quick commands:
```bash
# First time
python -m venv venv
venv\Scripts\activate          # Windows
pip install -r requirements.txt
cp .env.example .env           # fill in your PostgreSQL credentials
python manage.py makemigrations
python manage.py migrate
python manage.py loaddata room_inventory/fixtures/initial_data.json
python manage.py createsuperuser

# Every time
venv\Scripts\activate
python manage.py runserver
```
