import io
import re
import math
import time
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
    page_title="Power Research AI Assistant",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
)

CUSTOM_CSS = """
<style>
.block-container {padding-top: 1.2rem;}
.hero {
    background: linear-gradient(135deg, #111827, #1f2937, #374151);
    color: white;
    padding: 1.4rem 1.6rem;
    border-radius: 24px;
    margin-bottom: 1rem;
    box-shadow: 0 8px 28px rgba(0,0,0,.16);
}
.hero h1 {font-size: 2.25rem; margin: 0; font-weight: 850;}
.hero p {margin: .35rem 0 0; opacity: .88; font-size: 1.03rem;}
.answer-card {
    background: #ffffff;
    border: 1px solid #e5e7eb;
    border-radius: 20px;
    padding: 1.15rem 1.25rem;
    box-shadow: 0 4px 18px rgba(15,23,42,.05);
    line-height: 1.62;
}
.source-card {
    background: #f9fafb;
    border: 1px solid #e5e7eb;
    border-radius: 16px;
    padding: .9rem;
    margin: .45rem 0;
}
.metric-card {
    background: #f9fafb;
    border: 1px solid #e5e7eb;
    border-radius: 16px;
    padding: .9rem;
}
.small-muted {color: #6b7280; font-size: .88rem;}
.tag {display: inline-block; background: #eef2ff; color: #3730a3; padding: .16rem .5rem; border-radius: 999px; font-size: .78rem; margin-right: .3rem;}
img.figure-img {border-radius: 14px; border: 1px solid #e5e7eb; max-height: 230px; object-fit: cover; width: 100%;}
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)
st.markdown(
    '<div class="hero"><h1>🧠 Power Research AI Assistant</h1><p>Detailed internet research, online PDFs, figures, equations, document analysis, math, and data tools. No API key required.</p></div>',
    unsafe_allow_html=True,
)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/123 Safari/537.36"
}

STOPWORDS = set("""
a an and are as at be by for from has have he her him his i in is it its of on or that the to was were will with you your we they them this those these can could should would about into over under than then there their if but not no yes do does did done using use used more most many much such also other some any all each when where what why how who whom whose which write give explain define equation equations motion law formula formulas tell discuss describe provide please make detailed detail answer everything applicable expression expressions figure image report pdf online internet google
""".split())

SCIENCE_WORDS = {
    "physics", "chemistry", "biology", "math", "equation", "formula", "motion", "force", "energy", "velocity", "acceleration",
    "concrete", "soil", "geotechnical", "foundation", "engineering", "construction", "beam", "load", "stress", "strain"
}


def clean_text(text: str) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    return text


def split_sentences(text: str):
    text = clean_text(text)
    parts = re.split(r"(?<=[.!?])\s+", text)
    return [p.strip() for p in parts if 35 <= len(p.strip()) <= 700]


def keywords(query: str):
    words = re.findall(r"[a-zA-Z][a-zA-Z0-9-]{2,}", query.lower())
    return [w for w in words if w not in STOPWORDS]


def domain_name(url: str) -> str:
    try:
        return urlparse(url).netloc.replace("www.", "")
    except Exception:
        return "source"


def safe_get(url: str, timeout: int = 12):
    try:
        return requests.get(url, headers=HEADERS, timeout=timeout, allow_redirects=True)
    except Exception:
        return None


def ddg_text_search(query: str, max_results: int = 10):
    results = []
    try:
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=max_results):
                title = r.get("title") or "Untitled"
                url = r.get("href") or r.get("url") or ""
                snippet = r.get("body") or ""
                if url and not any(bad in url.lower() for bad in ["/search?", "duckduckgo.com"]):
                    results.append({"title": title, "url": url, "snippet": snippet, "kind": "web"})
    except Exception as e:
        st.warning(f"Search issue: {e}")
    return results


def ddg_image_search(query: str, max_results: int = 6):
    images = []
    try:
        with DDGS() as ddgs:
            for r in ddgs.images(query, max_results=max_results):
                img = r.get("image") or r.get("thumbnail") or ""
                title = r.get("title") or "Figure"
                source = r.get("url") or r.get("source") or ""
                if img:
                    images.append({"title": title, "image": img, "source": source})
    except Exception:
        pass
    return images


def extract_html_text(url: str, limit: int = 22000):
    response = safe_get(url)
    if not response or response.status_code >= 400:
        return ""
    content_type = response.headers.get("content-type", "").lower()
    if "pdf" in content_type or url.lower().endswith(".pdf"):
        return extract_pdf_from_bytes(response.content, limit=limit)
    try:
        soup = BeautifulSoup(response.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header", "aside", "form", "noscript"]):
            tag.decompose()
        chunks = []
        for tag in soup.find_all(["h1", "h2", "h3", "p", "li", "table"]):
            t = clean_text(tag.get_text(" "))
            if len(t) > 45:
                chunks.append(t)
        return clean_text(" ".join(chunks))[:limit]
    except Exception:
        return ""


def extract_pdf_from_bytes(data: bytes, limit: int = 22000):
    try:
        reader = PdfReader(io.BytesIO(data))
        pages = []
        for page in reader.pages[:12]:
            pages.append(page.extract_text() or "")
        return clean_text("\n".join(pages))[:limit]
    except Exception:
        return ""


def wikipedia_source(query: str):
    try:
        hits = wikipedia.search(query, results=3)
        if not hits:
            return None
        page = wikipedia.page(hits[0], auto_suggest=False)
        return {"title": page.title, "url": page.url, "snippet": "Wikipedia background source", "kind": "wikipedia", "text": page.content[:18000]}
    except Exception:
        return None


def score_sentence(sentence: str, q_words):
    s = sentence.lower()
    score = 0.0
    for w in q_words:
        if w in s:
            score += 2.5
    if any(x in s for x in ["equation", "formula", "law", "states", "defined", "definition", "therefore", "because", "used", "applications", "example", "where", "unit", "figure", "diagram"]):
        score += 1.4
    if re.search(r"[A-Za-z]\s*=|\d|\^|²|³|√|/", sentence):
        score += 1.2
    score += min(len(sentence) / 220, 2.0)
    return score


def rank_sentences(text: str, query: str, max_items: int = 22):
    sents = split_sentences(text)
    if not sents:
        return []
    q_words = keywords(query)
    ranked = sorted(sents, key=lambda s: score_sentence(s, q_words), reverse=True)
    selected = []
    seen = set()
    for s in ranked:
        simple = re.sub(r"[^a-z0-9]", "", s.lower())[:100]
        if simple not in seen:
            selected.append(s)
            seen.add(simple)
        if len(selected) >= max_items:
            break
    return selected


def extract_equations(text: str):
    patterns = [
        r"[A-Za-z][A-Za-z0-9_]*(?:\s|\()*=\s*[^.;,]{2,80}",
        r"[a-zA-Z]\s*[²^]\s*\d?\s*=\s*[^.;,]{2,80}",
        r"[a-zA-Z]\s*=\s*[^.;,]{2,80}",
        r"\b(?:v|u|a|t|s|F|m|E|p|P|V|I|R|W|Q|T)\s*=\s*[^.;,]{2,80}",
    ]
    found = []
    for p in patterns:
        for m in re.findall(p, text):
            item = clean_text(m)
            if 3 <= len(item) <= 100 and item not in found:
                found.append(item)
    # Also capture common unicode/symbol-heavy formula fragments.
    for m in re.findall(r"[A-Za-z0-9²³√πθμσΔ=+\-*/()\[\] ]{8,90}", text):
        item = clean_text(m)
        if "=" in item and len(item.split()) <= 14 and item not in found:
            found.append(item)
    return found[:18]


def build_detailed_answer(query: str, collected):
    all_text = "\n\n".join([c["text"] for c in collected if c.get("text")])
    key_sents = rank_sentences(all_text, query, max_items=28)
    equations = extract_equations(all_text)

    if not key_sents:
        return "I found search results, but I could not extract enough readable text. Try adding more specific words or use the Document Assistant for uploaded PDFs."

    q_words = keywords(query)
    title = query.strip().capitalize()
    answer = []
    answer.append(f"## Detailed answer: {title}\n")
    answer.append("### 1. Main idea\n")
    answer.append(" ".join(key_sents[:4]))

    answer.append("\n\n### 2. Important details\n")
    bullets = key_sents[4:14]
    if bullets:
        for s in bullets:
            answer.append(f"- {s}")
    else:
        answer.append("- The available sources did not provide many additional readable details.")

    if equations:
        answer.append("\n\n### 3. Applicable equations / expressions found in sources\n")
        for eq in equations[:12]:
            answer.append(f"- `{eq}`")

    answer.append("\n\n### 4. Explanation in simple words\n")
    simple = key_sents[14:21] if len(key_sents) > 14 else key_sents[:5]
    answer.append(" ".join(simple))

    answer.append("\n\n### 5. Practical use / why it matters\n")
    practical = [s for s in key_sents if any(w in s.lower() for w in ["use", "used", "application", "calculate", "determine", "measure", "design", "predict", "estimate", "engineering", "example"])]
    for s in practical[:5]:
        answer.append(f"- {s}")
    if not practical:
        answer.append("- Use the answer above as a starting point, then open the cited sources for full context and examples.")

    answer.append("\n\n### 6. What I used\n")
    domains = []
    for c in collected:
        d = domain_name(c["url"])
        if d not in domains:
            domains.append(d)
    answer.append("I combined information from: " + ", ".join(domains[:8]) + ".")

    return "\n".join(answer)


def research_web(query: str, depth: str = "Deep"):
    max_results = 8 if depth == "Fast" else 14
    page_limit = 5 if depth == "Fast" else 9
    queries = [query]
    if depth == "Deep":
        queries += [
            f"{query} explanation examples equations",
            f"{query} filetype:pdf report notes",
            f"{query} site:.edu OR site:.gov",
        ]

    seen_urls = set()
    results = []
    for q in queries:
        for r in ddg_text_search(q, max_results=max_results):
            if r["url"] not in seen_urls:
                results.append(r)
                seen_urls.add(r["url"])
        time.sleep(0.2)

    collected = []
    progress = st.progress(0, text="Reading internet sources...")
    for i, r in enumerate(results[:page_limit]):
        progress.progress((i + 1) / max(page_limit, 1), text=f"Reading: {domain_name(r['url'])}")
        text = extract_html_text(r["url"])
        combined = clean_text((r.get("snippet", "") + " " + text).strip())
        if len(combined) > 250:
            item = dict(r)
            item["text"] = combined
            collected.append(item)
    progress.empty()

    if len(collected) < 2:
        wiki = wikipedia_source(query)
        if wiki:
            collected.append(wiki)

    images = ddg_image_search(query + " diagram figure", max_results=6)
    answer = build_detailed_answer(query, collected) if collected else "I could not find enough readable internet content. Try a more specific question."
    return answer, collected, images


def extract_pdf_text(uploaded_file):
    reader = PdfReader(uploaded_file)
    pages = []
    for page in reader.pages[:80]:
        pages.append(page.extract_text() or "")
    return "\n".join(pages)


def extract_docx_text(uploaded_file):
    doc = Document(uploaded_file)
    return "\n".join([p.text for p in doc.paragraphs])


def extract_txt_text(uploaded_file):
    return uploaded_file.read().decode("utf-8", errors="ignore")


def document_answer(text: str, question: str):
    ranked = rank_sentences(text, question or "summary", max_items=30)
    eqs = extract_equations(text)
    out = ["## Document answer"]
    if question:
        out.append(f"**Question/focus:** {question}")
    out.append("### Key points")
    for s in ranked[:12]:
        out.append(f"- {s}")
    if eqs:
        out.append("\n### Equations / expressions found")
        for e in eqs[:12]:
            out.append(f"- `{e}`")
    out.append("\n### Longer extracted summary")
    out.append(" ".join(ranked[12:24] if len(ranked) > 12 else ranked[:8]))
    return "\n".join(out)


def solve_math(expr):
    try:
        x = sp.symbols("x")
        if "=" in expr:
            left, right = expr.split("=", 1)
            equation = sp.sympify(left) - sp.sympify(right)
            sol = sp.solve(equation, x)
            return f"### Solution\n\nEquation: `{expr}`\n\nSolution for x: `{sol}`\n\nSimplified form: `{sp.factor(equation)}`"
        result = sp.sympify(expr)
        return f"### Result\n\n`{sp.simplify(result)}`"
    except Exception as e:
        return f"Could not solve that expression. Error: {e}"


if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "Ask me a question. I can research the internet, online PDFs, figures, and documents, then write a detailed sourced answer."}
    ]

with st.sidebar:
    st.header("Assistant modes")
    mode = st.radio(
        "Choose mode",
        ["Internet Research Chat", "Document Assistant", "CSV Analyzer", "Math Solver"],
        index=0,
    )
    st.divider()
    depth = st.radio("Research depth", ["Fast", "Deep"], index=1)
    st.caption("No API key version. It uses web search, public pages, PDFs, Wikipedia fallback, and local analysis. It is powerful, but not a true LLM like ChatGPT.")

if mode == "Internet Research Chat":
    st.subheader("Internet Research Chat")
    st.info("Ask anything. For best results, ask specific questions such as: 'write equations of motion with explanation and diagram' or 'explain mat foundation design with equations and sources'.")

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    question = st.chat_input("Ask a detailed question...")
    if question:
        st.session_state.messages.append({"role": "user", "content": question})
        with st.chat_message("user"):
            st.markdown(question)

        with st.chat_message("assistant"):
            with st.spinner("Searching web, reports, PDFs, and figures..."):
                answer, sources, images = research_web(question, depth=depth)
            st.markdown(f'<div class="answer-card">{answer}</div>', unsafe_allow_html=True)

            if images:
                st.markdown("### Figures / images found online")
                cols = st.columns(min(3, len(images)))
                for idx, img in enumerate(images[:6]):
                    with cols[idx % len(cols)]:
                        st.image(img["image"], caption=img["title"], use_container_width=True)
                        if img.get("source"):
                            st.markdown(f"[Source]({img['source']})")

            if sources:
                st.markdown("### Sources read")
                for i, src in enumerate(sources[:10], start=1):
                    st.markdown(
                        f'<div class="source-card"><b>{i}. {src["title"]}</b> <span class="tag">{src.get("kind", "web")}</span><br>'
                        f'<a href="{src["url"]}" target="_blank">{src["url"]}</a><br>'
                        f'<span class="small-muted">{src.get("snippet", "")}</span></div>',
                        unsafe_allow_html=True,
                    )

            saved = answer + "\n\nSources:\n" + "\n".join([f"- {s['title']}: {s['url']}" for s in sources[:10]])
            st.session_state.messages.append({"role": "assistant", "content": saved})

elif mode == "Document Assistant":
    st.subheader("Document Assistant")
    uploaded = st.file_uploader("Upload PDF, DOCX, or TXT", type=["pdf", "docx", "txt"])
    question = st.text_input("Ask a question about the document or leave blank for summary")
    if uploaded:
        if uploaded.name.lower().endswith(".pdf"):
            text = extract_pdf_text(uploaded)
        elif uploaded.name.lower().endswith(".docx"):
            text = extract_docx_text(uploaded)
        else:
            text = extract_txt_text(uploaded)
        st.success(f"Extracted about {len(text):,} characters.")
        if st.button("Analyze document"):
            st.markdown(document_answer(text, question))

elif mode == "CSV Analyzer":
    st.subheader("CSV Analyzer")
    uploaded = st.file_uploader("Upload CSV", type=["csv"])
    if uploaded:
        df = pd.read_csv(uploaded)
        st.dataframe(df, use_container_width=True)
        c1, c2, c3 = st.columns(3)
        c1.metric("Rows", f"{df.shape[0]:,}")
        c2.metric("Columns", f"{df.shape[1]:,}")
        c3.metric("Missing cells", f"{int(df.isna().sum().sum()):,}")
        st.markdown("### Statistical summary")
        st.write(df.describe(include="all"))
        numeric = df.select_dtypes(include=[np.number]).columns.tolist()
        if numeric:
            col = st.selectbox("Chart numeric column", numeric)
            st.bar_chart(df[col])

elif mode == "Math Solver":
    st.subheader("Math Solver")
    expr = st.text_input("Enter expression or equation, for example: x**2 - 5*x + 6 = 0")
    if st.button("Solve") and expr:
        st.markdown(solve_math(expr))
