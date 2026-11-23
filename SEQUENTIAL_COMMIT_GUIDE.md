# Sequential Two-Developer GitHub Commit Guide

Use this playbook to push the CampusHub codebase sequentially to your shared GitHub repository so both **Md Alamin (`alaminbdf`)** and **Abdullah Al Shahriar Shobuj (`Shahriar-786`)** have a clean, authentic, reviewable commit and PR history matching your blueprint split.

## One-Time Shared Repository Setup
1. Create a new repository on GitHub (e.g., `campushub`) and add your teammate as a **Collaborator** (Settings → Collaborators).
2. Both teammates clone the empty repository locally, configure Git identity (`git config user.name` and `git config user.email` matching your GitHub accounts), and keep the unzipped `campushub/` project folder beside it so you can copy in each step's files cleanly.
3. After Step 1 is pushed to `main`, enable **Branch Protection** on `main` (Settings → Branches → Require PR + 1 approval + CI passing) if you want full PR history too.

---

## Ordered Commit Sequence (12 Sequential Commits)

| Step | Author (GitHub) | Branch | Files to Stage (`git add`) | Commit Message |
|---:|---|---|---|---|
| **1** | **Md Alamin** (`alaminbdf`) | `main` (initial) | `.gitignore`, `.env.example`, `requirements.txt`, `pyproject.toml`, `Dockerfile`, `compose.yaml`, `render.yaml`, `build.sh`, `docs/decisions/`, `.github/` | `chore(init): scaffold repo, approved ADRs 001-003, Docker, Render/Neon config and CI` |
| **2** | **Md Alamin** (`alaminbdf`) | `feature/01-django-core-auth` | `manage.py`, `config/`, `apps/__init__.py`, `apps/core/`, `apps/accounts/`, `apps/access_control/` | `feat(accounts): add Django config, custom UUID User, 9 operational roles and server-side RBAC` |
| **3** | **Md Alamin** (`alaminbdf`) | `feature/02-audit-notifications` | `apps/audit/`, `apps/notifications/` | `feat(audit): add append-only audit log and transactional notification outbox` |
| **4** | **Abdullah Al Shahriar Shobuj** (`Shahriar-786`) | `feature/03-library-inventory` | `apps/library/`, `templates/library/` | `feat(library): implement zones, seats, sessions, closures and ADR-003 booking policy` |
| **5** | **Abdullah Al Shahriar Shobuj** (`Shahriar-786`) | `feature/04-reservation-concurrency` | `apps/reservations/`, `templates/reservations/` | `feat(reservations): implement attendee-sorted locking protocol, group consent and anti-proxy limits` |
| **6** | **Abdullah Al Shahriar Shobuj** (`Shahriar-786`) | `feature/05-ml-demand-forecasting` | `apps/forecasting/`, `templates/forecasting/` | `feat(forecasting): add synthetic time-aware ML demand forecasting pipeline and Chart.js dashboard` |
| **7** | **Md Alamin** (`alaminbdf`) | `feature/06-lost-and-found` | `apps/lost_found/`, `templates/lost_found/` | `feat(lost-found): add report intake, unverified match leads, claim verification and handover chain` |
| **8** | **Md Alamin** (`alaminbdf`) | `feature/07-facilities-dashboards` | `apps/facilities/`, `apps/dashboards/`, `templates/base.html`, `templates/accounts/`, `templates/dashboards/`, `templates/facilities/`, `templates/audit/`, `templates/notifications/`, `static/` | `feat(facilities): add queue-scoped ticketing, role dashboards and responsive Bootstrap 5 UI` |
| **9** | **Abdullah Al Shahriar Shobuj** (`Shahriar-786`) | `test/08-library-ml-tests` | `tests/__init__.py`, `tests/conftest.py`, `tests/unit/test_library_rules.py`, `tests/concurrency/test_reservation_concurrency.py`, `tests/unit/test_ml_forecasting.py` | `test(library-ml): add anti-proxy, PostgreSQL concurrency and time-aware ML forecast tests` |
| **10** | **Md Alamin** (`alaminbdf`) | `test/09-rbac-services-tests` | `tests/authorization/test_rbac_boundaries.py`, `tests/integration/test_lost_found_and_facilities.py` | `test(security-services): add RBAC negative tests, audit immutability, Lost & Found and Facility tests` |
| **11** | **Abdullah Al Shahriar Shobuj** (`Shahriar-786`) | `docs/10-role-readme-guide` | `README.md` | `docs(readme): add 9-role usage guide, local Docker setup and Render+Neon free deploy guide` |
| **12** | **Md Alamin** (`alaminbdf`) | `docs/11-contribution-journal` | `CONTRIBUTION_JOURNAL.md`, `SEQUENTIAL_COMMIT_GUIDE.md` | `docs(journal): add engineering contribution journal and sequential commit playbook` |

---

## Standard Commands for Each Step
Before starting your next assigned step, always sync `main` first:
```bash
git switch main
git pull --ff-only
git switch -c <branch-name>
# Copy only the files listed for your step into the repo folder
git status
git add <specific-files-for-this-step>
git commit -m "<commit-message>"
git push -u origin <branch-name>
```
Then open a Pull Request on GitHub, have your teammate review and approve it, wait for the green **CI** check, and **Squash and merge** into `main` before the next step begins.
