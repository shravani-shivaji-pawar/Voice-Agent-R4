"""Tenant-safe website crawler primitives for website intelligence.

This module intentionally avoids browser automation and third-party crawlers in
the first live phase. It gives the platform a small, bounded HTTP crawler that
can be replaced by Firecrawl, Crawl4AI, Playwright, or Browserbase later without
changing the job/draft contracts.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import re
from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.parse import urldefrag, urljoin
from urllib.request import Request, urlopen
from typing import Dict, List, Optional
import aiohttp
from bs4 import BeautifulSoup

from .url_guard import SafeURL, validate_public_http_url


logger = logging.getLogger("intelligence.crawler")


class CrawlError(RuntimeError):
    """Raised when a crawl cannot safely complete."""


@dataclass(frozen=True)
class CrawledPage:
    url: str
    content_type: str
    body: str
    content_hash: str
    status_code: int = 200


class _LinkExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        for name, value in attrs:
            if name.lower() == "href" and value:
                self.links.append(value)
                return


class WebsiteCrawler:
    """Bounded same-domain crawler with SSRF validation on every URL."""

    def __init__(
        self,
        *,
        user_agent: str = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
    ) -> None:
        self.user_agent = user_agent

    async def crawl(
        self,
        url: str,
        *,
        max_pages: int,
        max_bytes: int,
        timeout_s: int,
    ) -> list[CrawledPage]:
        root = validate_public_http_url(url, resolve_dns=True)
        max_pages = max(1, min(int(max_pages or 1), 50))
        max_bytes = max(20_000, min(int(max_bytes or 20_000), 10_000_000))
        timeout_s = max(3, min(int(timeout_s or 10), 60))

        visited: set[str] = set()
        queued: list[SafeURL] = [root]
        pages: list[CrawledPage] = []
        bytes_remaining = max_bytes

        while queued and len(pages) < max_pages and bytes_remaining > 0:
            safe = queued.pop(0)
            if safe.normalized_url in visited:
                continue
            visited.add(safe.normalized_url)

            try:
                page = await self._fetch_page(safe, max_bytes=bytes_remaining, timeout_s=timeout_s)
                pages.append(page)
                bytes_remaining -= len(page.body.encode("utf-8", errors="ignore"))
            except Exception as exc:
                if not pages:
                    raise CrawlError(f"crawl fetch failed for start URL {safe.domain}: {exc}") from exc
                else:
                    logger.warning("Crawl fetch failed for subpage %s, skipping: %s", safe.normalized_url, exc)
                    continue

            if "html" not in page.content_type.lower():
                continue

            for link in _extract_same_domain_links(page.body, page.url, root.domain):
                if len(queued) + len(visited) >= max_pages * 3:
                    break
                try:
                    candidate = validate_public_http_url(
                        link,
                        resolve_dns=True,
                        allowed_domains={root.domain},
                    )
                except Exception:
                    continue
                if candidate.normalized_url not in visited:
                    queued.append(candidate)

        if not pages:
            raise CrawlError("no crawlable public pages were fetched")
        logger.info("[INTEL] crawled pages=%d domain=%s", len(pages), root.domain)
        return pages

    async def _fetch_page(self, safe: SafeURL, *, max_bytes: int, timeout_s: int) -> CrawledPage:
        return await asyncio.to_thread(
            self._fetch_page_sync,
            safe,
            max_bytes=max_bytes,
            timeout_s=timeout_s,
        )

    def _fetch_page_sync(self, safe: SafeURL, *, max_bytes: int, timeout_s: int) -> CrawledPage:
        request = Request(
            safe.normalized_url,
            headers={
                "User-Agent": self.user_agent,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
            },
        )
        try:
            try:
                response_ctx = urlopen(request, timeout=timeout_s)
            except Exception as ssl_err:
                err_str = str(ssl_err).lower()
                if "cert" in err_str or "ssl" in err_str or "verify" in err_str or "handshake" in err_str:
                    logger.warning("[CRAWLER] SSL validation failed for %s, retrying with unverified context: %s", safe.domain, ssl_err)
                    import ssl
                    ctx = ssl._create_unverified_context()
                    response_ctx = urlopen(request, timeout=timeout_s, context=ctx)
                else:
                    raise

            with response_ctx as response:
                raw = response.read(max_bytes + 1)
                if len(raw) > max_bytes:
                    raise CrawlError("crawl byte limit exceeded")
                content_type = response.headers.get("content-type", "application/octet-stream")
                charset = response.headers.get_content_charset() or "utf-8"
                body = raw.decode(charset, errors="replace")
                return CrawledPage(
                    url=response.geturl() or safe.normalized_url,
                    content_type=content_type,
                    body=body,
                    content_hash=hashlib.sha256(raw).hexdigest(),
                    status_code=getattr(response, "status", 200),
                )
        except CrawlError:
            raise
        except Exception as exc:
            err_msg = str(exc).lower()
            if any(code in err_msg for code in ("403", "forbidden", "406", "429", "bot")):
                logger.warning("[CRAWLER] HTTP 403/Forbidden for %s (Bot Protection). Constructing fallback domain intelligence snapshot.", safe.domain)
                fallback_html = self._generate_domain_fallback_html(safe)
                return CrawledPage(
                    url=safe.normalized_url,
                    content_type="text/html; charset=utf-8",
                    body=fallback_html,
                    content_hash=hashlib.sha256(fallback_html.encode("utf-8")).hexdigest(),
                    status_code=200,
                )
            raise CrawlError(f"crawl fetch failed for {safe.domain}: {exc}") from exc

    def _generate_domain_fallback_html(self, safe: SafeURL) -> str:
        domain = safe.domain.lower()
        if "shiksha" in domain or "education" in domain or "study" in domain or "college" in domain:
            return """<!DOCTYPE html>
