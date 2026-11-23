# ADR-003: Library Policy Prototype Defaults

- **Status:** Approved Prototype Defaults (23 November 2026) — **Not DIU Institutional Policy**
- **Approved By:** Abdullah Al Shahriar Shobuj (`Shahriar-786`), Md Alamin (`alaminbdf`)
- **Configurable Defaults (stored in `BookingPolicyVersion`):**
  1. **Allocation granularity:** Seat-level selection inside configured zones.
  2. **Operational day & timezone:** `Asia/Dhaka` (`00:00`–`23:59` local date).
  3. **Daily & consecutive limits:** Maximum 2 consecutive sessions in a single booking; no further bookings for the remainder of the operational day once a confirmed booking exists.
  4. **Group confirmation mode:** All-or-nothing confirmation (every invited attendee must accept before confirmation).
  5. **Consent requirement:** Required for every invited attendee other than the creator.
  6. **Invitation expiry:** 30 minutes from creation (unaccepted invitations expire and do not hold confirmed capacity).
  7. **Cancellation effect:** Cancelling before session start preserves history and restores same-day eligibility.
  8. **Check-in & grace period:** Authenticated check-in button or Library Staff check-in; 15-minute grace period after session start before no-show eligibility.
  9. **Early departure:** Deferred (not auto-released based on unverified client action).
  10. **Supervisor overrides:** Narrowly scoped to Library Supervisor with mandatory reason and immutable audit record.
