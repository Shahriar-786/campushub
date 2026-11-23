# ADR-002: Free Hosting Architecture

- **Status:** Approved (23 November 2026)
- **Approved By:** Abdullah Al Shahriar Shobuj (`Shahriar-786`), Md Alamin (`alaminbdf`)
- **Decision:** Deploy the Django web service on **Render Free Tier** (Singapore region, auto-deployed from GitHub via `render.yaml`) connected to **Neon Free PostgreSQL** (serverless Postgres, $0/month, 1 GB storage, no 30-day expiration).
- **Trade-offs Accepted:** Render free web services spin down after 15 minutes of inactivity (~1 min cold start); Neon free compute scales to zero after 5 minutes of inactivity. Acceptable for an academic capstone prototype showcase using synthetic data.
