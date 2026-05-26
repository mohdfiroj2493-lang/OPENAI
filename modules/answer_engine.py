import re
import wikipedia
from .search_tools import search_all, fetch_webpage_text, ddg_image_search, relevance_score
from .pdf_tools import fetch_pdf_text
from .text_utils import clean_text, extract_key_points, extract_equations, keywords, compress_text
from .config import MAX_TOTAL_CONTEXT_CHARS


def wikipedia_relevant(query: str):
    try:
        hits = wikipedia.search(query, results=5)
        q_words = set(keywords(query))
        best = None
        best_score = -999
        for h in hits:
            try:
                page = wikipedia.page(h, auto_suggest=False)
                text = page.content[:12000]
                score = relevance_score(query, page.title, "", page.url, text)
                title_words = set(keywords(page.title))
                score += len(q_words.intersection(title_words)) * 5
                if score > best_score:
                    best = {"title": page.title, "url": page.url, "snippet": "Wikipedia background source", "text": text, "score": score, "type": "wiki"}
                    best_score = score
            except Exception:
                continue
        if best and best_score > 5:
            return best
    except Exception:
        pass
    return None


def read_sources(query: str, results, max_sources=8):
    sources = []
    total = 0
    for r in results:
        if len(sources) >= max_sources or total >= MAX_TOTAL_CONTEXT_CHARS:
            break
        url = r.get("url", "")
        if not url or r.get("score", 0) < 0:
            continue
        text = fetch_pdf_text(url) if r.get("type") == "pdf" else fetch_webpage_text(url)
        if len(text) < 250:
            continue
        score = relevance_score(query, r.get("title", ""), r.get("snippet", ""), url, text)
        if score < 3:
            continue
        src = dict(r)
        src["text"] = text
        src["score"] = score
        sources.append(src)
        total += len(text)
    if len(sources) < 2:
        wiki = wikipedia_relevant(query)
        if wiki:
            sources.append(wiki)
    return sorted(sources, key=lambda x: x.get("score", 0), reverse=True)


def infer_question_type(query: str):
    q = query.lower()
    if any(x in q for x in ["how many", "methods", "types", "classification"]):
        return "classification"
    if any(x in q for x in ["equation", "formula", "derive", "calculate"]):
        return "equation"
    if any(x in q for x in ["compare", "difference", "vs", "versus"]):
        return "comparison"
    if any(x in q for x in ["procedure", "steps", "how to"]):
        return "procedure"
    return "general"


def build_detailed_answer(query: str, sources):
    if not sources:
        return "I could not find enough relevant readable sources. Try adding more specific technical terms.", []
    combined = "\n\n".join([s.get("text", "") for s in sources])
    qtype = infer_question_type(query)
    key_points = extract_key_points(combined, query, n=22)
    equations = extract_equations(combined, max_items=18)
    source_names = ", ".join([s.get("title", "Untitled")[:70] for s in sources[:5]])
    answer = []
    answer.append(f"## Detailed answer: {query}")
    answer.append("\n### 1. Direct answer")
    if qtype == "classification":
        answer.append("The sources indicate that this question is best answered by grouping the available approaches into major categories, then listing the common practical methods used in design and analysis.")
    elif qtype == "equation":
        answer.append("The sources provide formulas, definitions, and calculation relationships relevant to the question. I extracted the most applicable expressions below and then explain how they are used.")
    else:
        answer.append("Based on the most relevant internet sources found, the topic can be explained using the following key ideas and practical details.")
    answer.append("\n### 2. Main points from sources")
    for p in key_points[:10]:
        answer.append(f"- {p}")
    answer.append("\n### 3. Detailed explanation")
    for p in key_points[10:18]:
        answer.append(f"- {p}")
    if equations:
        answer.append("\n### 4. Applicable equations / expressions found")
        for eq in equations[:12]:
            answer.append(f"- `{eq}`")
    answer.append("\n### 5. Simple explanation")
    simple_points = extract_key_points(combined, query + " simple explanation basic meaning", n=5)
    for p in simple_points[:5]:
        answer.append(f"- {p}")
    answer.append("\n### 6. Practical use / why it matters")
    practical = extract_key_points(combined, query + " design practical application example construction engineering", n=6)
    for p in practical[:6]:
        answer.append(f"- {p}")
    answer.append("\n### 7. Sources used")
    answer.append(f"I used information from: {source_names}.")
    return "\n".join(answer), equations


def research(query: str, include_images=True):
    results = search_all(query, max_per_query=8)
    sources = read_sources(query, results, max_sources=8)
    answer, equations = build_detailed_answer(query, sources)
    images = ddg_image_search(query + " diagram figure", max_results=10) if include_images else []
    return {"answer": answer, "sources": sources, "results": results, "images": images, "equations": equations}