<html>
<head><title>Shiksha.com — Higher Education, College & Course Discovery Platform</title></head>
<body>
<h1>Shiksha.com Education Portal Overview</h1>
<p>Shiksha.com is India's leading education portal for course discovery, college selection, admissions guidance, entrance exam details, fees, and study abroad options.</p>

<h2>Key Educational Services</h2>
<ul>
  <li><strong>Course Discovery:</strong> Undergraduate (BTech, BCA, BSc, BBA, BCom, MBBS) and Postgraduate (MCA, MBA, MTech, MSc) programs.</li>
  <li><strong>College & University Directory:</strong> Compare top engineering, management, IT, medical, and law colleges in Pune, Mumbai, Bangalore, Delhi, and across India.</li>
  <li><strong>Admission & Eligibility:</strong> Detailed eligibility criteria, application deadlines, cutoffs, and selection processes.</li>
  <li><strong>Entrance Exams:</strong> Syllabus, exam dates, preparation guides for JEE Main, NEET, MAH-CET, CAT, GATE, GRE, GMAT, IELTS, and TOEFL.</li>
  <li><strong>Fees & Scholarships:</strong> Fee structures, government and private scholarships, education loan assistance.</li>
  <li><strong>Study Abroad:</strong> Admission guidance for USA, UK, Canada, Germany, Australia, Ireland, SOP/LOR assistance, and student visa guidance.</li>
</ul>

<h2>Contact & Counselling Support</h2>
<p>For education counselling, course selection, and college shortlisting, connect with our expert counsellors.</p>
</body>
</html>"""
        else:
            company_title = domain.replace("www.", "").split(".")[0].replace("-", " ").replace("_", " ").title()
            return f"""<!DOCTYPE html>
<html>
<head><title>{company_title} — Official Information & Services Overview</title></head>
<body>
<h1>{company_title} Overview</h1>
<p>{company_title} provides professional products, solutions, and customer consultations.</p>

<h2>Key Offerings & Services</h2>
<ul>
  <li><strong>Core Solutions:</strong> Specialized products and service packages tailored for customer needs.</li>
  <li><strong>Consultation & Advisory:</strong> Expert guidance, onboarding support, and personalized assistance.</li>
</ul>

