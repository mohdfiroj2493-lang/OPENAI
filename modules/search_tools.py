import re
import requests
from bs4 import BeautifulSoup
from duckduckgo_search import DDGS
from urllib.parse import urlparse
from .config import HEADERS, DEFAULT_TIMEOUT, MAX_SOURCE_CHARS, ACADEMIC_DOMAINS, GEOTECH_TERMS
from .text_utils import clean_text, keywords


def is_pdf_url(url: str) -> bool:
    return (url or "").lower().split("?")[0].endswith(".pdf")


def domain_of(url: str) -> str:
    try:
        return urlparse(url).netloc.replace("www.", "")
    except Exception:
        return ""


def expand_query(query: str):
    q = clean_text(query)
    q_lower = q.lower()
    queries = [q]
    if any(term in q_lower for term in ["earth pressure", "retaining", "soil pressure", "lateral pressure"]):
        queries.extend([
            f"{q} geotechnical engineering retaining wall",
            f"{q} Rankine Coulomb at rest active passive lateral earth pressure",
            f"{q} PDF geotechnical retaining wall design",
            f"{q} FHWA USACE PDF",
        ])
    elif any(term in q_lower for term in ["equation", "formula", "derive", "calculation"]):
        queries.extend([f"{q} formula equation examples", f"{q} lecture notes pdf", f"{q} explained"])
    else:
        queries.extend([f"{q} detailed explanation", f"{q} pdf report", f"{q} examples"])
    unique = []
    for item in queries:
        if item not in unique:
            unique.append(item)
    return unique[:5]


def relevance_score(query: str, title: str = "", snippet: str = "", url: str = "", body: str = "") -> float:
    q_words = keywords(query)
    combined = f"{title} {snippet} {url} {body[:3000]}".lower()
    score = 0.0
    for word in q_words:
        if word in combined:
            score += 3.0
    query_lower = query.lower()
    domain = domain_of(url).lower()
    if any(d in domain for d in ACADEMIC_DOMAINS):
        score += 2.0
    if is_pdf_url(url):
        score += 1.5
    if "earth pressure" in query_lower:
        geotech_hits = sum(1 for t in GEOTECH_TERMS if t in combined)
        score += geotech_hits * 1.5
        bad_terms = ["moon", "lunar", "astronomy", "planet", "apollo", "satellite", "orbit"]
        if any(b in combined for b in bad_terms):
            score -= 25
        if not any(t in combined for t in ["soil", "retaining", "lateral", "rankine", "coulomb", "geotechnical", "wall"]):
            score -= 12
    return score


def ddg_text_search(query: str, max_results: int = 10):
    results = []
    try:
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=max_results):
                url = r.get("href") or r.get("url") or ""
                if not url:
                    continue
                title = clean_text(r.get("title") or "Untitled")
                snippet = clean_text(r.get("body") or "")
                score = relevance_score(query, title, snippet, url)
                results.append({"title": title, "url": url, "snippet": snippet, "score": score, "type": "pdf" if is_pdf_url(url) else "web"})
    except Exception as e:
        results.append({"title": "Search error", "url": "", "snippet": str(e), "score": -99, "type": "error"})
    return results


def ddg_image_search(query: str, max_results: int = 12):
    images = []
    try:
        with DDGS() as ddgs:
            for r in ddgs.images(query, max_results=max_results):
                img = r.get("image") or r.get("thumbnail") or ""
                if img:
                    images.append({
                        "title": clean_text(r.get("title") or "Image"),
                        "image": img,
                        "url": r.get("url") or r.get("source") or img,
                        "thumbnail": r.get("thumbnail") or img,
                    })
    except Exception:
        pass
    return images


def fetch_webpage_text(url: str, timeout: int = DEFAULT_TIMEOUT):
    try:
        response = requests.get(url, headers=HEADERS, timeout=timeout)
        if response.status_code >= 400:
            return ""
        ctype = response.headers.get("content-type", "").lower()
        if "pdf" in ctype or is_pdf_url(url):
            return ""
        soup = BeautifulSoup(response.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header", "aside", "form", "noscript"]):
            tag.decompose()
        chunks = []
        for tag in soup.find_all(["h1", "h2", "h3", "p", "li", "td", "th"]):
            txt = clean_text(tag.get_text(" "))
            if len(txt) > 35:
                chunks.append(txt)
        return clean_text(" ".join(chunks))[:MAX_SOURCE_CHARS]
    except Exception:
        return ""


def search_all(query: str, max_per_query: int = 8):
    all_results = []
    seen = set()
    for q in expand_query(query):
        for r in ddg_text_search(q, max_results=max_per_query):
            url = r.get("url", "")
            if url and url not in seen:
                r["query_used"] = q
                all_results.append(r)
                seen.add(url)
    all_results = sorted(all_results, key=lambda x: x.get("score", 0), reverse=True)
    return all_results
