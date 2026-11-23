# ADR-001: Initial Web Architecture

- **Status:** Approved (23 November 2026)
- **Approved By:** Abdullah Al Shahriar Shobuj (`Shahriar-786`), Md Alamin (`alaminbdf`)
- **Decision:** Build CampusHub as a **Django 5.2 LTS + Python 3.13** modular monolith backed by **PostgreSQL**, using **Django Templates + HTMX + Bootstrap 5** for a mobile-first responsive UI, **Chart.js** for dashboards, and **pandas + scikit-learn** for the mandatory ML demand forecasting pipeline.
- **Rationale:** Single primary language across web domain logic and ML, built-in Django auth/ORM/migrations/CSRF/session hardening, and lowest operational complexity for a 2-developer capstone team.
