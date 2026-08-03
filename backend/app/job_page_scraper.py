from __future__ import annotations

from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime, timezone
from html import unescape
import json
import re
from typing import Any

try:
    from selenium import webdriver
    from selenium.common.exceptions import TimeoutException, WebDriverException
    from selenium.webdriver.chrome.options import Options as ChromeOptions
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.support.ui import WebDriverWait
except ImportError:  # pragma: no cover - optional runtime dependency
    webdriver = None
    TimeoutException = WebDriverException = Exception
    ChromeOptions = None
    By = None
    WebDriverWait = None
    EC = None


UNAVAILABLE_MARKERS = (
    "no longer accepting applications",
    "job is no longer available",
    "job posting has expired",
    "this job has expired",
    "applications are closed",
    "position has been filled",
)
OPEN_MARKERS = (
    "easy apply",
    "apply now",
    "submit application",
    "apply for this job",
    "fill out the form",
    "send your cv",
    "send your cv in english",
)


@dataclass
class ScrapedJobPage:
    source_url: str
    final_url: str
    title: str | None
    company_name: str | None
    description: str | None
    location: str | None
    posted_at: datetime | None
    application_deadline: datetime | None
    availability_status: str
    availability_reason: str | None
    scraper: str


def _clean_html_text(value: str | None) -> str | None:
    if not value:
        return None
    text = re.sub(r"<[^>]+>", " ", value)
    text = unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text or None


def _parse_datetime_value(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, (int, float)):
        try:
            if value > 10_000_000_000:
                value = value / 1000
            return datetime.fromtimestamp(value, tz=timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None
    if isinstance(value, str):
        cleaned = value.strip()
        if not cleaned:
            return None
        try:
            return datetime.fromisoformat(cleaned.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def _iter_json_ld_objects(payload: Any) -> list[dict[str, Any]]:
    objects: list[dict[str, Any]] = []
    if isinstance(payload, dict):
        objects.append(payload)
        graph = payload.get("@graph")
        if isinstance(graph, list):
            for item in graph:
                objects.extend(_iter_json_ld_objects(item))
    elif isinstance(payload, list):
        for item in payload:
            objects.extend(_iter_json_ld_objects(item))
    return objects


def parse_job_posting_json_ld(page_source: str) -> dict[str, Any] | None:
    script_contents = re.findall(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        page_source,
        flags=re.IGNORECASE | re.DOTALL,
    )
    for script_content in script_contents:
        try:
            payload = json.loads(unescape(script_content.strip()))
        except json.JSONDecodeError:
            continue
        for item in _iter_json_ld_objects(payload):
            type_value = item.get("@type")
            type_names = type_value if isinstance(type_value, list) else [type_value]
            if "JobPosting" not in [str(name) for name in type_names if name]:
                continue
            hiring_org = item.get("hiringOrganization") or {}
            location = item.get("jobLocation") or item.get("applicantLocationRequirements")
            location_name = None
            if isinstance(location, list) and location:
                location = location[0]
            if isinstance(location, dict):
                address = location.get("address") or {}
                location_name = (
                    address.get("addressLocality")
                    or address.get("addressRegion")
                    or address.get("addressCountry")
                    or location.get("name")
                )
            return {
                "title": _clean_html_text(item.get("title")),
                "company_name": _clean_html_text(hiring_org.get("name")) if isinstance(hiring_org, dict) else None,
                "description": _clean_html_text(item.get("description")),
                "location": _clean_html_text(location_name),
                "posted_at": _parse_datetime_value(item.get("datePosted")),
                "application_deadline": _parse_datetime_value(item.get("validThrough")),
            }
    return None


def _availability_from_page_text(final_url: str, body_text: str) -> tuple[str, str | None]:
    lowered = body_text.lower()
    if any(marker in lowered for marker in OPEN_MARKERS):
        return "open", "The page still shows application actions."
    if any(marker in lowered for marker in UNAVAILABLE_MARKERS):
        return "closed", "The page says the role is no longer accepting applications."
    if "linkedin.com" in final_url.lower() and "sign in" in lowered and "/jobs/view/" not in final_url.lower():
        return "unknown", "LinkedIn redirected to a sign-in wall, so public availability could not be confirmed."
    return "unknown", "The page loaded, but the scraper could not confirm whether applications are still open."


def _extract_visible_text(driver: Any) -> str:
    try:
        body = driver.find_element(By.TAG_NAME, "body")
        return re.sub(r"\s+", " ", body.text or "").strip()
    except Exception:
        return ""


def scrape_job_page_with_selenium(url: str) -> ScrapedJobPage | None:
    if webdriver is None or ChromeOptions is None or By is None:
        return None
    if "linkedin.com" in url.lower():
        return None

    options = ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1440,2200")
    options.add_argument(
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/136.0 Safari/537.36"
    )

    driver = None
    try:
        driver = webdriver.Chrome(options=options)
        driver.set_page_load_timeout(25)
        driver.get(url)
        if WebDriverWait and EC and By:
            WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, "body")))

        page_source = driver.page_source or ""
        final_url = driver.current_url or url
        visible_text = _extract_visible_text(driver)
        json_ld = parse_job_posting_json_ld(page_source) or {}

        title = json_ld.get("title")
        company_name = json_ld.get("company_name")
        description = json_ld.get("description")
        location = json_ld.get("location")

        if not title:
            for selector in ("h1", ".topcard__title", ".job-details-jobs-unified-top-card__job-title"):
                try:
                    title = _clean_html_text(driver.find_element(By.CSS_SELECTOR, selector).text)
                    if title:
                        break
                except Exception:
                    continue
        if not company_name:
            for selector in (
                ".topcard__org-name-link",
                ".topcard__flavor",
                ".job-details-jobs-unified-top-card__company-name",
            ):
                try:
                    company_name = _clean_html_text(driver.find_element(By.CSS_SELECTOR, selector).text)
                    if company_name:
                        break
                except Exception:
                    continue
        if not description:
            for selector in (
                ".show-more-less-html__markup",
                ".description__text",
                ".jobs-description__content",
            ):
                try:
                    description = _clean_html_text(driver.find_element(By.CSS_SELECTOR, selector).get_attribute("innerHTML"))
                    if description:
                        break
                except Exception:
                    continue

        availability_status, availability_reason = _availability_from_page_text(final_url, visible_text)
        return ScrapedJobPage(
            source_url=url,
            final_url=final_url,
            title=title,
            company_name=company_name,
            description=description,
            location=location,
            posted_at=json_ld.get("posted_at"),
            application_deadline=json_ld.get("application_deadline"),
            availability_status=availability_status,
            availability_reason=availability_reason,
            scraper="selenium",
        )
    except (TimeoutException, WebDriverException):
        return None
    finally:
        if driver is not None:
            with suppress(Exception):
                driver.quit()
