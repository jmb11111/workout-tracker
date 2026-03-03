"""
HTML fetcher for the Full Range PVD blog.

Fetches workout posts from the Squarespace blog, finds the post
matching a given date, downloads the full HTML, and strips it to
clean plain text.
"""

import logging
import re
from datetime import date, datetime
from typing import Optional
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from app.core.config import settings

logger = logging.getLogger(__name__)

# Common user-agent to avoid being blocked by Squarespace
_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

_REQUEST_TIMEOUT = 30.0


class FetchError(Exception):
    """Raised when fetching or parsing the blog page fails."""


def _build_client() -> httpx.Client:
    """Build an httpx client with standard headers."""
    return httpx.Client(
        headers={"User-Agent": _USER_AGENT},
        timeout=_REQUEST_TIMEOUT,
        follow_redirects=True,
    )


def _date_variants(target_date: date) -> list[str]:
    """
    Generate several slug-friendly date string variants that Squarespace
    blogs commonly use in their URLs.

    For 2024-03-15, produces patterns like:
      - "3/15/2024", "3-15-2024", "3-15"
      - "march-15", "march15"
      - "2024/3/15", "2024-3-15"
      - "031524" (compact), "31524"
    """
    month_names = [
        "", "january", "february", "march", "april", "may", "june",
        "july", "august", "september", "october", "november", "december",
    ]
    month_name = month_names[target_date.month]

    variants = [
        # Full date forms
        f"{target_date.month}/{target_date.day}/{target_date.year}",
        f"{target_date.month}-{target_date.day}-{target_date.year}",
        f"{target_date.year}/{target_date.month}/{target_date.day}",
        f"{target_date.year}-{target_date.month}-{target_date.day}",
        # Zero-padded
        target_date.strftime("%m-%d-%Y"),
        target_date.strftime("%Y-%m-%d"),
        # Month name forms
        f"{month_name}-{target_date.day}",
        f"{month_name}{target_date.day}",
        # Day/month
        f"{target_date.day}-{month_name}",
        # Short year
        f"{target_date.month}-{target_date.day}-{str(target_date.year)[2:]}",
    ]
    return variants


def _extract_date_from_url(url: str) -> Optional[date]:
    """
    Try to extract a date from a Squarespace blog post URL.

    Squarespace URLs often follow the pattern:
      /blog/YYYY/M/D/slug  or  /blog/slug-with-date
    """
    # Pattern: /blog/YYYY/M/D/...
    match = re.search(r"/blog/(\d{4})/(\d{1,2})/(\d{1,2})/", url)
    if match:
        try:
            return date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
        except ValueError:
            pass

    # Pattern: date embedded in slug as YYYY-MM-DD or similar
    match = re.search(r"(\d{4})-(\d{1,2})-(\d{1,2})", url)
    if match:
        try:
            return date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
        except ValueError:
            pass

    return None


def _collect_blog_links(soup: BeautifulSoup, base_url: str) -> list[dict]:
    """
    Collect all links that point to /blog/ subpages.

    Does NOT deduplicate — multiple <a> tags can point to the same post
    (image link, title link, "Read More" link) but only the title link
    typically has the date text we need for matching.
    """
    blog_links: list[dict] = []
    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"]
        if "/blog/" in href and href not in ("/blog/", "/blog"):
            full_url = urljoin(base_url, href)
            blog_links.append({"url": full_url, "href": href, "tag": a_tag})
    return blog_links


def _match_date_in_text(text: str, target_date: date) -> bool:
    """
    Check if text contains the target date in any common format.

    Handles formats like:
      - "3.3.2026" or "3.3.26" (dot-separated, as used by Full Range PVD)
      - "March 3" / "March 03"
      - "3/3/2026" / "03/03/2026"
      - "Tuesday 3.3.2026" (day name + dot date)
    """
    text_lower = text.lower()

    # Dot-separated (the actual blog format): "3.3.2026" or "3.3.26"
    dot_variants = [
        f"{target_date.month}.{target_date.day}.{target_date.year}",
        f"{target_date.month}.{target_date.day}.{str(target_date.year)[2:]}",
        f"{target_date.month:02d}.{target_date.day:02d}.{target_date.year}",
    ]
    for v in dot_variants:
        if v in text_lower:
            return True

    # Slash-separated
    slash_variants = [
        f"{target_date.month}/{target_date.day}/{target_date.year}",
        f"{target_date.month}/{target_date.day}/{str(target_date.year)[2:]}",
        target_date.strftime("%-m/%-d/%Y"),
    ]
    for v in slash_variants:
        if v in text_lower:
            return True

    # Month name forms
    month_names = [
        "", "january", "february", "march", "april", "may", "june",
        "july", "august", "september", "october", "november", "december",
    ]
    month_name = month_names[target_date.month]
    name_variants = [
        f"{month_name} {target_date.day}",
        f"{month_name} {target_date.day:02d}",
    ]
    for v in name_variants:
        if v in text_lower:
            return True

    return False


