# Bayanihan Ready

A local-first Django application for Filipino community leaders, volunteers, and beneficiaries to coordinate preparedness tasks, emergency supplies, and community needs.

## Local setup

Windows PowerShell:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Open <http://127.0.0.1:8000/>. The local database is SQLite (`db.sqlite3`).

Sign in with a superuser account to use the app administration area at <http://127.0.0.1:8000/admin/> to create accounts and assign each account a role: community leader, volunteer, or beneficiary. A leader can manage tasks and inventory; volunteers see tasks assigned to them and can update their status; signed-in users can report needs; beneficiaries see only the needs they reported.

Community leaders can create tasks from **Tasks → Create a task** and supplies from **Resources → Add resource**. Assign a task to a volunteer for it to appear in that volunteer's task list. Volunteers can open a community need and choose **Submit completion photo** to provide evidence that the support was delivered. A super admin reviews submissions under **Admin → Completion reviews**; approving one marks the need done, while rejecting it lets a volunteer submit updated evidence. Completion photos are served only to authorized admin users and are limited to 5 MB.

Set `DJANGO_SECRET_KEY` and `DJANGO_ALLOWED_HOSTS` in the environment before deploying. The built-in secret fallback and development server settings are for local use only.

Superusers are detected automatically through `is_superuser`; their community role does not limit management access. The Admin navigation and account-access fields are restricted to superusers on the server. **Admin → Manage users** supports account creation, search, roles, activation, staff access, and super admin access. Admins cannot disable or demote their own account through this form. Existing Django maintenance model URLs remain available to authorized staff.

## Maps

The dashboard map and the task, resource, and community-need location pickers use Leaflet with MapLibre GL and OpenFreeMap's public vector style. No map API key is needed. OpenFreeMap renders OpenStreetMap-derived data without using the OpenStreetMap Foundation's volunteer tile server, which may block applications that do not meet its usage policy. Map pins are optional; older records without coordinates remain valid and are not shown on the map. For community needs, pin a public support or meeting point rather than a household's exact home.

Map attribution for OpenFreeMap, OpenMapTiles, and OpenStreetMap contributors is shown on the map. OpenFreeMap's public service has no SLA; use a dedicated provider or self-host tiles if you need guaranteed availability.

## Checks

```powershell
python manage.py check
python manage.py test
```

Install dependencies after updating the project with `python -m pip install -r requirements.txt`; completion-photo uploads use Pillow for image validation.
