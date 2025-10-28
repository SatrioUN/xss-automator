import asyncio
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
import httpx
import logging

logger = logging.getLogger(__name__)

class Crawler:
    def __init__(self, base_url, allow_hosts, max_pages=200, rps=5, respect_robots=True, timeout=15):
        self.base = base_url
        self.allow_hosts = set([h for h in (allow_hosts or []) if h])
        self.max_pages = max_pages
        self.rate_limit = rps
        self.respect_robots = respect_robots
        self.timeout = timeout
        self.visited = set()
        self.to_visit = [base_url]
        self.client = httpx.AsyncClient(timeout=self.timeout, follow_redirects=True)

    async def fetch(self, url):
        await asyncio.sleep(1.0 / max(1, self.rate_limit))
        try:
            r = await self.client.get(url)
            return r
        except Exception:
            logger.debug("Fetch failed for %s", url, exc_info=True)
            return None

    async def crawl(self):
        results = []
        while self.to_visit and len(self.visited) < self.max_pages:
            url = self.to_visit.pop(0)
            if url in self.visited:
                continue
            parsed = urlparse(url)
            hostname = parsed.hostname
            if hostname and self.allow_hosts and hostname not in self.allow_hosts:
                self.visited.add(url)
                continue
            self.visited.add(url)
            r = await self.fetch(url)
            if not r:
                continue
            results.append((url, r))
            try:
                soup = BeautifulSoup(r.text or "", "html.parser")
            except Exception:
                soup = BeautifulSoup("", "html.parser")
            for a in soup.find_all("a", href=True):
                href = a['href']
                next_url = urljoin(url, href)
                parsed2 = urlparse(next_url)
                if parsed2.scheme in ('http','https'):
                    nh = parsed2.hostname
                    if nh and (not self.allow_hosts or nh in self.allow_hosts):
                        if next_url not in self.visited and next_url not in self.to_visit:
                            self.to_visit.append(next_url)
        try:
            await self.client.aclose()
        except Exception:
            pass
        return results