def _find_post_url(blog_html: str, target_date: date, base_url: str) -> Optional[str]:
    """
    Scan the blog listing page HTML for a post matching the target date.

    Strategy:
    1. Look for links whose href contains the target date in the URL path
       (Squarespace often uses /blog/YYYY/M/D/slug).
    2. Check link text/title and surrounding context for date strings
       (Full Range PVD uses titles like "Tuesday 3.3.2026").
    3. If today's date, fall back to most recent post.
    """
    soup = BeautifulSoup(blog_html, "lxml")
    blog_links = _collect_blog_links(soup, base_url)

    if not blog_links:
        logger.warning("No blog post links found on listing page")
        return None

    # Strategy 1: Check URL path for date
    date_slugs = _date_variants(target_date)
    for link in blog_links:
        extracted = _extract_date_from_url(link["href"])
        if extracted == target_date:
            logger.info("Found post by URL date pattern: %s", link["url"])
            return link["url"]

        href_lower = link["href"].lower()
        for variant in date_slugs:
            if variant.lower() in href_lower:
                logger.info("Found post by date variant in URL: %s", link["url"])
                return link["url"]

    # Strategy 2: Check link text for date strings
    # Only check the link's own text, not parent context, to avoid
    # false matches from metadata dates in surrounding elements.
    for link in blog_links:
        link_text = link["tag"].get_text(strip=True)
        if link_text and _match_date_in_text(link_text, target_date):
            logger.info("Found post by date in link text: %s", link["url"])
            return link["url"]

    # Strategy 3: If today's post, take the first/most recent blog link
    if target_date == date.today() and blog_links:
        logger.info(
            "No exact date match found; using most recent post for today: %s",
            blog_links[0]["url"],
        )
        return blog_links[0]["url"]

    logger.warning("No post found matching date %s on current page", target_date.isoformat())
    return None


def _try_squarespace_json(blog_html: str, target_date: date, base_url: str) -> Optional[str]:
    """
    Squarespace pages sometimes embed JSON data containing blog post metadata.
    Try to extract post URLs from embedded JSON.
    """
    import json

    # Look for Static.SQUARESPACE_CONTEXT or window.__INITIAL_STATE__
    patterns = [
        r'Static\.SQUARESPACE_CONTEXT\s*=\s*(\{.*?\});',
        r'window\.__INITIAL_STATE__\s*=\s*(\{.*?\});',
    ]
    for pattern in patterns:
        match = re.search(pattern, blog_html, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(1))
                # Try to navigate to blog items
                items = data.get("collection", {}).get("items", [])
                if not items:
                    items = data.get("items", [])
                for item in items:
                    item_date_ms = item.get("publishOn", item.get("addedOn", 0))
                    if item_date_ms:
                        item_date = datetime.fromtimestamp(item_date_ms / 1000).date()
                        if item_date == target_date:
                            url_slug = item.get("fullUrl", item.get("urlId", ""))
                            if url_slug:
                                return urljoin(base_url, url_slug)
            except (json.JSONDecodeError, KeyError, TypeError):
                continue

    return None


