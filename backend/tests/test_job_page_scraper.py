from app.job_page_scraper import parse_job_posting_json_ld


def test_parse_job_posting_json_ld_extracts_core_fields():
    page_source = """
    <html>
      <head>
        <script type="application/ld+json">
          {
            "@context": "https://schema.org",
            "@type": "JobPosting",
            "title": "Backend Engineer",
            "description": "<p>Build APIs with Python and FastAPI.</p>",
            "datePosted": "2026-05-19T12:30:00Z",
            "validThrough": "2026-06-15T23:59:59Z",
            "hiringOrganization": {
              "@type": "Organization",
              "name": "Acme Corp"
            },
            "jobLocation": {
              "@type": "Place",
              "address": {
                "@type": "PostalAddress",
                "addressLocality": "Bogota",
                "addressCountry": "CO"
              }
            }
          }
        </script>
      </head>
    </html>
    """

    payload = parse_job_posting_json_ld(page_source)

    assert payload is not None
    assert payload["title"] == "Backend Engineer"
    assert payload["company_name"] == "Acme Corp"
    assert payload["description"] == "Build APIs with Python and FastAPI."
    assert payload["location"] == "Bogota"
    assert payload["posted_at"] is not None
    assert payload["application_deadline"] is not None