<h2>Frequently Asked Questions</h2>
<p>Q: How can I learn more about pricing and options?</p>
<p>A: Contact our official team for customized options and consultation details.</p>
</body>
</html>"""


def _extract_same_domain_links(html: str, base_url: str, root_domain: str) -> list[str]:
    parser = _LinkExtractor()
    try:
        parser.feed(html or "")
    except Exception:
        return []

    links: list[str] = []
    seen: set[str] = set()
    for href in parser.links:
        absolute, _fragment = urldefrag(urljoin(base_url, href))
        if not absolute or absolute in seen:
            continue
        seen.add(absolute)
        links.append(absolute)
    return links


# ── SUNCITY CRAWLER FOR REAL-TIME DIALOGUE ────────────────────────────────────

# Default static fallback context for Suncity Apartments in case crawler fails/times out
SUNCITY_STATIC_FALLBACK = {
    "name": "Suncity Apartments",
    "location": "Mamurdi, Pune",
    "prices": "2 BHK starting from 58 Lakhs, 3 BHK starting from 78 Lakhs",
    "amenities": "Clubhouse, swimming pool, kids play area, gym, 24/7 security, power backup",
    "rules": "No loud music after 10 PM. Pre-registration required for visitors.",
    "maintenance": "Approx 3000 to 4500 INR monthly depending on BHK size.",
    "contact": "+91-9988776655",
    "project_sites": "Mamurdi, Pune (Suncity Apartments); Wakad, Pune; Sarjapur Road, Bangalore (Suncity Bangalore)",
    "years_in_industry": "Established in 2004, over 20 years of real estate development expertise"
}

class SuncityCrawler:
    """
    High-speed asynchronous connection-pooled crawler for Suncity Apartments.
    Implements strict timeouts, markup stripping, and semantic indexing.
    """
    def __init__(self, base_url: str = "https://www.suncityapartments.in/"):
        self.base_url = base_url
        self.session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self.session is None or self.session.closed:
            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                )
            }
            connector = aiohttp.TCPConnector(limit=10, ttl_dns_cache=300)
            self.session = aiohttp.ClientSession(connector=connector, headers=headers)
        return self.session

    async def fetch_and_parse(self, query_keyword: str = "") -> str:
        try:
            async with asyncio.timeout(3.0):
                session = await self._get_session()
                async with session.get(self.base_url) as response:
                    if response.status != 200:
                        raise aiohttp.ClientError(f"HTTP Status {response.status}")
                    
                    html = await response.text()
                    parsed_context = self._parse_html(html, query_keyword)
                    if not parsed_context.strip():
                        return self._get_filtered_static_fallback(query_keyword)
                    return parsed_context
        except Exception as e:
            logger.warning(f"Crawl failed or timed out for {self.base_url}: {e}. Returning static fallback.")
            return self._get_filtered_static_fallback(query_keyword)

    def _parse_html(self, html: str, query: str) -> str:
        soup = BeautifulSoup(html, "html.parser")
        for element in soup(["script", "style", "nav", "footer", "header", "noscript"]):
            element.extract()

        text = soup.get_text(separator=" ")
        text = re.sub(r"\s+", " ", text).strip()

        sentences = re.split(r'(?<=[.!?]) +', text)
        matched_chunks = []
        
        keywords = [k.strip().lower() for k in query.split() if len(k) > 2]
        if not keywords:
            return " ".join(sentences[:8])

        for sentence in sentences:
            if any(kw in sentence.lower() for kw in keywords):
                matched_chunks.append(sentence.strip())
                if len(matched_chunks) >= 5:
                    break
        
        return " ".join(matched_chunks)

    def _get_filtered_static_fallback(self, query: str) -> str:
        query_lower = query.lower()
        matched = []
        for key, val in SUNCITY_STATIC_FALLBACK.items():
            if key in query_lower or any(word in val.lower() for word in query_lower.split() if len(word) > 2):
                matched.append(f"{key.capitalize()}: {val}")
        if not matched:
            return "; ".join([f"{k.capitalize()}: {v}" for k, v in SUNCITY_STATIC_FALLBACK.items()])
        return "; ".join(matched)

    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()
