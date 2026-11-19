# CampusIQ — Smart Campus Timetable & Room Allocation Optimizer

A role-based Flask application for campus account management, academic resources, teacher availability, and conflict-aware timetable generation.

## Features
- Separate Admin, Teacher and Student sign-in and dashboards
- Admin management of accounts, subjects, classrooms and labs
- Teacher availability preferences
- Student-group and teacher conflict checks
- Room/time-slot allocation and graph-colouring scheduling heuristic
- Responsive dashboard UI
- SQLite database

## Requirements
- Python 3.10+
- Windows, macOS or Linux

## Run on Windows (PowerShell)
```powershell
cd path\to\smart-campus-optimizer
py -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
flask --app app init-db
python app.py
```
Open http://127.0.0.1:5000

## Demo accounts
| Role | Email | Password |
|---|---|---|
| Admin | admin@campus.local | Admin@123 |
| Teacher | teacher@campus.local | Teacher@123 |
| Student | student@campus.local | Student@123 |

Change demo passwords and set a strong `SECRET_KEY` before deployment. The demo credentials are for local evaluation only.

## Suggested demonstration flow
1. Sign in as Admin and create additional teacher/student accounts.
2. Add rooms and subjects; assign a teacher and student group to each subject.
3. Sign in as Teacher and submit unavailable periods.
4. Return as Admin and generate the timetable.
5. Sign in as Student and Teacher to see their respective schedules.

## Notes on the optimizer
The scheduler creates a conflict graph for requested class sessions and applies NetworkX greedy graph colouring as a scheduling heuristic. It then searches available weekday/time-slot combinations and assigns an unoccupied room. This is a practical educational optimizer, not a proof of globally optimal scheduling. It currently uses one-hour periods, weekdays Monday–Friday, and the configured session count per subject.
