import io
import re
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

st.set_page_config(
    page_title="Powerful Web Research AI Assistant",
    page_icon="🌐",
    layout="wide",
)

CUSTOM_CSS = """
<style>
.main-title {font-size: 2.4rem; font-weight: 900; margin-bottom: 0.2rem;}
.subtitle {color: #5f6368; font-size: 1rem; margin-bottom: 1rem;}
.answer-card {background: #ffffff; border: 1px solid #e7e7e7; border-radius: 20px; padding: 1.25rem; box-shadow: 0 4px 22px rgba(0,0,0,0.045); margin-bottom: 1rem;}
.source-card {background: #f8fafc; border: 1px solid #e8edf3; border-radius: 16px; padding: 0.85rem; margin-bottom: 0.7rem;}
.metric-card {background: #f6f8fb; border: 1px solid #edf0f4; border-radius: 16px; padding: 1rem;}
.small-muted {color: #6b7280; font-size: 0.88rem;}
.badge {display: inline-block; background: #eef2ff; color: #3730a3; border-radius: 999px; padding: 0.16rem 0.55rem; font-size: 0.78rem; margin-right: 0.35rem;}
.eq-box {background: #0f172a; color: #f8fafc; border-radius: 14px; padding: 0.8rem 1rem; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; margin: 0.35rem 0;}
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)
st.markdown('<div class="main-title">🌐 Powerful Web Research AI Assistant</div>', unsafe_allow_html=True)
st.markdown('<div class="subtitle">Searches webpages, online PDFs/reports, images, and your uploaded files. No API key required.</div>', unsafe_allow_html=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/123 Safari/537.36"
}

STOPWORDS = set("""
a an and are as at be by for from has have he in is it its of on or that the to was were will with you your i we they them this those these can could should would about into over under than then there their if but not no yes do does did done using use used more most many much such also other some any all each when where what why how who whom whose which write give explain define equation equations motion law formula formulas information detailed full complete everything applicable report pdf online google internet source sources
""".split())

MATH_SCIENCE_HINTS = [
    "equation", "formula", "motion", "velocity", "acceleration", "force", "energy", "momentum",
    "physics", "math", "calculus", "algebra", "geometry", "graph", "diagram", "figure",
]


def clean_text(text: str) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    return text


def safe_domain(url: str) -> str:
    try:
        return urlparse(url).netloc.replace("www.", "")
    except Exception:
        return "source"


def split_sentences(text: str):
    text = clean_text(text)
    parts = re.split(r"(?<=[.!?])\s+", text)
    return [p.strip() for p in parts if 35 <= len(p.strip()) <= 650]


def keywords(query: str):
    words = re.findall(r"[a-zA-Z][a-zA-Z0-9-]{2,}", query.lower())
    return [w for w in words if w not in STOPWORDS]


def sentence_score(sentence: str, query_words):
    s = sentence.lower()
    score = 0.0
    for w in query_words:
        if w in s:
            score += 3.0
    score += min(len(sentence) / 170, 2.5)
    boost_terms = [
        "formula", "equation", "defined", "states", "known as", "used to", "therefore",
        "because", "example", "where", "unit", "law", "principle", "relationship", "derived",
        "figure", "table", "report", "study", "pdf", "standard",
    ]
    if any(x in s for x in boost_terms):
        score += 2.0
    if re.search(r"[=±√∑∫π]|\b[a-zA-Z]\s*=\s*", sentence):
        score += 2.5
    return score


def extract_equations(text: str, limit: int = 12):
    candidates = []
    # Pull compact equation-looking strings and sentences with equations.
    for sent in split_sentences(text):
        if re.search(r"[=±√∑∫π]|\b[a-zA-Z][a-zA-Z0-9_]*\s*=\s*", sent):
            cleaned = clean_text(sent)
            if len(cleaned) < 260:
                candidates.append(cleaned)
    # Also catch common inline symbolic fragments.
    fragments = re.findall(r"\b[A-Za-z][A-Za-z0-9_]*(?:\s*[+\-*/^=]\s*[A-Za-z0-9().^*/+\-]+){1,8}", text)
    for frag in fragments:
        if "=" in frag and 4 <= len(frag) <= 90:
            candidates.append(frag)
    seen, unique = set(), []
    for c in candidates:
        key = re.sub(r"\W+", "", c.lower())[:120]
        if key and key not in seen:
            seen.add(key)
            unique.append(c)
        if len(unique) >= limit:
            break
    return unique


def ddg_text_search(query: str, max_results: int = 8):
    results = []
    try:
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=max_results):
                title = r.get("title") or "Untitled"
                href = r.get("href") or r.get("url") or ""
                body = r.get("body") or ""
                if href and href not in [x["url"] for x in results]:
                    results.append({"title": title, "url": href, "snippet": body, "kind": "web"})
    except Exception as e:
        st.warning(f"Search issue: {e}")
    return results


def ddg_image_search(query: str, max_results: int = 6):
    images = []
    try:
        with DDGS() as ddgs:
            for r in ddgs.images(query, max_results=max_results):
                image_url = r.get("image") or r.get("thumbnail")
                title = r.get("title") or "Image result"
                source = r.get("url") or r.get("source") or ""
                if image_url:
                    images.append({"title": title, "image": image_url, "source": source})
    except Exception:
        pass
    return images


def fetch_html_text(url: str, timeout: int = 10):
    try:
        response = requests.get(url, headers=HEADERS, timeout=timeout)
        if response.status_code >= 400:
            return ""
        ctype = response.headers.get("content-type", "").lower()
        if "pdf" in ctype or url.lower().endswith(".pdf"):
            return fetch_pdf_text_from_bytes(response.content)
        soup = BeautifulSoup(response.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header", "aside", "form", "button"]):
            tag.decompose()
        parts = []
        for tag in soup.find_all(["h1", "h2", "h3", "p", "li", "td"]):
            t = clean_text(tag.get_text(" "))
            if len(t) > 35:
                parts.append(t)
        return clean_text(" ".join(parts))[:25000]
    except Exception:
        return ""


def fetch_pdf_text_from_bytes(data: bytes, max_pages: int = 8):
    try:
        reader = PdfReader(io.BytesIO(data))
        pages = []
        for page in reader.pages[:max_pages]:
            pages.append(page.extract_text() or "")
        return clean_text("\n".join(pages))[:25000]
    except Exception:
        return ""


def wikipedia_fallback(query: str):
    try:
        hits = wikipedia.search(query, results=3)
        if not hits:
            return None
        page = wikipedia.page(hits[0], auto_suggest=False)
        return {"title": page.title, "url": page.url, "text": page.content[:16000], "kind": "wikipedia"}
    except Exception:
        return None


def collect_sources(query: str, web_count: int, pdf_count: int):
    search_queries = [query]
    if pdf_count > 0:
        search_queries += [f'{query} filetype:pdf', f'{query} lecture notes pdf OR report pdf']

    raw_results = []
    seen_urls = set()
    for sq in search_queries:
        for r in ddg_text_search(sq, max_results=web_count):
            if r["url"] not in seen_urls:
                seen_urls.add(r["url"])
                raw_results.append(r)

    selected = []
    pdf_seen = 0
    web_seen = 0
    for r in raw_results:
        is_pdf = ".pdf" in r["url"].lower() or "pdf" in r["title"].lower()
        if is_pdf and pdf_seen >= pdf_count:
            continue
        if not is_pdf and web_seen >= web_count:
            continue
        if is_pdf:
            pdf_seen += 1
            r["kind"] = "pdf/report"
        else:
            web_seen += 1
            r["kind"] = "web"
        selected.append(r)

    source_docs = []
    progress = st.progress(0) if selected else None
    for i, result in enumerate(selected):
        if progress:
            progress.progress((i + 1) / max(1, len(selected)))
        page_text = fetch_html_text(result["url"])
        combined = clean_text((result.get("snippet", "") + " " + page_text).strip())
        if len(combined) > 120:
            source_docs.append({**result, "text": combined})

    if progress:
        progress.empty()

    if len(source_docs) < 2:
        wiki = wikipedia_fallback(query)
        if wiki:
            source_docs.append({
                "title": wiki["title"],
                "url": wiki["url"],
                "snippet": "Wikipedia fallback source",
                "kind": "wikipedia",
                "text": wiki["text"],
            })
    return source_docs


def rank_sentences_from_sources(source_docs, query: str, limit: int):
    q_words = keywords(query)
    rows = []
    for src_idx, src in enumerate(source_docs, start=1):
        for sent in split_sentences(src["text"]):
            score = sentence_score(sent, q_words)
            rows.append((score, sent, src_idx, src))
    rows = sorted(rows, key=lambda x: x[0], reverse=True)

    selected = []
    seen = set()
    for score, sent, src_idx, src in rows:
        key = re.sub(r"\W+", "", sent.lower())[:150]
        if key and key not in seen:
            seen.add(key)
            selected.append((sent, src_idx, src))
        if len(selected) >= limit:
            break
    return selected


def build_detailed_answer(query: str, source_docs, detail_level: str):
    sentence_limit = {"Medium": 12, "Detailed": 20, "Very detailed": 32}.get(detail_level, 20)
    ranked = rank_sentences_from_sources(source_docs, query, limit=sentence_limit)
    all_text = "\n\n".join(src["text"] for src in source_docs)
    equations = extract_equations(all_text, limit=16)

    if not ranked:
        return "I found sources, but I could not extract enough readable content. Try a more specific question.", equations

    # Create a long, ChatGPT-like structured answer using sourced extracted content.
    top_keywords = Counter([w for w in re.findall(r"[a-zA-Z]{4,}", all_text.lower()) if w not in STOPWORDS]).most_common(10)
    topic_terms = ", ".join([w for w, _ in top_keywords[:8]])

    answer = []
    answer.append(f"## Direct answer\n")
    for sent, src_idx, src in ranked[:4]:
        answer.append(f"{sent} **[{src_idx}]**")

    answer.append("\n## Detailed explanation\n")
    for sent, src_idx, src in ranked[4: max(10, sentence_limit // 2)]:
        answer.append(f"- {sent} **[{src_idx}]**")

    if equations:
        answer.append("\n## Applicable equations / expressions found online\n")
        for eq in equations[:10]:
            answer.append(f"```text\n{eq}\n```")

    answer.append("\n## Important points to remember\n")
    for sent, src_idx, src in ranked[max(10, sentence_limit // 2):sentence_limit]:
        answer.append(f"- {sent} **[{src_idx}]**")

    if topic_terms:
        answer.append(f"\n## Related terms found in sources\n{topic_terms}")

    answer.append("\n## Source index\n")
    for i, src in enumerate(source_docs, start=1):
        answer.append(f"**[{i}] {src['title']}** — {safe_domain(src['url'])} — {src.get('kind', 'web')}")

    return "\n\n".join(answer), equations


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


def summarize_uploaded_document(text, focus=""):
    query = focus or "important summary findings conclusions recommendations"
    fake_source = [{"title": "Uploaded document", "url": "uploaded-file", "snippet": "User uploaded document", "kind": "upload", "text": text[:50000]}]
    answer, _ = build_detailed_answer(query, fake_source, "Detailed")
    return answer


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
        {"role": "assistant", "content": "Hi! Ask me anything. I will search webpages, online PDFs/reports, and images, then write a detailed sourced answer."}
    ]

with st.sidebar:
    st.header("Research Settings")
    mode = st.radio("Choose mode", ["Internet Research Chat", "Document Assistant", "CSV Analyzer", "Math Solver"], index=0)
    detail_level = st.select_slider("Answer detail", options=["Medium", "Detailed", "Very detailed"], value="Very detailed")
    web_count = st.slider("Web pages to read", 3, 12, 8)
    pdf_count = st.slider("Online PDFs/reports to try", 0, 6, 3)
    show_images = st.checkbox("Show image/figure results when available", value=True)
    st.caption("No OpenAI/Claude API key is used. Answers are generated by web/PDF extraction and source-based summarization.")

if mode == "Internet Research Chat":
    st.subheader("Ask from webpages, online reports/PDFs, and images")
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    question = st.chat_input("Ask a question, for example: write equation of motion")
    if question:
        st.session_state.messages.append({"role": "user", "content": question})
        with st.chat_message("user"):
            st.markdown(question)

        with st.chat_message("assistant"):
            with st.spinner("Searching the web, opening pages, reading PDFs/reports, and building a detailed answer..."):
                docs = collect_sources(question, web_count=web_count, pdf_count=pdf_count)
                images = ddg_image_search(question + " diagram figure", max_results=6) if show_images else []

            if not docs:
                answer = "I could not find readable online content for this question. Try rephrasing the question or reducing restrictions."
                st.error(answer)
            else:
                answer, equations = build_detailed_answer(question, docs, detail_level)
                st.markdown(f'<div class="answer-card">', unsafe_allow_html=True)
                st.markdown(answer)
                st.markdown('</div>', unsafe_allow_html=True)

                if images:
                    st.markdown("## Figures / image results")
                    cols = st.columns(3)
                    for i, img in enumerate(images[:6]):
                        with cols[i % 3]:
                            try:
                                st.image(img["image"], caption=img["title"], use_container_width=True)
                                if img.get("source"):
                                    st.caption(img["source"])
                            except Exception:
                                pass

                st.markdown("## Sources")
                for i, src in enumerate(docs, start=1):
                    st.markdown(
                        f'<div class="source-card"><span class="badge">{src.get("kind", "web")}</span><b>[{i}] {src["title"]}</b><br>'
                        f'<a href="{src["url"]}" target="_blank">{src["url"]}</a><br>'
                        f'<span class="small-muted">{src.get("snippet", "")}</span></div>',
                        unsafe_allow_html=True,
                    )

            saved_sources = "\n".join([f"[{i}] {s['title']}: {s['url']}" for i, s in enumerate(docs, 1)]) if docs else ""
            st.session_state.messages.append({"role": "assistant", "content": answer + "\n\n" + saved_sources})

elif mode == "Document Assistant":
    st.subheader("Upload and analyze documents")
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
        if st.button("Analyze document"):
            st.markdown(summarize_uploaded_document(text, user_focus))

elif mode == "CSV Analyzer":
    st.subheader("CSV data analyzer")
    file = st.file_uploader("Upload CSV", type=["csv"])
    if file:
        df = pd.read_csv(file)
        st.dataframe(df, use_container_width=True)
        st.markdown("### Data summary")
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
