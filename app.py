import re
import io
import html
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

st.set_page_config(page_title="Research Search Engine AI", page_icon="🔎", layout="wide")

CUSTOM_CSS = """
<style>
.main-title {font-size: 2.3rem; font-weight: 850; margin-bottom: 0.2rem;}
.subtitle {color: #5f6368; font-size: 1rem; margin-bottom: 1.2rem;}
.card {background: #ffffff; border: 1px solid #e7e9ee; border-radius: 18px; padding: 1.1rem; box-shadow: 0 2px 14px rgba(0,0,0,0.04); margin-bottom: 0.8rem;}
.result-title {font-size: 1.08rem; font-weight: 750; margin-bottom: 0.25rem;}
.url {font-size: 0.82rem; color: #188038; word-break: break-all;}
.snippet {font-size: 0.95rem; color: #3c4043; margin-top: 0.4rem;}
.badge {display: inline-block; border: 1px solid #dfe3ea; background: #f8fafd; color: #3c4043; padding: 0.15rem 0.45rem; border-radius: 999px; font-size: 0.75rem; margin-right: 0.25rem;}
.answer-card {background: #fbfcff; border: 1px solid #dde5f5; border-radius: 18px; padding: 1.2rem; box-shadow: 0 2px 14px rgba(0,0,0,0.04);}
.small-muted {color: #747775; font-size: 0.85rem;}
hr {margin-top: 1rem; margin-bottom: 1rem;}
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

st.markdown('<div class="main-title">🔎 Research Search Engine AI</div>', unsafe_allow_html=True)
st.markdown('<div class="subtitle">Search the internet, read pages/PDFs, view figures, and generate detailed research-style answers. No API key required.</div>', unsafe_allow_html=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"
}

STOPWORDS = set("""
a an and are as at be by for from has have he in is it its of on or that the to was were will with you your i we they them this those these can could should would about into over under than then there their if but not no yes do does did done using use used more most many much such also other some any all each when where what why how who whom whose which write give explain define equation equations motion law formula formulas method methods calculate calculation available
""".split())

GEOTECH_HINTS = [
    "earth pressure", "retaining wall", "active pressure", "passive pressure", "at-rest pressure",
    "rankine", "coulomb", "lateral earth pressure", "soil mechanics", "geotechnical",
    "surcharge", "cohesion", "friction angle", "ka", "kp", "k0"
]

BAD_DOMAINS = ["pinterest.", "facebook.", "instagram.", "tiktok.", "x.com", "twitter.com"]


def clean_text(text: str) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    return text


def split_sentences(text: str):
    text = clean_text(text)
    parts = re.split(r"(?<=[.!?])\s+", text)
    return [p.strip() for p in parts if len(p.strip()) > 35]


def keywords(query: str):
    words = re.findall(r"[a-zA-Z][a-zA-Z0-9-]{2,}", query.lower())
    return [w for w in words if w not in STOPWORDS]


def is_probably_pdf_url(url: str) -> bool:
    return url.lower().split("?")[0].endswith(".pdf")


def domain_of(url: str) -> str:
    try:
        return urlparse(url).netloc.replace("www.", "")
    except Exception:
        return ""


def source_type(url: str) -> str:
    if is_probably_pdf_url(url):
        return "PDF"
    d = domain_of(url)
    if "wikipedia.org" in d:
        return "Wikipedia"
    if ".edu" in d:
        return "University"
    if ".gov" in d:
        return "Government"
    return "Webpage"


def expand_query(query: str):
    q = query.strip()
    variants = [q]
    lower = q.lower()
    if "earth pressure" in lower or ("earth" in lower and "pressure" in lower):
        variants += [
            "earth pressure calculation methods retaining wall Rankine Coulomb at rest active passive",
            "lateral earth pressure methods Rankine Coulomb equivalent fluid pressure pdf",
            "site:edu earth pressure retaining wall Rankine Coulomb PDF",
            "site:gov lateral earth pressure design retaining walls pdf",
        ]
    else:
        variants += [
            f"{q} explanation formulas examples",
            f"{q} PDF report guide",
            f"site:edu {q}",
        ]
    seen = []
    for v in variants:
        if v not in seen:
            seen.append(v)
    return seen[:5]


def relevance_score(query: str, title: str, snippet: str, text: str = "") -> float:
    q_words = keywords(query)
    combined = f"{title} {snippet} {text[:2500]}".lower()
    score = 0.0
    for w in q_words:
        if w in combined:
            score += 3.0
    phrase = query.lower().strip()
    if phrase and phrase in combined:
        score += 10.0
    if "earth" in query.lower() and "pressure" in query.lower():
        score += sum(2.5 for h in GEOTECH_HINTS if h in combined)
        if any(bad in combined for bad in ["moon", "astronomy", "lunar", "planet", "satellite"]):
            score -= 20
    if source_type(title + snippet) == "PDF":
        score += 1
    return score


def ddg_web_search(query: str, max_results: int = 10):
    results = []
    try:
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=max_results):
                title = clean_text(r.get("title") or "Untitled")
                url = r.get("href") or r.get("url") or ""
                snippet = clean_text(r.get("body") or "")
                if not url:
                    continue
                if any(b in url.lower() for b in BAD_DOMAINS):
                    continue
                results.append({"title": title, "url": url, "snippet": snippet, "type": source_type(url)})
    except Exception as e:
        st.warning(f"Search issue: {e}")
    return results


def ddg_image_search(query: str, max_results: int = 8):
    images = []
    try:
        with DDGS() as ddgs:
            for r in ddgs.images(query, max_results=max_results):
                img = r.get("image") or r.get("thumbnail")
                title = clean_text(r.get("title") or "Figure")
                source = r.get("url") or r.get("source") or ""
                if img:
                    images.append({"title": title, "image": img, "source": source})
    except Exception:
        pass
    return images


def fetch_webpage_text(url: str, timeout: int = 10):
    try:
        response = requests.get(url, headers=HEADERS, timeout=timeout)
        if response.status_code >= 400:
            return ""
        ctype = response.headers.get("content-type", "").lower()
        if "pdf" in ctype or is_probably_pdf_url(url):
            return extract_pdf_from_bytes(response.content)
        soup = BeautifulSoup(response.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header", "aside", "form"]):
            tag.decompose()
        parts = []
        for tag in soup.find_all(["h1", "h2", "h3", "p", "li", "table"]):
            txt = clean_text(tag.get_text(" "))
            if len(txt) > 35:
                parts.append(txt)
        return clean_text(" ".join(parts))[:30000]
    except Exception:
        return ""


def extract_pdf_from_bytes(content: bytes):
    try:
        reader = PdfReader(io.BytesIO(content))
        pages = []
        for page in reader.pages[:12]:
            pages.append(page.extract_text() or "")
        return clean_text("\n".join(pages))[:30000]
    except Exception:
        return ""


def wikipedia_fallback(query: str):
    try:
        hits = wikipedia.search(query, results=5)
        for hit in hits:
            if "earth" in query.lower() and "pressure" in query.lower() and "moon" in hit.lower():
                continue
            page = wikipedia.page(hit, auto_suggest=False)
            text = page.content[:15000]
            if relevance_score(query, page.title, "", text) > 8:
                return {"title": page.title, "url": page.url, "snippet": "Wikipedia background source", "type": "Wikipedia", "text": text}
    except Exception:
        return None
    return None


def search_engine(query: str, max_sources: int = 8):
    all_results = []
    seen_urls = set()
    for q in expand_query(query):
        for result in ddg_web_search(q, max_results=8):
            url = result["url"]
            if url in seen_urls:
                continue
            seen_urls.add(url)
            result["score"] = relevance_score(query, result["title"], result["snippet"])
            all_results.append(result)
    all_results.sort(key=lambda r: r.get("score", 0), reverse=True)
    return all_results[:max_sources]


def read_and_rank_sources(query: str, search_results):
    enriched = []
    for result in search_results:
        text = fetch_webpage_text(result["url"])
        score = relevance_score(query, result["title"], result["snippet"], text)
        if score >= 3 and len(text) > 200:
            item = dict(result)
            item["text"] = text
            item["score"] = score
            enriched.append(item)
    enriched.sort(key=lambda r: r.get("score", 0), reverse=True)
    if len(enriched) < 2:
        wiki = wikipedia_fallback(query)
        if wiki:
            enriched.append(wiki)
    return enriched


def sentence_score(sentence: str, query_words):
    s = sentence.lower()
    score = 0
    for w in query_words:
        if w in s:
            score += 2.5
    score += min(len(sentence) / 220, 2)
    if any(x in s for x in ["method", "formula", "equation", "pressure", "coefficient", "defined", "states", "used", "therefore", "because", "design", "calculate"]):
        score += 1.5
    return score


def extract_equations(text: str):
    equations = []
    patterns = [
        r"[A-Za-z][A-Za-z0-9_]*\s*=\s*[^.;,\n]{2,80}",
        r"[Kk][aApP0]?\s*=\s*[^.;,\n]{2,80}",
        r"[Ppσγ][A-Za-z0-9_]*\s*=\s*[^.;,\n]{2,80}",
        r"tan\^?2?\s*\(?\s*45[^.;,\n]{0,80}",
        r"sin\s*\(?[^.;,\n]{2,80}",
    ]
    for pat in patterns:
        for m in re.findall(pat, text):
            eq = clean_text(m)
            if 4 <= len(eq) <= 120 and eq not in equations:
                equations.append(eq)
    return equations[:12]


def make_detailed_answer(query: str, sources):
    if not sources:
        return "I could not find enough relevant web content. Try adding more specific words such as the subject, standard, method, or application."

    combined = "\n\n".join([s.get("text", "") for s in sources[:6]])
    sentences = split_sentences(combined)
    q_words = keywords(query)
    ranked = sorted(sentences, key=lambda s: sentence_score(s, q_words), reverse=True)
    chosen = []
    for s in ranked:
        if s not in chosen and len(chosen) < 18:
            chosen.append(s)
    chosen = sorted(chosen, key=lambda s: sentences.index(s) if s in sentences else 999999)

    equations = extract_equations(combined)

    main = chosen[:5]
    details = chosen[5:13]
    practical = chosen[13:18]

    answer = []
    answer.append(f"## Detailed answer: {query}\n")
    answer.append("### 1. Main idea")
    answer.append("\n".join([f"- {s}" for s in main]) if main else "- I found relevant sources, but the readable text was limited.")
    answer.append("\n### 2. Important details")
    answer.append("\n".join([f"- {s}" for s in details]) if details else "- Not enough additional readable detail was found.")
    if equations:
        answer.append("\n### 3. Applicable equations / expressions found in sources")
        answer.append("\n".join([f"- `{e}`" for e in equations]))
    answer.append("\n### 4. Simple explanation")
    simple = summarize_simple(query, main + details)
    answer.append(simple)
    answer.append("\n### 5. Practical use / why it matters")
    answer.append("\n".join([f"- {s}" for s in practical]) if practical else "- This information helps compare methods, choose correct assumptions, and support engineering/design decisions.")
    answer.append("\n### 6. Sources used")
    answer.append("\n".join([f"- {domain_of(s['url'])}: {s['title']}" for s in sources[:6]]))
    return "\n".join(answer)


def summarize_simple(query, sentences):
    if "earth" in query.lower() and "pressure" in query.lower():
        return "Earth pressure means the lateral force that soil applies to a retaining wall, basement wall, sheet pile, or similar structure. Different methods are used depending on wall movement, soil strength, wall friction, groundwater, surcharge loads, and whether the condition is active, passive, or at-rest."
    if sentences:
        return " ".join(sentences[:2])
    return "In simple words, the answer depends on the relevant definitions, formulas, and applications found in the selected sources."


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


def basic_document_summary(text):
    sentences = split_sentences(text)
    if not sentences:
        return "No readable text found."
    words = [w.lower() for w in re.findall(r"[a-zA-Z]{4,}", text) if w.lower() not in STOPWORDS]
    common = Counter(words).most_common(15)
    top_words = [w for w, _ in common]
    ranked = sorted(sentences, key=lambda s: sentence_score(s, top_words), reverse=True)[:10]
    ranked = sorted(ranked, key=lambda s: sentences.index(s))
    return "\n\n".join(ranked)


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
        {"role": "assistant", "content": "Hi! Ask me anything. I can search the web, read pages/PDFs, show figures, and give sources."}
    ]

with st.sidebar:
    st.header("Tools")
    mode = st.radio(
        "Choose mode",
        ["AI Research Chat", "Search Engine", "Document Assistant", "CSV Analyzer", "Math Solver"],
        index=0,
    )
    st.caption("No API key required. Uses public search results, webpages, PDFs, and local tools.")
    max_sources = st.slider("Sources to read", 3, 10, 6)

if mode == "AI Research Chat":
    st.subheader("Ask a question")
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    question = st.chat_input("Ask anything...")
    if question:
        st.session_state.messages.append({"role": "user", "content": question})
        with st.chat_message("user"):
            st.markdown(question)

        with st.chat_message("assistant"):
            with st.spinner("Searching, reading webpages/PDFs, and preparing a detailed answer..."):
                results = search_engine(question, max_sources=max_sources)
                sources = read_and_rank_sources(question, results)
                answer = make_detailed_answer(question, sources)
                images = ddg_image_search(question + " diagram figure", max_results=6)
            st.markdown(f'<div class="answer-card">{html.escape(answer).replace(chr(10), "<br>")}</div>', unsafe_allow_html=True)

            if images:
                st.markdown("### Figures / images found online")
                cols = st.columns(3)
                for i, img in enumerate(images[:6]):
                    with cols[i % 3]:
                        st.image(img["image"], caption=img["title"], use_container_width=True)
                        if img.get("source"):
                            st.markdown(f"[Source]({img['source']})")

            if sources:
                st.markdown("### Sources read")
                for i, src in enumerate(sources[:8], start=1):
                    st.markdown(
                        f'<div class="card"><div class="result-title">{i}. {html.escape(src["title"])}</div>'
                        f'<span class="badge">{src.get("type", source_type(src["url"]))}</span>'
                        f'<span class="badge">score {src.get("score", 0):.1f}</span>'
                        f'<div class="url"><a href="{src["url"]}" target="_blank">{src["url"]}</a></div>'
                        f'<div class="snippet">{html.escape(src.get("snippet", "")[:350])}</div></div>',
                        unsafe_allow_html=True,
                    )

            saved = answer + "\n\nSources:\n" + "\n".join([f"- {s['title']}: {s['url']}" for s in sources[:8]])
            st.session_state.messages.append({"role": "assistant", "content": saved})

elif mode == "Search Engine":
    st.subheader("Search Engine")
    query = st.text_input("Search the web", placeholder="example: earth pressure calculation methods retaining walls")
    col1, col2, col3 = st.columns(3)
    with col1:
        web_on = st.checkbox("Webpages", value=True)
    with col2:
        pdf_on = st.checkbox("PDFs / reports", value=True)
    with col3:
        image_on = st.checkbox("Images / figures", value=True)

    if st.button("Search", type="primary") and query:
        with st.spinner("Searching..."):
            results = search_engine(query, max_sources=12)
            if not web_on:
                results = [r for r in results if r.get("type") != "Webpage"]
            if not pdf_on:
                results = [r for r in results if r.get("type") != "PDF"]
            images = ddg_image_search(query + " diagram figure", max_results=9) if image_on else []

        st.markdown("### Results")
        if not results:
            st.warning("No relevant results found. Try a more specific query.")
        for i, r in enumerate(results, start=1):
            with st.expander(f"{i}. {r['title']}  —  {r.get('type', 'Webpage')}", expanded=i <= 3):
                st.markdown(f"**URL:** [{r['url']}]({r['url']})")
                st.markdown(f"**Snippet:** {r.get('snippet','')}")
                st.markdown(f"**Initial relevance score:** {r.get('score', 0):.1f}")
                if st.button(f"Read and summarize source {i}", key=f"read_{i}"):
                    with st.spinner("Reading source..."):
                        text = fetch_webpage_text(r["url"])
                    if text:
                        st.markdown("#### Source summary")
                        st.markdown(make_detailed_answer(query, [{**r, "text": text, "score": relevance_score(query, r['title'], r.get('snippet',''), text)}]))
                    else:
                        st.warning("Could not read this source. It may block automated reading or require JavaScript.")

        if images:
            st.markdown("### Image / figure results")
            cols = st.columns(3)
            for i, img in enumerate(images[:9]):
                with cols[i % 3]:
                    st.image(img["image"], caption=img["title"], use_container_width=True)
                    if img.get("source"):
                        st.markdown(f"[Source]({img['source']})")

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
        if st.button("Summarize document"):
            st.markdown(basic_document_summary(text))

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
