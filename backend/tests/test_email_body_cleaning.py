import base64

from app.gmail_integration import _extract_body_text


def test_extract_body_text_strips_html_css_and_footer_noise() -> None:
    html = """
    <html>
      <head>
        <style>@media (max-width: 480px) { .hero { display:none; } }</style>
      </head>
      <body>
        <p>Interview availability for Backend Engineer</p>
        <p>Please share your availability for a 45 minute call.</p>
        <p>This email was intended for Jose Gomez</p>
        <p>Unsubscribe: example.com</p>
      </body>
    </html>
    """
    encoded = base64.urlsafe_b64encode(html.encode("utf-8")).decode("utf-8").rstrip("=")
    payload = {"mimeType": "text/html", "body": {"data": encoded}}

    cleaned = _extract_body_text(payload)

    assert "Interview availability for Backend Engineer" in cleaned
    assert "Please share your availability for a 45 minute call." in cleaned
    assert "This email was intended for" not in cleaned
    assert "@media" not in cleaned
