# HSRS — Hostel & Guest Room Booking System
### Part of ESPro ERP | Django 5 · PostgreSQL · DRF · HTMX · Alpine.js

---

## Table of Contents
1. [Setup](#setup)
2. [Running the Project](#running-the-project)
3. [Project Structure](#project-structure)
4. [Role & Test Accounts](#role--test-accounts)
5. [API Endpoints](#api-endpoints)
6. [Integration Contracts](#integration-contracts)
7. [Adding a New Module App](#adding-a-new-module-app)

---

## Setup

### Prerequisites
- Python 3.11+
- PostgreSQL 16 installed locally
- Git

### 1. Clone the Repo
```bash
git clone <repo-url>
cd hsrs
```

### 2. Create & Activate Virtual Environment
```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS/Linux
source venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure Environment
```bash
cp .env.example .env
```
Edit `.env` and fill in your PostgreSQL credentials:
```
DATABASE_URL=postgres://YOUR_USER:YOUR_PASSWORD@localhost:5432/hsrs_db
SECRET_KEY=some-long-random-string
DEBUG=True
```

### 5. Create the PostgreSQL Database
```sql
-- In psql or pgAdmin:
CREATE USER hsrs_user WITH PASSWORD 'hsrs_password';
CREATE DATABASE hsrs_db OWNER hsrs_user;
GRANT ALL PRIVILEGES ON DATABASE hsrs_db TO hsrs_user;
```

### 6. Run Migrations
```bash
python manage.py makemigrations accounts common
python manage.py makemigrations room_inventory housekeeping
python manage.py makemigrations booking
python manage.py migrate
```

### 7. Load Seed Fixtures
```bash
python manage.py loaddata room_inventory/fixtures/initial_data.json
```

### 8. Create Superuser
```bash
python manage.py createsuperuser
```

---

## Running the Project

```bash
python manage.py runserver
```

- **Web app:** http://127.0.0.1:8000/
- **Login:** http://127.0.0.1:8000/accounts/login/
- **Admin:** http://127.0.0.1:8000/admin/
- **DRF API:** http://127.0.0.1:8000/api/bookings/
- **JWT token:** http://127.0.0.1:8000/api/token/

> **Email:** In dev mode, all emails print to the terminal (Django console backend). No SMTP needed.

> **Celery:** Tasks run synchronously in dev (`CELERY_TASK_ALWAYS_EAGER=True`). No Redis/worker needed.

---

## Project Structure

```
hsrs/
├── config/                  Django project (settings split: base/dev/prod)
│   ├── settings/
│   │   ├── base.py          Core settings, shared by all environments
│   │   ├── dev.py           Development overrides (DEBUG=True)
│   │   └── prod.py          Production overrides (HTTPS, SMTP)
│   ├── urls.py              Root URL conf — namespaced app includes
│   └── celery.py            Celery app factory
│
├── accounts/                Shared: custom User model, RBAC, login
├── booking/                 MY MODULE: full application form + workflow
├── room_inventory/          Teammate stub: campus, guest house, event data
├── housekeeping/            Teammate stub: room status API
├── common/                  Shared utilities: base model, pagination, API response
│
├── templates/               All HTML templates
│   ├── base.html
│   ├── accounts/
│   └── booking/
│
├── static/css/main.css      Design system CSS
├── requirements.txt
├── .env.example
└── manage.py
```

---

## Role & Test Accounts

Create these via Django Admin or the management command. Suggested test credentials:

| Role | Username | Password | Post-login destination |
|---|---|---|---|
| REQUESTOR | `requestor1` | `Pass@1234` | `/booking/my-bookings/` |
| FACULTY_INCHARGE | `faculty1` | `Pass@1234` | `/booking/my-bookings/` |
| HOD_DIRECTOR | `hod1` | `Pass@1234` | `/booking/approvals/` |
| GUEST_HOUSE_TEAM | `ghteam1` | `Pass@1234` | `/booking/allotment/` |
| MANAGEMENT | `mgmt1` | `Pass@1234` | `/booking/approvals/management/` |
| ADMIN | `admin` | (set by createsuperuser) | `/admin/` |

Create test accounts via Admin: http://127.0.0.1:8000/admin/accounts/user/add/

---

## API Endpoints

### Authentication
```
POST /api/token/            → obtain JWT access + refresh tokens
POST /api/token/refresh/    → refresh access token
```

### Booking (JWT or Session Auth required)
```
GET    /api/bookings/               → list (requestors see own; others see all)
POST   /api/bookings/               → create DRAFT booking
GET    /api/bookings/<id>/          → retrieve booking detail
PATCH  /api/bookings/<id>/          → update DRAFT booking
DELETE /api/bookings/<id>/          → delete DRAFT booking
POST   /api/bookings/<id>/submit/   → submit (DRAFT → PENDING_HOD_APPROVAL)
POST   /api/bookings/<id>/cancel/   → cancel (DRAFT or PENDING_HOD → CANCELLED)
```

### Room Inventory Stub
```
GET /api/rooms/campuses/            → list all campuses
GET /api/rooms/guest-houses/?campus=<id>   → guest houses per campus
GET /api/rooms/availability/?guest_house=<id>&check_in=YYYY-MM-DD&check_out=YYYY-MM-DD
GET /api/rooms/events/?campus=<id>  → events per campus
```

### Housekeeping Stub
```
GET /api/housekeeping/room-status/?room=<id>  → CLEAN | DIRTY | OUT_OF_SERVICE
```

### User Profile
```
GET   /accounts/api/profile/   → own profile
PATCH /accounts/api/profile/   → update own profile
```

---

## Integration Contracts

These are the **fixed API shapes** that teammate modules must implement to replace the stubs.
Do not change the response shape without notifying dependent module owners.

---

### `room_inventory` contract (owner: teammate A)

#### `GET /api/rooms/guest-houses/?campus=<id>`
```json
[
  {
    "id": 1,
    "name": "Faculty Guest House",
    "campus": 1,
    "campus_name": "Main Campus",
    "total_rooms": 20,
    "contact_number": "9876543210"
  }
]
```

#### `GET /api/rooms/availability/?guest_house=<id>&check_in=YYYY-MM-DD&check_out=YYYY-MM-DD`
```json
{
  "guest_house_id": 1,
  "guest_house_name": "Faculty Guest House",
  "available_rooms": 12,
  "configurations": ["Single", "Double", "Suite"],
  "check_in": "2025-09-15",
  "check_out": "2025-09-17"
}
```

#### `GET /api/rooms/events/?campus=<id>`
```json
[
  {
    "id": 1,
    "name": "Annual Research Conference 2025",
    "event_date": "2025-09-15",
    "campus": 1,
    "campus_name": "Main Campus",
    "description": "..."
  }
]
```

---

### `housekeeping` contract (owner: teammate B)

#### `GET /api/housekeeping/room-status/?room=<id>`
```json
{
  "room_id": "42",
  "status": "CLEAN",
  "last_updated": "2025-07-22T10:30:00Z"
}
```
> `status` must be one of: `CLEAN`, `DIRTY`, `OUT_OF_SERVICE`

---

## Adding a New Module App

1. Create the app: `python manage.py startapp <appname>`
2. Add `'<appname>.apps.<AppName>Config'` to `INSTALLED_APPS` in `config/settings/base.py`
3. Create `<appname>/urls.py` with `app_name = "<appname>"`
4. Include it in `config/urls.py`: `path("<prefix>/", include("<appname>.urls", namespace="<appname>"))`
5. Run `python manage.py makemigrations <appname>` — **only for your own app**
6. Import permission classes from `accounts.permissions` — do not copy them
7. Document any new integration contracts in this README
