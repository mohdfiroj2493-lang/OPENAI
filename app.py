import re
import io
import math
import textwrap
from collections import Counter
from urllib.parse import urlparse

import requests
import streamlit as st
from bs4 import BeautifulSoup
from duckduckgo_search import DDGS
import wikipedia
import pandas as pd
import numpy as np
import sympy as sp
from pypdf import PdfReader
from docx import Document

st.set_page_config(page_title="Powerful Web Research AI", page_icon="🌐", layout="wide")

CUSTOM_CSS = """
<style>
.main-title {font-size: 2.35rem; font-weight: 850; margin-bottom: 0.2rem;}
.subtitle {color: #666; font-size: 1rem; margin-bottom: 1.2rem;}
.answer-card {background: #ffffff; border: 1px solid #e7e7e7; border-radius: 18px; padding: 1.25rem; box-shadow: 0 2px 16px rgba(0,0,0,0.05); line-height: 1.65;}
.source-card {background: #f8f9fb; border: 1px solid #ececec; border-radius: 14px; padding: 0.85rem; margin-bottom: 0.65rem;}
.figure-card {background: #fff; border: 1px solid #eee; border-radius: 14px; padding: 0.65rem; margin-bottom: 0.65rem;}
.small-muted {color: #777; font-size: 0.88rem;}
.badge {display:inline-block; border:1px solid #ddd; border-radius:999px; padding:0.15rem 0.55rem; margin:0.15rem; font-size:0.8rem; background:#fafafa;}
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)
st.markdown('<div class="main-title">🌐 Powerful Web Research AI</div>', unsafe_allow_html=True)
st.markdown('<div class="subtitle">Researches webpages, online PDFs/reports, images, equations, and uploaded files. No API key required.</div>', unsafe_allow_html=True)

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"}

STOPWORDS = set("""
a an and are as at be by for from has have he in is it its of on or that the to was were will with you your i we they them this those these can could should would about into over under than then there their if but not no yes do does did done using use used more most many much such also other some any all each when where what why how who whom whose which write give explain define method methods calculate calculation available everything detailed answer very same chatgpt
""".split())

BAD_TOPIC_WORDS = set("moon lunar astronaut apollo planet satellite astronomy nasa spacecraft orbit celestial".split())


def clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def split_sentences(text: str):
    text = clean_text(text)
    parts = re.split(r"(?<=[.!?])\s+", text)
    return [p.strip() for p in parts if 35 <= len(p.strip()) <= 650]


def keywords(query: str):
    words = re.findall(r"[a-zA-Z][a-zA-Z0-9-]{2,}", query.lower())
    return [w for w in words if w not in STOPWORDS]


def keyphrases(query: str):
    q = query.lower()
    phrases = []
    quoted = re.findall(r'"([^"]+)"', query)
    phrases.extend([x.lower() for x in quoted])
    # Important two/three-word technical phrases from the question itself.
    words = keywords(query)
    for n in [3, 2]:
        for i in range(len(words) - n + 1):
            phrase = " ".join(words[i:i+n])
            if len(phrase) > 7:
                phrases.append(phrase)
    # Remove duplicates while preserving order.
    seen = set()
    out = []
    for p in phrases:
        if p not in seen:
            seen.add(p)
            out.append(p)
    return out[:8]


def relevance_score(text: str, query: str) -> float:
    text_l = (text or "").lower()
    q_words = keywords(query)
    phrases = keyphrases(query)
    if not q_words:
        return 0
    score = 0.0
    for w in q_words:
        if re.search(rf"\b{re.escape(w)}\b", text_l):
            score += 1.0
    for p in phrases:
        if p in text_l:
            score += 4.0
    # Penalize obviously irrelevant astronomy result when query is geotechnical earth pressure.
    if "earth" in q_words and "pressure" in q_words:
        bad_hits = sum(1 for w in BAD_TOPIC_WORDS if w in text_l)
        if bad_hits and "pressure" not in text_l[:2500]:
            score -= 10
        if "earth pressure" in text_l:
            score += 8
        if any(x in text_l for x in ["retaining wall", "rankine", "coulomb", "active pressure", "passive pressure", "at-rest pressure", "lateral earth pressure"]):
            score += 8
    coverage = sum(1 for w in set(q_words) if w in text_l) / max(len(set(q_words)), 1)
    return score + 5 * coverage


def is_relevant(text: str, query: str, min_score: float = 7.0) -> bool:
    return relevance_score(text, query) >= min_score


def sentence_score(sentence: str, query_words, phrases):
    s = sentence.lower()
    score = 0.0
    for w in query_words:
        if re.search(rf"\b{re.escape(w)}\b", s):
            score += 2.0
    for p in phrases:
        if p in s:
            score += 4.0
    if any(x in s for x in ["formula", "equation", "method", "theory", "rankine", "coulomb", "coefficient", "pressure", "used", "based on", "assumes", "calculated"]):
        score += 2.0
    score += min(len(sentence) / 220, 2)
    return score


def build_search_queries(query: str):
    phrases = keyphrases(query)
    q_clean = query.strip()
    qs = [q_clean]
    if phrases:
        qs.append('"' + phrases[0] + '" ' + q_clean)
    qs.append(q_clean + " methods formulas")
    qs.append(q_clean + " pdf report")
    qs.append(q_clean + " site:edu OR site:gov")
    # Generic engineering context when user asks earth pressure, without hardcoding the answer.
    if "earth" in q_clean.lower() and "pressure" in q_clean.lower():
        qs.extend([
            '"earth pressure" "retaining wall" methods Rankine Coulomb',
            '"lateral earth pressure" calculation methods pdf',
            '"active passive at-rest earth pressure"',
        ])
    # Deduplicate.
    out = []
    seen = set()
    for q in qs:
        if q not in seen:
            out.append(q)
            seen.add(q)
    return out[:8]


def ddg_search(query: str, max_results: int = 8):
    results = []
    try:
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=max_results):
                title = r.get("title") or "Untitled"
                href = r.get("href") or r.get("url") or ""
                body = r.get("body") or ""
                if href:
                    results.append({"title": title, "url": href, "snippet": body})
    except Exception as e:
        st.warning(f"Search issue: {e}")
    return results


def ddg_image_search(query: str, max_results: int = 6):
    imgs = []
    try:
        with DDGS() as ddgs:
            for r in ddgs.images(query, max_results=max_results):
                image = r.get("image") or r.get("thumbnail") or ""
                title = r.get("title") or "Figure"
                source = r.get("url") or r.get("source") or ""
                if image:
                    imgs.append({"title": title, "image": image, "source": source})
    except Exception:
        pass
    return imgs


def fetch_page_text(url: str, timeout: int = 10):
    try:
        response = requests.get(url, headers=HEADERS, timeout=timeout)
        if response.status_code >= 400:
            return ""
        content_type = response.headers.get("content-type", "").lower()
        if "pdf" in content_type or url.lower().endswith(".pdf"):
            reader = PdfReader(io.BytesIO(response.content))
            pages = []
            for page in reader.pages[:15]:
                pages.append(page.extract_text() or "")
            return clean_text(" ".join(pages))[:30000]
        soup = BeautifulSoup(response.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header", "aside", "form"]):
            tag.decompose()
        items = []
        for tag in soup.find_all(["h1", "h2", "h3", "p", "li", "td", "th"]):
            t = clean_text(tag.get_text(" "))
            if len(t) > 35:
                items.append(t)
        return clean_text(" ".join(items))[:30000]
    except Exception:
        return ""


def safe_wikipedia_fallback(query: str):
    try:
        hits = wikipedia.search(query, results=6)
        for hit in hits:
            try:
                page = wikipedia.page(hit, auto_suggest=False)
                text = page.title + " " + page.content[:12000]
                if is_relevant(text, query, min_score=9.0):
                    return {"title": page.title, "url": page.url, "text": page.content[:12000]}
            except Exception:
                continue
    except Exception:
        return None
    return None


def extract_equations(text: str, limit: int = 12):
    candidates = []
    patterns = [
        r"\b[A-Za-z][A-Za-z0-9_]*\s*=\s*[^.;,\n]{2,80}",
        r"\bK[_a-zA-Z0-9]*\s*=\s*[^.;,\n]{2,80}",
        r"\bP[_a-zA-Z0-9]*\s*=\s*[^.;,\n]{2,80}",
        r"\b\w+\s*\^\s*2\s*=\s*[^.;,\n]{2,80}",
    ]
    for pat in patterns:
        for m in re.finditer(pat, text):
            eq = clean_text(m.group(0))
            if 4 <= len(eq) <= 100 and not eq.lower().startswith(("http", "figure", "table")):
                candidates.append(eq)
    seen = set()
    out = []
    for c in candidates:
        c = re.sub(r"\s+", " ", c)
        if c not in seen:
            seen.add(c)
            out.append(c)
    return out[:limit]


def make_detailed_answer(query: str, source_texts, sources):
    full_text = clean_text("\n\n".join(source_texts))
    sentences = split_sentences(full_text)
    q_words = keywords(query)
    phrases = keyphrases(query)

    ranked = sorted(sentences, key=lambda s: sentence_score(s, q_words, phrases), reverse=True)
    chosen = []
    seen = set()
    for s in ranked:
        simplified = re.sub(r"[^a-z0-9]+", " ", s.lower())[:160]
        if simplified not in seen:
            chosen.append(s)
            seen.add(simplified)
        if len(chosen) >= 18:
            break

    if not chosen:
        return "I found sources, but could not extract enough readable text. Try adding more specific terms."

    equations = extract_equations(full_text)
    domains = sorted(set(urlparse(s["url"]).netloc.replace("www.", "") for s in sources if s.get("url")))

    # Build structured answer from source sentences. This is extractive, not a hardcoded answer.
    intro_sentences = chosen[:3]
    detail_sentences = chosen[3:12]
    practical_sentences = chosen[12:18]

    md = []
    md.append(f"## Detailed answer: {query}\n")
    md.append("### 1. Main answer")
    for s in intro_sentences:
        md.append(f"- {s}")

    md.append("\n### 2. Important details from sources")
    for s in detail_sentences:
        md.append(f"- {s}")

    if equations:
        md.append("\n### 3. Applicable equations / expressions found online")
        for eq in equations[:10]:
            md.append(f"- `{eq}`")
    else:
        md.append("\n### 3. Applicable equations / expressions found online")
        md.append("- I did not find clean equation text in the readable pages. Try adding words like `formula`, `equation`, or `PDF` to the question.")

    md.append("\n### 4. Simple explanation")
    for s in intro_sentences[:2] + detail_sentences[:2]:
        md.append(f"- {s}")

    if practical_sentences:
        md.append("\n### 5. Practical use / why it matters")
        for s in practical_sentences:
            md.append(f"- {s}")

    md.append("\n### 6. What I used")
    if domains:
        md.append("I used readable content from: " + ", ".join(domains[:8]) + ".")
    else:
        md.append("I used readable internet search results.")
    return "\n".join(md)


def research_answer(query: str):
    queries = build_search_queries(query)
    all_results = []
    seen_urls = set()

    for q in queries:
        for r in ddg_search(q, max_results=6):
            if r["url"] not in seen_urls:
                seen_urls.add(r["url"])
                r["search_query"] = q
                all_results.append(r)

    # Rank search results by title/snippet relevance before fetching pages.
    all_results = sorted(
        all_results,
        key=lambda r: relevance_score((r.get("title", "") + " " + r.get("snippet", "")), query),
        reverse=True,
    )

    source_texts = []
    sources = []

    for result in all_results[:12]:
        preview = result.get("title", "") + " " + result.get("snippet", "")
        if relevance_score(preview, query) < 2.5:
            continue
        page_text = fetch_page_text(result["url"])
        combined = clean_text((preview + " " + page_text).strip())
        if len(combined) > 250 and is_relevant(combined, query, min_score=7.0):
            source_texts.append(combined)
            result["relevance"] = round(relevance_score(combined, query), 2)
            sources.append(result)
        if len(source_texts) >= 6:
            break

    if len(source_texts) < 2:
        wiki = safe_wikipedia_fallback(query)
        if wiki:
            source_texts.append(wiki["text"])
            sources.append({"title": wiki["title"] + " Wikipedia", "url": wiki["url"], "snippet": "Wikipedia fallback source", "relevance": round(relevance_score(wiki["text"], query), 2)})

    if not source_texts:
        return (
            "I could not find reliable relevant sources for this question. Try using more specific technical words, for example: `earth pressure retaining wall Rankine Coulomb methods`. I rejected irrelevant results instead of giving a wrong answer.",
            [],
            [],
        )

    answer = make_detailed_answer(query, source_texts, sources)
    figures = ddg_image_search(query + " diagram figure", max_results=6)
    # Keep figures roughly relevant by title/source text.
    figures = [f for f in figures if relevance_score(f.get("title", "") + " " + f.get("source", ""), query) >= 1.0][:4]
    return answer, sources, figures


def extract_pdf_text(uploaded_file):
    reader = PdfReader(uploaded_file)
    text = []
    for page in reader.pages:
        text.append(page.extract_text() or "")
    return "\n".join(text)


def extract_docx_text(uploaded_file):
    doc = Document(uploaded_file)
    return "\n".join([p.text for p in doc.paragraphs])


def extract_txt_text(uploaded_file):
    return uploaded_file.read().decode("utf-8", errors="ignore")


def basic_document_summary(text, focus=""):
    sentences = split_sentences(text)
    if not sentences:
        return "No readable text found."
    key_source = focus if focus else text[:5000]
    words = keywords(key_source)
    if not words:
        words = [w.lower() for w in re.findall(r"[a-zA-Z]{4,}", text) if w.lower() not in STOPWORDS]
    common = [w for w, _ in Counter(words).most_common(15)]
    ranked = sorted(sentences, key=lambda s: sentence_score(s, common, keyphrases(focus)), reverse=True)[:12]
    ranked = sorted(ranked, key=lambda s: sentences.index(s))
    return "\n\n".join([f"- {s}" for s in ranked])


def solve_math(expr):
    try:
        x = sp.symbols("x")
        if "=" in expr:
            left, right = expr.split("=", 1)
            sol = sp.solve(sp.sympify(left) - sp.sympify(right), x)
            return f"Solution: {sol}"
        result = sp.sympify(expr)
        return f"Result: {sp.simplify(result)}"
    except Exception as e:
        return f"Could not solve that expression. Error: {e}"


if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "Hi! Ask me anything. I will search the internet, reject irrelevant results, read sources/PDFs, and answer with links."}
    ]

with st.sidebar:
    st.header("Tools")
    mode = st.radio("Choose mode", ["Internet Chat", "Document Assistant", "CSV Analyzer", "Math Solver"], index=0)
    st.caption("No OpenAI/Claude API key. This is a web-research assistant, not a true LLM.")
    st.markdown("### Search quality")
    st.write("The app now checks relevance before using sources, so `earth pressure` will not turn into `Moon` results.")

if mode == "Internet Chat":
    st.subheader("Ask from the internet")
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    question = st.chat_input("Ask a detailed question...")
    if question:
        st.session_state.messages.append({"role": "user", "content": question})
        with st.chat_message("user"):
            st.markdown(question)

        with st.chat_message("assistant"):
            with st.spinner("Searching multiple web queries, reading webpages/PDFs, checking relevance, and preparing answer..."):
                answer, sources, figures = research_answer(question)
            st.markdown(f'<div class="answer-card">{answer}</div>', unsafe_allow_html=True)

            if figures:
                st.markdown("### Related figures / diagrams")
                cols = st.columns(min(2, len(figures)))
                for i, fig in enumerate(figures):
                    with cols[i % len(cols)]:
                        st.image(fig["image"], caption=fig.get("title", "Figure"), use_container_width=True)
                        if fig.get("source"):
                            st.markdown(f"[Image source]({fig['source']})")

            if sources:
                st.markdown("### Sources read")
                for i, src in enumerate(sources[:8], start=1):
                    st.markdown(
                        f'<div class="source-card"><b>{i}. {src["title"]}</b> <span class="badge">relevance {src.get("relevance", "")}</span><br><a href="{src["url"]}" target="_blank">{src["url"]}</a><br><span class="small-muted">{src.get("snippet", "")}</span></div>',
                        unsafe_allow_html=True,
                    )
            saved = answer + "\n\nSources:\n" + "\n".join([f"- {s['title']}: {s['url']}" for s in sources[:8]])
            st.session_state.messages.append({"role": "assistant", "content": saved})

elif mode == "Document Assistant":
    st.subheader("Upload and summarize documents")
    file = st.file_uploader("Upload PDF, DOCX, or TXT", type=["pdf", "docx", "txt"])
    if file:
        with st.spinner("Reading document..."):
            if file.name.lower().endswith(".pdf"):
                text = extract_pdf_text(file)
            elif file.name.lower().endswith(".docx"):
                text = extract_docx_text(file)
            else:
                text = extract_txt_text(file)
        st.success(f"Extracted approximately {len(text):,} characters.")
        user_focus = st.text_input("Optional: what should I focus on?", "")
        if st.button("Summarize document"):
            st.markdown(basic_document_summary(text, user_focus))

elif mode == "CSV Analyzer":
    st.subheader("CSV data analyzer")
    file = st.file_uploader("Upload CSV", type=["csv"])
    if file:
        df = pd.read_csv(file)
        st.dataframe(df, use_container_width=True)
        st.markdown("### Summary")
        st.write(df.describe(include="all"))
        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        if numeric_cols:
            col = st.selectbox("Choose numeric column for chart", numeric_cols)
            st.bar_chart(df[col])

elif mode == "Math Solver":
    st.subheader("Math solver")
    expr = st.text_input("Enter expression or equation, for example: x**2 - 5*x + 6 = 0")
    if st.button("Solve") and expr:
        st.markdown(solve_math(expr))
