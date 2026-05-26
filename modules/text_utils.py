import re
from collections import Counter
from .config import STOPWORDS


def clean_text(text: str) -> str:
    text = text or ""
    text = re.sub(r"\s+", " ", text)
    text = text.replace("\x00", " ")
    return text.strip()


def normalize_query(query: str) -> str:
    return clean_text(query).lower()


def split_sentences(text: str):
    text = clean_text(text)
    if not text:
        return []
    parts = re.split(r"(?<=[.!?])\s+", text)
    return [p.strip() for p in parts if len(p.strip()) > 35]


def keywords(query: str):
    words = re.findall(r"[a-zA-Z][a-zA-Z0-9\-]{2,}", query.lower())
    return [w for w in words if w not in STOPWORDS]


def keyword_counter(text: str, limit=20):
    words = [w.lower() for w in re.findall(r"[a-zA-Z][a-zA-Z0-9\-]{3,}", text or "")]
    words = [w for w in words if w not in STOPWORDS]
    return Counter(words).most_common(limit)


def sentence_score(sentence: str, query_words):
    s = sentence.lower()
    score = 0.0
    for w in query_words:
        if w in s:
            score += 2.5
    score += min(len(sentence) / 200, 2.5)
    boosters = ["equation", "formula", "method", "theory", "approach", "calculation", "defined", "states", "used", "because", "therefore", "example", "design", "factor"]
    if any(b in s for b in boosters):
        score += 1.5
    if len(sentence) > 600:
        score -= 2
    return score


def extract_equations(text: str, max_items=20):
    patterns = [
        r"[A-Za-z][A-Za-z0-9_\s\-()]*\s*=\s*[^.;\n]{2,120}",
        r"[Kk][aop]?\s*=\s*[^.;\n]{2,120}",
        r"[σγφcqusKPaMN/0-9\s_\-()+*/^.=≤≥<>]+",
    ]
    found = []
    for pat in patterns:
        for m in re.finditer(pat, text or ""):
            item = clean_text(m.group(0))
            if 5 <= len(item) <= 160 and any(ch in item for ch in "=≤≥<>^"):
                if item not in found:
                    found.append(item)
            if len(found) >= max_items:
                return found
    return found


def extract_key_points(text: str, query: str, n=10):
    sentences = split_sentences(text)
    if not sentences:
        return []
    q_words = keywords(query)
    ranked = sorted(sentences, key=lambda s: sentence_score(s, q_words), reverse=True)
    selected = []
    seen = set()
    for sent in ranked:
        key = sent[:80].lower()
        if key not in seen:
            selected.append(sent)
            seen.add(key)
        if len(selected) >= n:
            break
    return selected


def compress_text(text: str, query: str, max_sentences=24):
    selected = extract_key_points(text, query, max_sentences)
    return "\n\n".join(selected)


def make_bullets(sentences):
    return "\n".join([f"- {s}" for s in sentences if s])
