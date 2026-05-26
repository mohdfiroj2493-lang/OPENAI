import io
import requests
from pypdf import PdfReader
from .config import HEADERS, DEFAULT_TIMEOUT, MAX_SOURCE_CHARS
from .text_utils import clean_text
from .search_tools import is_pdf_url


def extract_pdf_from_bytes(data: bytes, max_pages=20):
    try:
        reader = PdfReader(io.BytesIO(data))
        pages = []
        for page in reader.pages[:max_pages]:
            pages.append(page.extract_text() or "")
        return clean_text("\n".join(pages))[:MAX_SOURCE_CHARS]
    except Exception:
        return ""


def fetch_pdf_text(url: str, timeout=DEFAULT_TIMEOUT, max_pages=20):
    if not is_pdf_url(url):
        return ""
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout)
        if r.status_code >= 400:
            return ""
        return extract_pdf_from_bytes(r.content, max_pages=max_pages)
    except Exception:
        return ""


def extract_uploaded_pdf(uploaded_file, max_pages=100):
    try:
        reader = PdfReader(uploaded_file)
        pages = []
        for page in reader.pages[:max_pages]:
            pages.append(page.extract_text() or "")
        return clean_text("\n".join(pages))
    except Exception as e:
        return f"PDF read error: {e}"