def _html_to_text(html: str) -> str:
    """
    Convert HTML to clean plain text, preserving structure where useful.

    Removes scripts, styles, navigation, footers. Keeps the main
    content area text with reasonable whitespace.
    """
    soup = BeautifulSoup(html, "lxml")

    # Remove elements that are never workout content
    for tag_name in ["script", "style", "nav", "footer", "header", "noscript", "iframe"]:
        for tag in soup.find_all(tag_name):
            tag.decompose()

    # Remove common Squarespace boilerplate by exact class or tag
    for tag in soup.find_all(class_=re.compile(
        r"^(?:sqs-cookie-banner|sqs-announcement-bar|newsletter-form(?:-wrapper)?|comment-list|social-links)$",
        re.IGNORECASE,
    )):
        tag.decompose()

    # Try to find the main content area
    content = None
    for selector in [
        "article",
        ".blog-item-content",
        ".sqs-block-content",
        ".entry-content",
        '[data-block-type="2"]',  # Squarespace text block
        "main",
        ".main-content",
    ]:
        elements = soup.select(selector)
        if elements:
            content = elements
            break

    if content:
        text_parts = [el.get_text(separator="\n", strip=True) for el in content]
        text = "\n\n".join(text_parts)
    else:
        # Fallback: get all body text
        body = soup.find("body")
        text = body.get_text(separator="\n", strip=True) if body else soup.get_text(separator="\n", strip=True)

    # Clean up excessive whitespace while preserving paragraph breaks
    lines = text.split("\n")
    cleaned_lines = []
    prev_empty = False
    for line in lines:
        stripped = line.strip()
        if not stripped:
            if not prev_empty:
                cleaned_lines.append("")
                prev_empty = True
        else:
            cleaned_lines.append(stripped)
            prev_empty = False

    return "\n".join(cleaned_lines).strip()


def _find_older_posts_link(soup: BeautifulSoup, base_url: str) -> Optional[str]:
    """Find the 'Older Posts' pagination link on a Squarespace blog page."""
    for a_tag in soup.find_all("a", href=True):
        text = a_tag.get_text(strip=True).lower()
        if "older" in text and "post" in text:
            return urljoin(base_url, a_tag["href"])
    # Also check for ?offset= links
    for a_tag in soup.find_all("a", href=True):
        if "offset=" in a_tag["href"]:
            return urljoin(base_url, a_tag["href"])
    return None


def fetch_workout(target_date: Optional[date] = None) -> dict:
    """
    Fetch the workout post for a given date.

    Args:
        target_date: The date to fetch. Defaults to today.

    Returns:
        dict with keys:
            - source_url: str - the URL of the post
            - raw_html: str - full HTML of the post page
            - raw_text: str - cleaned plain text of the post

    Raises:
        FetchError: if the blog page or post cannot be fetched.
    """
    if target_date is None:
        target_date = date.today()

    blog_url = settings.BLOG_URL
    logger.info("Fetching blog listing from %s for date %s", blog_url, target_date.isoformat())

    max_pages = 5  # Don't paginate forever

    try:
        with _build_client() as client:
            current_url = blog_url
            post_url = None

            for page in range(max_pages):
                # Fetch the listing page
                response = client.get(current_url)
                response.raise_for_status()
                listing_html = response.text
                logger.debug("Blog listing page %d fetched, %d bytes", page + 1, len(listing_html))

                # Try to find the post on this page
                post_url = _find_post_url(listing_html, target_date, blog_url)

                # Try embedded JSON as fallback
                if not post_url:
                    post_url = _try_squarespace_json(listing_html, target_date, blog_url)

                if post_url:
                    break

                # Check if there's an older posts page
                soup = BeautifulSoup(listing_html, "lxml")
                next_page = _find_older_posts_link(soup, blog_url)
                if not next_page or next_page == current_url:
                    logger.info("No more pages to check")
                    break

                logger.info("Post not found on page %d, checking older posts", page + 1)
                current_url = next_page

            if not post_url:
                raise FetchError(
                    f"No workout post found for {target_date.isoformat()} "
                    f"on {blog_url}"
                )

            # Fetch the full post page
            logger.info("Fetching post: %s", post_url)
            post_response = client.get(post_url)
            post_response.raise_for_status()
            raw_html = post_response.text

            # Convert to plain text
            raw_text = _html_to_text(raw_html)

            if not raw_text or len(raw_text) < 50:
                logger.warning(
                    "Extracted text is suspiciously short (%d chars), "
                    "page may not contain workout data",
                    len(raw_text),
                )

            logger.info(
                "Successfully fetched workout for %s (%d chars text)",
                target_date.isoformat(),
                len(raw_text),
            )

            return {
                "source_url": post_url,
                "raw_html": raw_html,
                "raw_text": raw_text,
            }

    except httpx.HTTPStatusError as exc:
        logger.error("HTTP error fetching blog: %s %s", exc.response.status_code, exc.request.url)
        raise FetchError(f"HTTP {exc.response.status_code} fetching {exc.request.url}") from exc
    except httpx.RequestError as exc:
        logger.error("Network error fetching blog: %s", exc)
        raise FetchError(f"Network error: {exc}") from exc
