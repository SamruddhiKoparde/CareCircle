# CareCircle — Elderly Care & Medication Management

CareCircle is a patient-controlled elderly care coordination platform designed to help patients, family members, and authorized caregivers manage everyday healthcare responsibilities together.

It brings medication schedules, dose confirmations, appointments, caregiver permissions, and activity history into one shared platform.

## Problem

Elderly people may depend on multiple family members or caregivers to manage medications and appointments. When information is scattered across messages, calls, and personal reminders, important updates can be missed and accountability becomes difficult.

## Solution

CareCircle provides a centralized care coordination platform where patients control who can access their information and what each person is allowed to do.

## Key Features

- **Patient-controlled access:** Patients can invite family members and caregivers.
- **Granular permissions:** Control access to profile information, medications, dose confirmations, and appointments.
- **Medication management:** Create, update, and manage medication schedules.
- **Dose tracking:** Track upcoming, awaiting-confirmation, patient-confirmed, caregiver-confirmed, and missed doses.
- **Caregiver accountability:** Record who confirmed a dose, their role, and the confirmation time.
- **Appointment management:** Schedule, update, and cancel medical appointments.
- **Activity history:** Maintain an audit trail of important care-related actions.
- **Dashboard:** View medication and appointment summaries.
- **Notification processing:** Queue notifications and retry failed deliveries.

## Technology Stack

| Layer | Technology |
|---|---|
| Backend | Python, FastAPI |
| Database | SQLite |
| ORM | SQLAlchemy |
| Frontend | HTML, CSS, JavaScript |
| Authentication | Session-cookie authentication |
| Scheduling | APScheduler |
| Testing | Pytest, HTTPX |

## Application Architecture

The application uses a FastAPI backend to handle authentication, permissions, medication records, appointments, dashboard data, and notification processing.

The frontend communicates with the backend through REST API endpoints.

SQLite stores patient profiles, care-team members, medications, dose records, appointments, notifications, and audit logs.

## Run Locally

### 1. Clone the repository

```bash
git clone YOUR_GITHUB_REPOSITORY_URL
cd CareCircle
```

### 2. Create a virtual environment

```bash
python -m venv venv
```

### 3. Activate it on Windows

```powershell
.\venv\Scripts\Activate.ps1
```

### 4. Install dependencies

```bash
pip install -r requirements.txt
```

### 5. Configure environment variables

Create a `.env` file in the project root:

```ini
APP_NAME=CareCircle
APP_ENV=development
SECRET_KEY=replace-with-a-secure-random-secret
DATABASE_URL=sqlite:///./data/carecircle.db
SESSION_EXPIRE_MINUTES=60
```

Use a unique, securely generated secret key for your environment. Never commit `.env` to GitHub.

### 6. Start the application

```bash
python -m uvicorn backend.app.main:app --reload
```

Open:

- Application: http://127.0.0.1:8000
- API documentation: http://127.0.0.1:8000/docs
- Health check: http://127.0.0.1:8000/health

The SQLite database is initialized automatically when the application starts.

## Run Tests

```bash
python -m pytest -v
```

## Security and Privacy

- Passwords/passcodes are handled through password hashing.
- Session-based authentication protects API access.
- Care-team permissions are checked by the backend.
- Revoked caregiver access is rejected.
- Patient records are scoped to the associated patient.
- Important actions are recorded in the audit history.
- Sensitive environment configuration and local database files are excluded from Git.

## Important Notes

- A dose marked as missed means no confirmation was recorded within the configured grace period. It does not prove that the medication was physically not taken.
- Caregiver-confirmed doses are distinguished from patient self-reported confirmations.
- Notification processing and retry logic are implemented. Actual email delivery requires valid SMTP configuration and must be verified separately.
- CareCircle is a care coordination tool, not a replacement for professional medical advice.

## Project Links

- **GitHub Repository:** To be added
- **Live Application:** To be added
- **Project Presentation:** To be added

## Future Improvements

- Production deployment with secure environment configuration.
- Verified email reminders and delivery monitoring.
- Improved accessibility and elder-friendly interface controls.
- Expanded integration and end-to-end testing.

---

**CareCircle — Better coordination. More accountable care.**