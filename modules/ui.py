import streamlit as st

CSS = """
<style>
.main-title{font-size:2.45rem;font-weight:900;margin-bottom:.1rem;}
.subtitle{color:#5f6368;font-size:1.05rem;margin-bottom:1.2rem;}
.answer-card{background:#fff;border:1px solid #e8eaed;border-radius:18px;padding:1.15rem;box-shadow:0 4px 20px rgba(0,0,0,.045);line-height:1.65;}
.source-card{background:#f8fafd;border:1px solid #e4e8ef;border-radius:14px;padding:.85rem;margin:.55rem 0;}
.result-card{background:#fff;border:1px solid #eceff3;border-radius:16px;padding:1rem;margin:.65rem 0;}
.badge{display:inline-block;background:#eef3ff;border:1px solid #d8e3ff;border-radius:999px;padding:.15rem .55rem;font-size:.78rem;margin-right:.25rem;}
.small-muted{color:#70757a;font-size:.88rem;}
</style>
"""


def setup_page():
    st.set_page_config(page_title="Ultimate Research AI Assistant", page_icon="🌐", layout="wide")
    st.markdown(CSS, unsafe_allow_html=True)
    st.markdown('<div class="main-title">🌐 Ultimate Research AI Assistant</div>', unsafe_allow_html=True)
    st.markdown('<div class="subtitle">No API key required. Searches the internet, reads pages and PDFs, extracts equations, shows figures, and analyzes files.</div>', unsafe_allow_html=True)


def source_card(src, i=1):
    title = src.get("title", "Untitled")
    url = src.get("url", "")
    snippet = src.get("snippet", "")
    score = src.get("score", 0)
    typ = src.get("type", "web")
    st.markdown(f"""
    <div class='source-card'>
    <b>{i}. {title}</b><br>
    <span class='badge'>{typ}</span><span class='badge'>score {score:.1f}</span><br>
    <a href='{url}' target='_blank'>{url}</a><br>
    <span class='small-muted'>{snippet}</span>
    </div>
    """, unsafe_allow_html=True)
