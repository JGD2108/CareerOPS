# Job Description Resolution QA

This checklist verifies the completed local-first job description flow. LinkedIn is Gmail-only discovery: do not enter LinkedIn credentials, reuse LinkedIn cookies, automate LinkedIn login, scrape LinkedIn job pages, use Selenium for LinkedIn, or bypass CAPTCHA/bot protection.

## State Model

`description_status` values:

- `missing`: no usable description.
- `partial_from_email`: Gmail alert metadata only, commonly from LinkedIn.
- `resolved_from_ats`: accepted deterministic match from Greenhouse, Lever, or Ashby.
- `resolved_from_company_site`: accepted public page under the company's official website domain.
- `manually_provided`: user pasted the full description.
- `manually_provided_url`: user provided an official public URL and the resolver extracted the description.
- `failed`: resolution failed.

`needs_manual_review` is a `fetch_status` and resolution attempt status, not a `description_status`. It means the job is still unresolved until the user accepts a candidate, adds an official public URL, or pastes the full official description.

## Manual Seed Data

Use non-private examples only:

- LinkedIn Gmail alert body:
  `LinkedIn Job Alerts\nData Engineer at Acme\nBogota, Colombia\nView job: https://www.linkedin.com/comm/jobs/view/123456789/`
- Greenhouse source:
  `source=greenhouse`, `company_key=example`, title `Data Engineer`, URL `https://boards.greenhouse.io/example/jobs/123`
- Lever source:
  `source=lever`, `company_key=example`, title `Backend Engineer`, URL `https://jobs.lever.co/example/123`
- Ashby source:
  `source=ashby`, `company_key=example`, title `Software Engineer`, URL `https://jobs.ashbyhq.com/example/123`
- Manual official URL:
  `https://acme.example/careers/data-engineer`
- Bad LinkedIn URL:
  `https://www.linkedin.com/jobs/view/123456789/`
- Fake login-required URL:
  `https://acme.example/login?next=/careers/data-engineer`
- Fake token URL:
  `https://acme.example/careers/data-engineer?session=secret`
- Medium-confidence candidate:
  title `Senior Data Engineer`, company `Acme`, location `Remote`, source URL `https://boards.greenhouse.io/acme/jobs/1`, confidence `0.70-0.89`

## Checklist

1. LinkedIn Gmail alert creates partial job
   - Sync or mock-ingest the LinkedIn alert.
   - Expected: job source is `linkedin_email_alert`, `description_status=partial_from_email`, `description_quality=low`, and no resolved description is stored.

2. Partial LinkedIn job blocks final scoring
   - Open the job and click final scoring.
   - Expected: scoring is blocked with an actionable message telling the user to add an official URL, accept a candidate, or paste the full official description.

3. Paste manual description enables final scoring
   - Paste a full official description of at least several paragraphs.
   - Expected: `description_status=manually_provided`, `fetch_status=success`, a resolution attempt is written, and final scoring is enabled.

4. Manual official URL succeeds
   - Add a public official job URL with substantial role text.
   - Expected: `POST /api/v1/jobs/{job_id}/manual-url` returns success, stores `manually_provided_url`, writes an attempt, and enables final scoring/CV/message prerequisites.

5. Manual official URL rejects LinkedIn
   - Submit `https://www.linkedin.com/jobs/view/123456789/`.
   - Expected: clear rejection explaining LinkedIn URLs are reference-only and cannot be fetched.

6. Manual official URL rejects login/auth/token URL
   - Submit a URL containing `/login`, `/auth`, `session=`, `token=`, or similar.
   - Expected: clear rejection explaining login/auth/session URLs are not accepted.

7. ATS resolver succeeds
   - Configure a known Greenhouse, Lever, or Ashby source for the company.
   - Expected: high-confidence match attaches automatically as `resolved_from_ats`; attempt history shows source, URL, confidence, reason, and timestamp.

8. ATS resolver fails and company careers fallback tries safely
   - Use a company website but no matching ATS source.
   - Expected: resolver tries only a small set under the official company domain, respects public HTML constraints, and either stores `resolved_from_company_site` or moves to manual review.

9. Medium-confidence candidate requires user approval
   - Create or mock a `0.70-0.89` candidate without strong enough title/company/location evidence.
   - Expected: candidate appears in manual review and is not auto-attached.

10. Accept candidate enables scoring
    - Click `Accept this description`.
    - Expected: candidate description is attached, success attempt is written, and final scoring is enabled.

11. Reject candidate keeps job unresolved
    - Click `Reject`.
    - Expected: rejection attempt is written, candidate is not attached, and scoring/CV/message actions remain blocked.

12. Batch resolve-pending only processes eligible jobs
    - Run `POST /api/v1/jobs/resolve-pending`.
    - Expected: only `missing`, `partial_from_email`, `failed`, `pending`, `error`, or `not_found` jobs are considered. Already high-quality resolved jobs are not overwritten.

13. Message drafting remains blocked until description and score are valid
    - Try message generation before complete description or with a preliminary score.
    - Expected: clear error explains the missing prerequisite.

14. CV tailoring remains blocked until description is valid
    - Try CV tailoring before a complete description and final score.
    - Expected: clear error explains the missing prerequisite.

## Security Checks

- No LinkedIn credentials are requested.
- No LinkedIn cookies are stored or sent.
- No Selenium LinkedIn scraping is used.
- No CAPTCHA bypass or authenticated scraping is used.
- Manual URLs with auth/session/token query parameters are rejected.
- Public fetches use timeout and response size limits.
- Blocked/social domains are rejected.
- Raw HTML is stored for traceability but not blindly rendered in the frontend.
