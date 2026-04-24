import os
import re
import json
import streamlit as st
from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue
from groq import Groq
from dotenv import load_dotenv
from cases import кейсы, получить_название_кейса
from fallback_answers import заготовленные_ответы

load_dotenv()

st.set_page_config(
    page_title="Навигатор цифровой химии",
    page_icon="⬢",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Geist:wght@300;400;500;600;700;800;900&family=Geist+Mono:wght@400;500;600&display=swap');

:root {
    --bg: #0a0a0a;
    --bg-soft: #111111;
    --bg-card: #141414;
    --border: #1f1f1f;
    --border-strong: #2a2a2a;
    --text: #fafafa;
    --text-muted: #a3a3a3;
    --text-dim: #525252;
}

.stApp {background: var(--bg); color: var(--text); font-family: 'Geist', -apple-system, sans-serif; font-feature-settings: "ss01","cv11";}
#MainMenu, footer, header {visibility: hidden;}
.block-container {padding: 3rem 4rem 4rem 4rem; max-width: 1440px;}
* {font-family: 'Geist', sans-serif;}
h1, h2, h3, h4 {letter-spacing: -0.04em; font-weight: 600; color: var(--text);}
code, pre, .mono {font-family: 'Geist Mono', monospace !important;}

@keyframes fadeUp {from {opacity: 0; transform: translateY(16px);} to {opacity: 1; transform: translateY(0);}}
@keyframes fadeIn {from {opacity: 0;} to {opacity: 1;}}
@keyframes slideInRight {from {transform: translateX(-4px); opacity: 0;} to {transform: translateX(0); opacity: 1;}}
@keyframes pulse {0%, 100% {opacity: 1; transform: scale(1);} 50% {opacity: 0.5; transform: scale(0.85);}}
@keyframes scroll {from {transform: translateX(0);} to {transform: translateX(-50%);}}
@keyframes scrollDown {0% {top: -50%;} 100% {top: 100%;}}
@keyframes shimmer {0% {background-position: -200% 0;} 100% {background-position: 200% 0;}}
@keyframes blink {0%, 49% {opacity: 1;} 50%, 100% {opacity: 0;}}
@keyframes float {0%, 100% {transform: translateY(0);} 50% {transform: translateY(-6px);}}

.nav {display: flex; justify-content: space-between; align-items: center; padding-bottom: 2rem; border-bottom: 1px solid var(--border); margin-bottom: 4rem; animation: fadeIn 0.5s ease-out;}
.nav-brand {display: flex; align-items: center; gap: 0.6rem; font-size: 0.95rem; font-weight: 500;}
.nav-brand .logo {width: 22px; height: 22px; background: var(--text); color: var(--bg); display: inline-flex; align-items: center; justify-content: center; font-size: 14px; font-weight: 700;}
.nav-meta {font-family: 'Geist Mono', monospace; font-size: 0.75rem; color: var(--text-dim); display: flex; gap: 2rem;}
.nav-meta span::before {content: "●"; color: #22c55e; margin-right: 0.5rem; font-size: 0.7em; display: inline-block; animation: pulse 2s ease-in-out infinite;}

.hero-block {margin: 0 0 4rem 0; position: relative;}
.hero-block::before {content: ""; position: absolute; top: -30px; right: -50px; width: 500px; height: 400px; background-image: radial-gradient(circle, var(--border-strong) 1px, transparent 1px); background-size: 22px 22px; opacity: 0.6; z-index: -1; pointer-events: none; -webkit-mask-image: radial-gradient(ellipse at right, black 0%, transparent 70%); mask-image: radial-gradient(ellipse at right, black 0%, transparent 70%);}
.hero-kicker {font-family: 'Geist Mono', monospace; font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.25em; color: var(--text-dim); margin-bottom: 1.5rem; opacity: 0; animation: fadeUp 0.6s cubic-bezier(0.16, 1, 0.3, 1) 0.05s forwards;}
.hero-title {font-size: 4.5rem; font-weight: 600; letter-spacing: -0.055em; line-height: 0.95; margin: 0 0 1.5rem 0; color: var(--text); opacity: 0; animation: fadeUp 0.8s cubic-bezier(0.16, 1, 0.3, 1) 0.1s forwards;}
.hero-title .accent {color: var(--text-dim);}
.hero-title .cursor {display: inline-block; width: 4px; height: 0.9em; background: var(--text); margin-left: 4px; vertical-align: middle; animation: blink 1s step-start infinite;}
.hero-desc {font-size: 1.1rem; color: var(--text-muted); max-width: 640px; line-height: 1.6; opacity: 0; animation: fadeUp 0.7s cubic-bezier(0.16, 1, 0.3, 1) 0.25s forwards;}

.stats-grid {display: grid; grid-template-columns: repeat(4, 1fr); gap: 3rem; margin: 5rem 0 4rem 0;}
.stat-item {padding: 0; position: relative;}
.stat-label {font-family: 'Geist Mono', monospace; font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.2em; color: var(--text-dim); margin-bottom: 0.5rem; opacity: 0; animation: fadeUp 0.6s cubic-bezier(0.16, 1, 0.3, 1) forwards;}
.stat-value {font-size: 2.75rem; font-weight: 500; letter-spacing: -0.045em; color: var(--text); font-variant-numeric: tabular-nums; line-height: 1; opacity: 0; animation: fadeUp 0.7s cubic-bezier(0.16, 1, 0.3, 1) forwards;}
.stat-item:nth-child(1) .stat-label {animation-delay: 0.3s;} .stat-item:nth-child(1) .stat-value {animation-delay: 0.35s;}
.stat-item:nth-child(2) .stat-label {animation-delay: 0.4s;} .stat-item:nth-child(2) .stat-value {animation-delay: 0.45s;}
.stat-item:nth-child(3) .stat-label {animation-delay: 0.5s;} .stat-item:nth-child(3) .stat-value {animation-delay: 0.55s;}
.stat-item:nth-child(4) .stat-label {animation-delay: 0.6s;} .stat-item:nth-child(4) .stat-value {animation-delay: 0.65s;}

.marquee {position: relative; overflow: hidden; padding: 1.5rem 0; margin: 5rem 0 3rem 0; border-top: 1px solid var(--border); border-bottom: 1px solid var(--border); -webkit-mask-image: linear-gradient(90deg, transparent, black 12%, black 88%, transparent); mask-image: linear-gradient(90deg, transparent, black 12%, black 88%, transparent); opacity: 0; animation: fadeIn 1s ease-out 0.7s forwards;}
.marquee-track {display: flex; gap: 4rem; animation: scroll 60s linear infinite; white-space: nowrap; width: max-content;}
.marquee:hover .marquee-track {animation-play-state: paused;}
.marquee-item {font-family: 'Geist Mono', monospace; font-size: 0.9rem; color: var(--text-dim); text-transform: uppercase; letter-spacing: 0.18em; display: flex; align-items: center;}
.marquee-item::before {content: "◆"; color: var(--text-muted); margin-right: 1rem; font-size: 0.55em;}

.scroll-hint {display: flex; flex-direction: column; align-items: center; gap: 1rem; margin: 4rem 0 5rem 0; opacity: 0; animation: fadeUp 0.8s cubic-bezier(0.16, 1, 0.3, 1) 1s forwards;}
.scroll-hint-label {font-family: 'Geist Mono', monospace; font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.3em; color: var(--text-dim);}
.scroll-hint-line {width: 1px; height: 48px; background: var(--border-strong); position: relative; overflow: hidden;}
.scroll-hint-line::after {content: ""; position: absolute; top: -50%; left: 0; width: 100%; height: 60%; background: linear-gradient(to bottom, transparent, var(--text)); animation: scrollDown 2.2s ease-in-out infinite;}

.stTabs [data-baseweb="tab-list"] {gap: 0; background: transparent; border-bottom: 1px solid var(--border); padding: 0; border-radius: 0;}
.stTabs [data-baseweb="tab"] {background: transparent; border: none; border-radius: 0; color: var(--text-dim); font-weight: 400; font-size: 0.9rem; padding: 1rem 1.5rem 1rem 0; margin-right: 2rem; position: relative; transition: color 0.25s ease;}
.stTabs [data-baseweb="tab"]:hover {color: var(--text-muted);}
.stTabs [aria-selected="true"] {color: var(--text) !important; background: transparent !important;}
.stTabs [aria-selected="true"]::after {content: ""; position: absolute; bottom: -1px; left: 0; right: 1.5rem; height: 1px; background: var(--text); animation: slideInRight 0.3s cubic-bezier(0.16, 1, 0.3, 1);}
.stTabs [data-baseweb="tab-panel"] {padding-top: 3rem; animation: fadeUp 0.5s cubic-bezier(0.16, 1, 0.3, 1);}

.stTextArea textarea {background: var(--bg-soft) !important; border: 1px solid var(--border-strong) !important; border-radius: 12px !important; color: var(--text) !important; font-size: 1.15rem !important; font-family: 'Geist', sans-serif !important; padding: 1.5rem !important; line-height: 1.5 !important; transition: all 0.25s cubic-bezier(0.16, 1, 0.3, 1);}
.stTextArea textarea:focus {border-color: var(--text) !important; box-shadow: 0 0 0 4px rgba(250,250,250,0.05) !important; outline: none !important;}
.stTextArea textarea::placeholder {color: var(--text-dim);}

.stSelectbox > div > div {background: var(--bg-soft) !important; border: 1px solid var(--border-strong) !important; border-radius: 8px !important; color: var(--text) !important; transition: border-color 0.2s;}
.stSelectbox > div > div:hover {border-color: var(--text-muted) !important;}
.stSelectbox label, .stSlider label {color: var(--text-muted) !important; font-size: 0.75rem !important; font-family: 'Geist Mono', monospace !important; text-transform: uppercase; letter-spacing: 0.15em !important;}

.stSlider {padding: 0.6rem 0 0 0;}
.stSlider > div {padding-top: 0 !important; padding-bottom: 0 !important;}
.stSlider div[style*="height: 0.25rem"], .stSlider div[style*="height:0.25rem"] {height: 3px !important; border-radius: 2px !important; background: var(--border-strong) !important; position: relative; overflow: hidden;}
.stSlider div[role="slider"] {background: var(--text) !important; border: 3px solid var(--bg) !important; width: 20px !important; height: 20px !important; border-radius: 50% !important; box-shadow: 0 0 0 1px var(--border-strong), 0 4px 12px rgba(0, 0, 0, 0.4) !important; transition: all 0.25s cubic-bezier(0.16, 1, 0.3, 1) !important; cursor: grab !important;}
.stSlider div[role="slider"]:hover {box-shadow: 0 0 0 1px var(--text), 0 0 0 6px rgba(250, 250, 250, 0.08), 0 6px 18px rgba(0, 0, 0, 0.5) !important; transform: translate(0, -5px) scale(1.08) !important;}
.stSlider div[role="slider"]:active, .stSlider div[role="slider"]:focus {cursor: grabbing !important; outline: none !important; box-shadow: 0 0 0 1px var(--text), 0 0 0 8px rgba(250, 250, 250, 0.12), 0 8px 22px rgba(0, 0, 0, 0.5) !important;}
.stSlider [data-testid="stSliderThumbValue"] {background: var(--text) !important; color: var(--bg) !important; font-family: 'Geist Mono', monospace !important; font-weight: 600 !important; border-radius: 6px !important; padding: 3px 9px !important; font-size: 0.76rem !important; top: -34px !important; letter-spacing: 0.02em !important; box-shadow: 0 6px 18px rgba(0, 0, 0, 0.35) !important; white-space: nowrap !important;}
.stSlider [data-testid="stSliderThumbValue"]::after {content: ""; position: absolute; bottom: -4px; left: 50%; transform: translateX(-50%); width: 0; height: 0; border-left: 4px solid transparent; border-right: 4px solid transparent; border-top: 4px solid var(--text);}
.stSlider [data-testid="stTickBar"] {padding-top: 0.4rem !important;}
.stSlider [data-testid="stTickBar"] > div[data-testid="stTickBar"] {display: none !important;}
.stSlider [data-testid="stTickBarMin"], .stSlider [data-testid="stTickBarMax"] {color: var(--text-dim) !important; font-family: 'Geist Mono', monospace !important; font-size: 0.7rem !important; letter-spacing: 0.08em !important;}

.stButton button {background: transparent; color: var(--text-muted); border: 1px solid var(--border); border-radius: 100px; font-weight: 400; font-size: 0.85rem; font-family: 'Geist', sans-serif; transition: all 0.25s cubic-bezier(0.16, 1, 0.3, 1); padding: 0.55rem 1rem;}
.stButton button:hover {background: var(--bg-soft); color: var(--text); border-color: var(--border-strong); transform: translateY(-1px);}
.stButton button[kind="primary"] {background: var(--text); color: var(--bg); border: 1px solid var(--text); border-radius: 10px; font-weight: 500; font-size: 0.92rem; padding: 0 1.6rem; height: 44px; letter-spacing: -0.01em; position: relative; overflow: hidden; transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1);}
.stButton button[kind="primary"] p {position: relative; z-index: 1; transition: transform 0.3s cubic-bezier(0.16, 1, 0.3, 1);}
.stButton button[kind="primary"]::before {content: ""; position: absolute; top: 0; left: -100%; width: 100%; height: 100%; background: linear-gradient(90deg, transparent, rgba(0,0,0,0.08), transparent); transition: left 0.6s;}
.stButton button[kind="primary"]:hover {background: var(--text); border-color: var(--text); color: var(--bg); transform: translateY(-1px); box-shadow: 0 10px 30px -10px rgba(250, 250, 250, 0.3);}
.stButton button[kind="primary"]:hover::before {left: 100%;}
.stButton button[kind="primary"]:hover p {transform: translateX(3px);}
.stButton button[kind="primary"]:active {transform: translateY(0);}

.answer-container {margin-top: 3rem; padding-top: 2rem; border-top: 1px solid var(--border);}
.answer-meta {font-family: 'Geist Mono', monospace; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.15em; color: var(--text-dim); margin-bottom: 2rem; display: flex; gap: 2rem; align-items: center;}
.answer-meta .dot {width: 6px; height: 6px; background: #22c55e; display: inline-block; border-radius: 50%; margin-right: 0.5rem; animation: pulse 2s ease-in-out infinite;}
.answer-body {font-size: 1.05rem; line-height: 1.7; color: var(--text); max-width: 900px;}

.source-row {display: flex; gap: 1.5rem; padding: 1rem 0; border-bottom: 1px solid var(--border); font-family: 'Geist Mono', monospace; font-size: 0.85rem; transition: padding-left 0.2s ease; align-items: baseline;}
.source-row:hover {padding-left: 0.5rem;}
.source-row .num {color: var(--text-dim); min-width: 2rem;}
.source-row .doc {color: var(--text); flex: 1; word-break: break-word;}
.source-row .pages {color: var(--text-dim); white-space: nowrap;}

.streamlit-expanderHeader, [data-testid="stExpander"] summary {background: var(--bg-soft) !important; border: 1px solid var(--border) !important; border-radius: 8px !important; color: var(--text-muted) !important; font-weight: 400 !important; transition: all 0.2s;}
.streamlit-expanderHeader:hover, [data-testid="stExpander"] summary:hover {color: var(--text) !important; border-color: var(--border-strong) !important;}
.streamlit-expanderHeader p, [data-testid="stExpander"] summary p {font-family: 'Geist Mono', monospace !important; font-size: 0.85rem !important;}
.streamlit-expanderContent, [data-testid="stExpander"] [data-testid="stExpanderDetails"] {border: 1px solid var(--border) !important; border-top: none !important; background: var(--bg-soft) !important; border-radius: 0 0 8px 8px !important; padding: 1.5rem !important;}

.stToggle label {color: var(--text-muted) !important; font-size: 0.85rem !important;}
code {background: var(--bg-soft) !important; color: var(--text) !important; padding: 0.15rem 0.4rem !important; border-radius: 4px !important; font-size: 0.88em !important; border: 1px solid var(--border);}
pre {background: var(--bg-soft) !important; border: 1px solid var(--border) !important; border-radius: 8px !important; padding: 1.5rem !important;}
pre code {background: transparent !important; border: none !important; padding: 0 !important; color: var(--text) !important; font-size: 0.85rem !important; line-height: 1.6 !important;}
label, .stMarkdown p, .stMarkdown li {color: var(--text-muted); line-height: 1.7;}
.stMarkdown strong {color: var(--text);}
hr {border-color: var(--border) !important; margin: 2.5rem 0 !important;}
div[data-testid="stAlert"] {background: var(--bg-soft) !important; border: 1px solid var(--border) !important; border-radius: 8px !important; color: var(--text-muted) !important;}

details.case-details {border-bottom: 1px solid var(--border); transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1);}
details.case-details summary {list-style: none; cursor: pointer; display: grid; grid-template-columns: 60px 1fr 40px; padding: 1.75rem 0; align-items: start; gap: 1rem; transition: all 0.25s cubic-bezier(0.16, 1, 0.3, 1);}
details.case-details summary::-webkit-details-marker {display: none;}
details.case-details summary::marker {display: none;}
details.case-details summary:hover {padding-left: 0.75rem;}
details.case-details summary:hover .case-title {color: var(--text);}
details.case-details summary:hover .case-toggle {color: var(--text);}
.case-num {font-family: 'Geist Mono', monospace; font-size: 0.8rem; color: var(--text-dim); letter-spacing: 0.05em; padding-top: 0.3rem; transition: color 0.2s;}
.case-title {font-size: 1.15rem; font-weight: 500; letter-spacing: -0.02em; margin: 0 0 0.4rem 0; color: var(--text); transition: color 0.2s;}
.case-desc {color: var(--text-muted); font-size: 0.95rem; line-height: 1.65; margin: 0;}
.case-toggle {font-family: 'Geist', sans-serif; color: var(--text-dim); font-size: 1.6rem; text-align: right; padding-top: 0; line-height: 1; transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1); transform-origin: center; font-weight: 300;}
details[open] .case-toggle {transform: rotate(45deg); color: var(--text);}
.case-expanded {padding: 0.5rem 0 2rem 60px; animation: fadeUp 0.35s cubic-bezier(0.16, 1, 0.3, 1);}
.case-exp-label {font-family: 'Geist Mono', monospace; font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.2em; color: var(--text-dim); margin: 1.25rem 0 0.75rem 0;}
.case-exp-label:first-child {margin-top: 0;}
.case-exp-list {list-style: none; padding: 0; margin: 0;}
.case-exp-list li {color: var(--text-muted); font-size: 0.95rem; padding: 0.5rem 0; border-bottom: 1px dashed var(--border); display: flex; gap: 0.75rem;}
.case-exp-list li:last-child {border-bottom: none;}
.case-exp-list li::before {content: "→"; color: var(--text-dim); flex-shrink: 0;}
.case-exp-quote {background: var(--bg-soft); border-left: 2px solid var(--text); padding: 1rem 1.25rem; color: var(--text); font-size: 0.95rem; margin-top: 0.5rem; font-style: italic;}

.tech-row {display: grid; grid-template-columns: 200px 1fr; padding: 1.25rem 0; border-bottom: 1px solid var(--border); font-size: 0.95rem; transition: padding-left 0.2s ease;}
.tech-row:hover {padding-left: 0.5rem;}
.tech-key {font-family: 'Geist Mono', monospace; font-size: 0.8rem; color: var(--text-dim); text-transform: uppercase; letter-spacing: 0.1em;}
.tech-val {color: var(--text); font-weight: 400;}
.tech-val .hint {color: var(--text-muted); font-size: 0.85rem; margin-left: 0.75rem;}

.pipeline-step {display: grid; grid-template-columns: 50px 160px 1fr; padding: 1.1rem 0; border-bottom: 1px solid var(--border); font-family: 'Geist Mono', monospace; font-size: 0.9rem; align-items: baseline; transition: padding-left 0.2s ease;}
.pipeline-step:hover {padding-left: 0.5rem;}
.pipeline-num {color: var(--text); font-weight: 500;}
.pipeline-tag {color: var(--text); text-transform: uppercase; letter-spacing: 0.15em; font-size: 0.8rem;}
.pipeline-desc {color: var(--text-muted); font-family: 'Geist', sans-serif;}

.query-label-big {font-family: 'Geist Mono', monospace; font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.2em; color: var(--text-dim); margin-bottom: 0.75rem;}

.features-grid {display: grid; grid-template-columns: repeat(3, 1fr); gap: 1.5rem; margin: 4rem 0;}
.feature-card {border: 1px solid var(--border); border-radius: 12px; padding: 2rem; background: var(--bg-soft); transition: all 0.35s cubic-bezier(0.16, 1, 0.3, 1); position: relative; overflow: hidden;}
.feature-card::before {content: ""; position: absolute; top: 0; left: 0; right: 0; height: 1px; background: linear-gradient(90deg, transparent, var(--text-muted), transparent); opacity: 0; transition: opacity 0.35s;}
.feature-card:hover {border-color: var(--border-strong); transform: translateY(-3px); background: var(--bg-card);}
.feature-card:hover::before {opacity: 0.6;}
.feature-icon {width: 40px; height: 40px; border: 1px solid var(--border-strong); border-radius: 8px; display: flex; align-items: center; justify-content: center; font-size: 1.2rem; color: var(--text); margin-bottom: 1.5rem; font-family: 'Geist Mono', monospace; transition: all 0.3s;}
.feature-card:hover .feature-icon {border-color: var(--text); background: var(--text); color: var(--bg);}
.feature-title {font-size: 1.1rem; font-weight: 500; letter-spacing: -0.02em; color: var(--text); margin: 0 0 0.6rem 0;}
.feature-desc {color: var(--text-muted); font-size: 0.9rem; line-height: 1.65; margin: 0;}
.feature-badge {position: absolute; top: 1.25rem; right: 1.25rem; font-family: 'Geist Mono', monospace; font-size: 0.65rem; color: var(--text-dim); text-transform: uppercase; letter-spacing: 0.15em;}

.terminal-stage {position: relative; height: 280vh; margin: 4rem 0 2rem 0; view-timeline-name: --term-scroll; view-timeline-axis: block;}
.terminal-sticky {position: sticky; top: 8vh; display: block;}
.terminal {border: 1px solid var(--border-strong); border-radius: 12px; background: #050505; overflow: hidden; box-shadow: 0 20px 60px -20px rgba(0, 0, 0, 0.8);}
.terminal-head {display: flex; align-items: center; gap: 0.5rem; padding: 0.9rem 1.25rem; border-bottom: 1px solid var(--border); background: var(--bg-soft);}
.terminal-dot {width: 10px; height: 10px; border-radius: 50%; background: var(--border-strong);}
.terminal-dot.r {background: #ef4444;}
.terminal-dot.y {background: #eab308;}
.terminal-dot.g {background: #22c55e;}
.terminal-title {margin-left: 1rem; font-family: 'Geist Mono', monospace; font-size: 0.75rem; color: var(--text-dim); letter-spacing: 0.05em;}
.terminal-body {padding: 1.5rem 1.75rem; font-family: 'Geist Mono', monospace; font-size: 0.88rem; line-height: 1.8; color: var(--text-muted);}
.term-prompt {color: #22c55e;}
.term-line {opacity: 0; transform: translateY(8px);}
.term-typing {display: inline-block; overflow: hidden; white-space: nowrap; border-right: 2px solid var(--text); width: 0;}
@keyframes typing {from {width: 0;} to {width: 30ch;}}
@keyframes termReveal {from {opacity: 0; transform: translateY(10px);} to {opacity: 1; transform: translateY(0);}}

@supports (animation-timeline: view()) {
    .term-typing {
        animation: typing 1s steps(32) both;
        animation-timeline: --term-scroll;
        animation-range: entry 50% cover 5%;
    }
    .term-line {
        animation: termReveal 0.45s cubic-bezier(0.16, 1, 0.3, 1) both;
        animation-timeline: --term-scroll;
    }
    .term-line.l1 {animation-range: cover 5% cover 12%;}
    .term-line.l2 {animation-range: cover 12% cover 19%;}
    .term-line.l3 {animation-range: cover 19% cover 26%;}
    .term-line.l4 {animation-range: cover 26% cover 33%;}
    .term-line.l5 {animation-range: cover 33% cover 40%;}
    .term-line.l6 {animation-range: cover 40% cover 47%;}
    .term-line.l7 {animation-range: cover 47% cover 54%;}
    .term-line.l8 {animation-range: cover 54% cover 62%;}
}

@supports not (animation-timeline: view()) {
    .term-typing {animation: typing 1.1s steps(32) 0.3s forwards, blink 0.8s step-end 4 0.3s;}
    .term-line {animation: termReveal 0.5s cubic-bezier(0.16, 1, 0.3, 1) forwards;}
    .term-line.l1 {animation-delay: 1.4s;}
    .term-line.l2 {animation-delay: 2.5s;}
    .term-line.l3 {animation-delay: 3.0s;}
    .term-line.l4 {animation-delay: 3.5s;}
    .term-line.l5 {animation-delay: 4.2s;}
    .term-line.l6 {animation-delay: 4.8s;}
    .term-line.l7 {animation-delay: 5.3s;}
    .term-line.l8 {animation-delay: 6.0s;}
}
.term-muted {color: var(--text-dim);}
.term-value {color: var(--text);}
.term-formula {background: rgba(250, 250, 250, 0.04); border-left: 2px solid var(--text); padding: 0.75rem 1rem; margin: 0.5rem 0; color: var(--text); font-weight: 500; display: inline-block;}
.term-caret {color: var(--text); animation: blink 1s step-start infinite;}
</style>
""", unsafe_allow_html=True)

системный_промпт = """Ты — ассистент базы знаний «Навигатор цифровой химии».

Правила:
1. Отвечай ТОЛЬКО на русском языке, даже если CONTEXT на английском.
2. Используй только факты из CONTEXT ниже. Не придумывай.
3. Если в CONTEXT есть хотя бы частичная информация по вопросу — дай развёрнутый ответ на её основе, перечисли все релевантные методы, молекулы, подходы из контекста.
4. Если CONTEXT состоит только из списков литературы (маркеры [1], [2], doi.org) и не содержит содержательного ответа — скажи: «В найденных фрагментах преимущественно библиографические ссылки. Попробуйте переформулировать вопрос или выбрать другой кейс».
5. Если CONTEXT совсем не относится к вопросу — скажи: «В базе нет данных для ответа на этот вопрос».
6. Химические термины и названия методов оставляй в оригинале и давай русский перевод в скобках при первом упоминании.
7. В конце ответа обязательно добавь раздел «Источники:» с новой строки. Каждый источник печатай с новой строки в формате `[N] имя_файла.pdf, стр. N`. Не склеивай источники в одну строку.
8. Если найдена формула — выведи её отдельным блоком с расшифровкой переменных."""


@st.cache_resource
def загрузить_модель():
    return SentenceTransformer("intfloat/multilingual-e5-base")


@st.cache_resource
def загрузить_qdrant():
    папка = os.path.join(os.path.dirname(os.path.abspath(__file__)), "qdrant_db")
    return QdrantClient(path=папка)


def похоже_на_библиографию(текст):
    """Чанк считается библиографией, если суммарно много ссылочных маркеров."""
    скобки = len(re.findall(r"\[\d{1,3}\]", текст))
    нум = len(re.findall(r"(?:^|\n)\s*\d{1,4}\.\s+[A-ZА-ЯЁ]", текст, re.MULTILINE))
    et_al = len(re.findall(r"\bet\s+al\.?", текст, re.IGNORECASE))
    doi = len(re.findall(r"(?:doi[:\s\.]|10\.\d{4,}\s*/)", текст, re.IGNORECASE))
    http = len(re.findall(r"https?://\S+", текст))
    годы = len(re.findall(r"\((?:19|20)\d{2}\)", текст))
    авторы = len(re.findall(
        r"[A-ZА-ЯЁ][a-zа-яё\-]{2,}(?:\s+[A-Z]{1,3}[,\s]|,\s+[A-ZА-ЯЁ]\.)",
        текст
    ))
    маркеры_бд = len(re.findall(
        r"\[(?:CrossRef|PubMed|Google\s+Scholar|DOI)\]",
        текст, re.IGNORECASE
    ))
    return (скобки + нум + et_al + doi + http + годы + авторы + маркеры_бд) >= 6


def найти_похожие(вопрос, выбранный_кейс, количество):
    модель = загрузить_модель()
    клиент = загрузить_qdrant()
    вектор = модель.encode("query: " + вопрос, normalize_embeddings=True).tolist()

    если_фильтр = None
    if выбранный_кейс != "все":
        если_фильтр = Filter(
            must=[FieldCondition(key="case", match=MatchValue(value=выбранный_кейс))]
        )

    ответ = клиент.query_points(
        collection_name="химия",
        query=вектор,
        limit=количество * 3,
        query_filter=если_фильтр,
        with_payload=True
    )

    содержательные = [
        точка for точка in ответ.points
        if not похоже_на_библиографию(точка.payload.get("text", ""))
    ]

    if not содержательные:
        return ответ.points[:количество]
    return содержательные[:количество]


def получить_ответ_от_groq(вопрос, фрагменты):
    if not _ключи_groq():
        return "Ошибка: GROQ_API_KEY не задан в файле .env"

    контекст = ""
    for i, фр in enumerate(фрагменты, 1):
        контекст += f"[{i}] Документ: {фр.payload['document']}, стр. {фр.payload['page']}\n"
        контекст += фр.payload["text"] + "\n\n"

    ответ = вызвать_groq({
        "model": "llama-3.3-70b-versatile",
        "messages": [
            {"role": "system", "content": системный_промпт},
            {"role": "user", "content": f"CONTEXT:\n{контекст}\n\nQUESTION:\n{вопрос}"}
        ],
        "temperature": 0.1,
        "max_tokens": 1500,
    })
    текст = ответ.choices[0].message.content
    return отрезать_источники(текст)


def отрезать_источники(текст):
    """Удаляет раздел со ссылками из ответа LLM — их мы выводим отдельно."""
    совпадение = re.search(r"\n*\**\s*(Источники|Sources|Ссылки)\s*:?\**", текст, re.IGNORECASE)
    if not совпадение:
        return текст.strip()
    return текст[:совпадение.start()].rstrip()


def красивое_имя_файла(имя):
    """Убирает .pdf, подчёркивания, лишние тире — делает заголовок читаемым."""
    без_расширения = имя[:-4] if имя.lower().endswith(".pdf") else имя
    чистое = без_расширения.replace("_", " ").replace("--", " — ")
    чистое = re.sub(r"\s+", " ", чистое).strip()
    if len(чистое) > 80:
        чистое = чистое[:77] + "…"
    return чистое


def построить_источники_html(фрагменты):
    """Группирует фрагменты по документу, собирает HTML-блок источников."""
    группы = {}
    порядок = []
    for фр in фрагменты:
        имя = фр["document"]
        стр = фр["page"]
        if имя not in группы:
            группы[имя] = []
            порядок.append(имя)
        if стр not in группы[имя]:
            группы[имя].append(стр)

    строки = ""
    for i, док in enumerate(порядок, 1):
        страницы = ", ".join(str(p) for p in sorted(группы[док]))
        имя = красивое_имя_файла(док)
        строки += (
            f'<div class="source-row">'
            f'<span class="num">{i:02d}</span>'
            f'<span class="doc">{имя}</span>'
            f'<span class="pages">стр. {страницы}</span>'
            f'</div>'
        )
    return строки


def почистить_pdf_текст(текст):
    """Убирает артефакты PDF-экстракции: переносы слов, лишние пробелы, висящие номера страниц."""
    результат = re.sub(r"(\w)-\s*\n\s*(\w)", r"\1\2", текст)
    результат = re.sub(r"\n(?!\s*\n)", " ", результат)
    результат = re.sub(r"\s*\b\d+\s+of\s+\d+\b\s*", " ", результат)
    результат = re.sub(r" {2,}", " ", результат)
    return результат.strip()


def _ключи_groq():
    """Возвращает список непустых ключей Groq в порядке предпочтения."""
    ключи = []
    for имя_переменной in ("GROQ_API_KEY", "GROQ_API_KEY_2", "GROQ_API_KEY_3"):
        к = os.getenv(имя_переменной)
        if к and к.strip():
            ключи.append(к.strip())
    return ключи


def _это_rate_limit(ошибка):
    """Определяет является ли исключение ошибкой лимита (429)."""
    текст = str(ошибка).lower()
    return "429" in текст or "rate_limit" in текст or "rate limit" in текст or "tokens per day" in текст


def вызвать_groq(параметры_запроса, резервная_модель="llama-3.1-8b-instant"):
    """Вызывает Groq с автоотказом: сначала все ключи на основной модели,
    затем все ключи на резервной (если исходная упёрлась в TPD)."""
    ключи = _ключи_groq()
    if not ключи:
        raise RuntimeError("Не задан ни один GROQ_API_KEY в .env")

    основная_модель = параметры_запроса.get("model")
    модели_к_попытке = [основная_модель]
    if резервная_модель and резервная_модель != основная_модель:
        модели_к_попытке.append(резервная_модель)

    последняя_ошибка = None
    for модель in модели_к_попытке:
        параметры = dict(параметры_запроса, model=модель)
        for ключ in ключи:
            try:
                клиент = Groq(api_key=ключ)
                return клиент.chat.completions.create(**параметры)
            except Exception as ошибка:
                последняя_ошибка = ошибка
                if _это_rate_limit(ошибка):
                    continue
                raise
    raise последняя_ошибка


_МАТЕМАТИЧЕСКИЕ_СИМВОЛЫ = set("Σ∑∏∫∈∉≤≥≠≈∞αβγθσμπλ∗·×→∂∇√∝⊂⊃⊆⊇∪∩⟨⟩⇒⇔")


def содержит_математику(текст):
    """Быстрый предфильтр: стоит ли тратить LLM-токены на поиск формул в тексте."""
    if any(с in _МАТЕМАТИЧЕСКИЕ_СИМВОЛЫ for с in текст):
        return True
    if re.search(r"\b[a-zA-Zα-ωΑ-Ω]\s*\([a-zA-Z0-9,\s]+\)\s*=", текст):
        return True
    if re.search(r"\b\w+\s*=\s*[\w\-+\d/·*().\[\]]{5,}", текст) and re.search(r"[_^]|\b\d+\b", текст):
        return True
    return False


@st.cache_data(show_spinner=False)
def перевести_на_русский(текст):
    """Переводит фрагмент на русский через Groq 8b с автофолбэком, результат кэшируется."""
    if not _ключи_groq():
        return текст
    try:
        ответ = вызвать_groq({
            "model": "llama-3.1-8b-instant",
            "messages": [
                {"role": "system", "content": "Ты переводчик научных текстов по химии и машинному обучению. Переведи на русский. Сохраняй термины в оригинале, давая русский перевод в скобках при первом упоминании. Убирай артефакты PDF (битые пробелы, случайные переносы, отсечённые слова). Химические формулы и обозначения не трогай. Верни только перевод, без вступлений."},
                {"role": "user", "content": текст}
            ],
            "temperature": 0.1,
            "max_tokens": 1000,
        })
        return ответ.choices[0].message.content
    except Exception:
        return текст


@st.cache_data(show_spinner=False)
def извлечь_формулы(текст):
    """Находит математические формулы в тексте и возвращает список {latex, описание}."""
    if not содержит_математику(текст):
        return []
    if not _ключи_groq():
        return []
    try:
        ответ = вызвать_groq({
            "model": "llama-3.1-8b-instant",
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": (
                    "Ты извлекаешь математические формулы из научного текста и конвертируешь их в корректный LaTeX.\n\n"
                    "Правила:\n"
                    "1. Найди все содержательные математические выражения: уравнения, функции, суммы, интегралы, нормы, вероятности, операторы argmin/argmax.\n"
                    "2. Игнорируй простые числа, единицы измерения, ссылки на литературу [12].\n"
                    "3. Каждую формулу ОБЯЗАТЕЛЬНО перепиши в корректном LaTeX-синтаксисе. Не копируй Unicode-символы!\n\n"
                    "Конвертация Unicode → LaTeX:\n"
                    "Σ, ∑ → \\\\sum    ∏ → \\\\prod    ∫ → \\\\int    ∈ → \\\\in    ∉ → \\\\notin\n"
                    "≤ → \\\\leq    ≥ → \\\\geq    ≠ → \\\\neq    ≈ → \\\\approx    ∞ → \\\\infty\n"
                    "α β γ → \\\\alpha \\\\beta \\\\gamma    θ → \\\\theta    σ → \\\\sigma    μ → \\\\mu\n"
                    "∗ · × → \\\\cdot    → → \\\\to    ∂ → \\\\partial    ∇ → \\\\nabla\n"
                    "Подстрочные: x_1, iref → i_{ref}, xopt → x_{opt}\n"
                    "Надстрочные: x^2, e^{-t}\n"
                    "argmin → \\\\arg\\\\min    argmax → \\\\arg\\\\max\n"
                    "Модуль |x| → |x|    Норма ||x|| → \\\\|x\\\\|\n\n"
                    "Примеры правильной конвертации:\n"
                    "'f(x) = Σ m∈IQA w(m)∗|m(ix)−m(iref)|' → 'f(x) = \\\\sum_{m \\\\in IQA} w(m) \\\\cdot |m(i_x) - m(i_{ref})|'\n"
                    "'xopt ∈ argmin x∈X f(x)' → 'x_{opt} \\\\in \\\\arg\\\\min_{x \\\\in X} f(x)'\n"
                    "'E = mc^2' → 'E = mc^2'\n\n"
                    "Ответ строго JSON: {\"formulas\": [{\"latex\": \"...\", \"описание\": \"...\"}]}.\n"
                    "Описание на русском, коротко: что это за формула и что означают переменные.\n"
                    "Если формул нет — {\"formulas\": []}. Не придумывай."
                )},
                {"role": "user", "content": текст}
            ],
            "temperature": 0.0,
            "max_tokens": 900,
        })
        сырой = ответ.choices[0].message.content
        данные = json.loads(сырой)
        if isinstance(данные, dict):
            for ключ in ("formulas", "формулы", "result", "items"):
                if ключ in данные and isinstance(данные[ключ], list):
                    return данные[ключ]
        return данные if isinstance(данные, list) else []
    except Exception:
        return []


def показать_демо_ответ(вопрос):
    вопрос_нижний = вопрос.lower()
    for запись in заготовленные_ответы:
        if any(слово in вопрос_нижний for слово in запись["вопрос"].lower().split()):
            return запись
    return заготовленные_ответы[0]


названия_кейсов = {"все": "Все кейсы"}
for ключ, данные in кейсы.items():
    названия_кейсов[ключ] = данные["название"]

расширенные_кейсы = {
    "поиск_молекул": {
        "методы": ["GNN — графовые нейронные сети на молекулярных графах", "Molecular fingerprints — бинарные отпечатки структуры", "Виртуальный скрининг больших библиотек соединений", "Transformer-модели для SMILES-строк"],
        "данные": ["Молекулярные структуры (SMILES, InChI)", "Биологическая активность (IC50, Ki)", "Базы: ChEMBL, PubChem, ZINC"],
        "вопрос": "Какие нейросетевые методы используют для поиска новых лекарственных молекул?"
    },
    "токсичность": {
        "методы": ["QSAR — количественные зависимости структура-активность", "Random Forest и градиентный бустинг", "Deep learning на молекулярных графах", "Ансамбли моделей для end-point-ов"],
        "данные": ["LD50, IC50, Ames-тест, hERG", "Tox21, ToxCast, PubChem BioAssay"],
        "вопрос": "Как предсказать острую токсичность нового соединения?"
    },
    "оптимизация_реакции": {
        "методы": ["Байесовская оптимизация (Gaussian Process)", "Активное обучение", "Multi-armed bandits", "Self-driving labs (автономные установки)"],
        "данные": ["Результаты экспериментов (HPLC, GC)", "Условия: температура, время, катализатор, растворитель"],
        "вопрос": "Как подобрать оптимальные условия реакции при минимуме экспериментов?"
    },
    "выход_реакции": {
        "методы": ["Transformer-модели на SMILES реагентов", "Random Forest на молекулярных дескрипторах", "Graph Neural Networks", "Формула: Y = (m_факт / m_теор) × 100%"],
        "данные": ["Реагенты, продукты, условия", "USPTO reaction dataset, Reaxys"],
        "вопрос": "Какая ожидаемая выходность реакции с такими-то реагентами?"
    },
    "катализ": {
        "методы": ["Регрессия на дескрипторах катализатора", "GNN на структурах поверхности", "Генеративные модели для подбора состава", "DFT + ML для скрининга"],
        "данные": ["Состав, активность, селективность", "Materials Project, Catalysis-Hub"],
        "вопрос": "Какой катализатор эффективнее всего для данной реакции?"
    },
    "новые_материалы": {
        "методы": ["GNN на кристаллических графах (CGCNN, SchNet)", "Генеративные модели (VAE, GAN, diffusion)", "Active learning + DFT", "MEGNet, M3GNet для свойств"],
        "данные": ["Materials Project, OQMD, AFLOW", "Кристаллические структуры (CIF)"],
        "вопрос": "Как найти стабильный материал с заданной шириной запрещённой зоны?"
    },
    "свойства_материалов": {
        "методы": ["GNN и дескрипторные подходы", "Transfer learning с больших датасетов", "Symbolic regression", "Bayesian neural networks для uncertainty"],
        "данные": ["Механические, тепловые, электронные свойства", "Экспериментальные и DFT-расчётные базы"],
        "вопрос": "Как по составу сплава предсказать его твёрдость и теплопроводность?"
    },
    "анализ_спектров": {
        "методы": ["CNN для распознавания пиков", "Transformer на спектральных данных", "NLP-подходы для структурной интерпретации", "Автоматическая расшифровка ЯМР, ИК, масс-спектров"],
        "данные": ["Базы спектров: NIST, SDBS, nmrshiftdb", "ЯМР (1H, 13C), ИК, МС"],
        "вопрос": "Как автоматически определить структуру по ЯМР-спектру?"
    },
    "контроль_производства": {
        "методы": ["Soft sensors (мягкие датчики) на базе LSTM", "Байесовские сети для диагностики", "Autoencoders для обнаружения аномалий", "Model Predictive Control + ML"],
        "данные": ["Технологические параметры в реальном времени", "Сенсоры, хроматография, спектроскопия"],
        "вопрос": "Как предсказать качество продукта без остановки производства?"
    },
    "предиктивное_обслуживание": {
        "методы": ["LSTM для временных рядов датчиков", "Isolation Forest для аномалий", "Survival analysis для оценки остаточного ресурса", "Классификация типов поломок"],
        "данные": ["Вибрация, температура, давление, ток", "История отказов оборудования"],
        "вопрос": "Когда нужно обслужить компрессор чтобы избежать аварии?"
    },
    "энергоэффективность": {
        "методы": ["Оптимизация на нейросетевых суррогатах", "Термодинамическое моделирование + ML", "Reinforcement learning для управления", "Pinch-анализ с ML-аугментацией"],
        "данные": ["Энергопотребление узлов", "Теплообмен, exergy-анализ"],
        "вопрос": "Как сократить энергозатраты ректификационной колонны на 10%?"
    },
    "зелёная_химия": {
        "методы": ["Green metrics: atom economy, E-factor, PMI", "ML для скрининга растворителей", "Retrosynthesis с оценкой экологичности", "Solvent selection tools"],
        "данные": ["Реакции, растворители, отходы", "CHEM21, Reaxys Green"],
        "вопрос": "Как выбрать экологичный маршрут синтеза данной молекулы?"
    },
    "извлечение_данных": {
        "методы": ["Named Entity Recognition (ChemDataExtractor, OSCAR)", "BERT-подобные модели для химии (ChemBERTa, MatBERT)", "Optical Structure Recognition (DECIMER)", "Relation extraction для реакций"],
        "данные": ["Научные статьи, патенты", "USPTO patents, PubMed, CrossRef"],
        "вопрос": "Как автоматически извлечь все реакции из патента?"
    },
    "лабораторные_данные": {
        "методы": ["FAIR-принципы (Findable, Accessible, Interoperable, Reusable)", "Electronic Lab Notebooks (ELN)", "Open Reaction Database (ORD) формат", "Автоматическая метадата-экстракция"],
        "данные": ["Протоколы, условия, результаты", "Метаданные по FAIR"],
        "вопрос": "Как организовать базу экспериментов чтобы ими могли пользоваться другие?"
    },
    "компетенции": {
        "методы": ["Хемоинформатика (RDKit, OpenBabel)", "Машинное обучение в химии (sklearn, PyTorch, DeepChem)", "Процессный инжиниринг", "Workflow-менеджеры (Snakemake, Nextflow)"],
        "данные": ["Междисциплинарные навыки", "Программирование + химия + ML"],
        "вопрос": "Какие ключевые компетенции нужны специалисту по цифровой химии?"
    }
}

верх_html = (
    '<div class="nav">'
    '<div class="nav-brand"><span class="logo">⬢</span><span>Навигатор / Цифровая химия</span></div>'
    '<div class="nav-meta"><span>система активна</span><span style="color:var(--text-dim);">v.1.0 · 2026</span></div>'
    '</div>'
    '<div class="hero-block">'
    '<div class="hero-kicker">RAG · Семантический поиск · Big Data в химии</div>'
    '<h1 class="hero-title">Поиск по научной<br><span class="accent">литературе химии.</span><span class="cursor"></span></h1>'
    '<p class="hero-desc">Векторная база знаний из 575 научных публикаций. Задайте вопрос на русском — получите ответ с указанием источников, страниц и цитат из оригиналов.</p>'
    '</div>'
    '<div class="stats-grid">'
    '<div class="stat-item"><div class="stat-label">Документов</div><div class="stat-value">575</div></div>'
    '<div class="stat-item"><div class="stat-label">Фрагментов</div><div class="stat-value">46 026</div></div>'
    '<div class="stat-item"><div class="stat-label">Кейсов</div><div class="stat-value">15</div></div>'
    '<div class="stat-item"><div class="stat-label">Размерность</div><div class="stat-value">768</div></div>'
    '</div>'
)
st.markdown(верх_html, unsafe_allow_html=True)

маркиза_слова = [
    "multilingual-e5-base", "Qdrant vector DB", "LLaMA 3.3 70B", "Groq API",
    "QSAR модели", "GNN · графовые нейросети", "Байесовская оптимизация",
    "SMILES · InChI", "Cosine similarity", "768-мерный вектор",
    "RAG retrieval", "Molecular fingerprints", "DECIMER · OSR",
    "Active learning", "Soft sensors", "Open Reaction Database"
]
маркиза_html = '<div class="marquee"><div class="marquee-track">'
for _ in range(2):
    for слово in маркиза_слова:
        маркиза_html += f'<div class="marquee-item">{слово}</div>'
маркиза_html += '</div></div>'
st.markdown(маркиза_html, unsafe_allow_html=True)

st.markdown(
    '<div class="scroll-hint">'
    '<div class="scroll-hint-label">прокрутите чтобы увидеть больше</div>'
    '<div class="scroll-hint-line"></div>'
    '</div>',
    unsafe_allow_html=True
)

фичи_html = (
    '<div class="query-label-big" style="margin-bottom: 1.5rem;">Возможности системы</div>'
    '<div class="features-grid">'

    '<div class="feature-card">'
    '<div class="feature-badge">01</div>'
    '<div class="feature-icon">⬢</div>'
    '<div class="feature-title">Семантический поиск</div>'
    '<div class="feature-desc">Поиск по смыслу, а не по ключевым словам. Модель multilingual-e5-base преобразует вопрос в 768-мерный вектор и находит похожие фрагменты по косинусной метрике.</div>'
    '</div>'

    '<div class="feature-card">'
    '<div class="feature-badge">02</div>'
    '<div class="feature-icon">◈</div>'
    '<div class="feature-title">Кросс-языковое сопоставление</div>'
    '<div class="feature-desc">Задавайте вопросы на русском — система найдёт релевантные фрагменты в англоязычных статьях и переведёт ответ обратно на русский.</div>'
    '</div>'

    '<div class="feature-card">'
    '<div class="feature-badge">03</div>'
    '<div class="feature-icon">◇</div>'
    '<div class="feature-title">Прозрачные источники</div>'
    '<div class="feature-desc">Каждый ответ сопровождается ссылкой на конкретный документ и номер страницы. Без галлюцинаций — только то, что есть в базе знаний.</div>'
    '</div>'

    '</div>'
)
st.markdown(фичи_html, unsafe_allow_html=True)

терминал_html = (
    '<div class="query-label-big" style="margin-top: 5rem;">Как это работает</div>'
    '<div class="terminal-stage">'
    '<div class="terminal-sticky">'
    '<div class="terminal">'
    '<div class="terminal-head">'
    '<div class="terminal-dot r"></div>'
    '<div class="terminal-dot y"></div>'
    '<div class="terminal-dot g"></div>'
    '<div class="terminal-title">navigator.py · live demo</div>'
    '</div>'
    '<div class="terminal-body">'
    '<div><span class="term-prompt">&gt;</span> <span class="term-typing">Какая формула выхода реакции?</span></div>'
    '<div class="term-line l1 term-muted">[qdrant]  векторизация запроса · 768-dim</div>'
    '<div class="term-line l2 term-muted">[qdrant]  найдено <span class="term-value">5 фрагментов</span> · 142ms</div>'
    '<div class="term-line l3 term-muted">[groq]    модель <span class="term-value">llama-3.3-70b</span> · генерация...</div>'
    '<div class="term-line l4" style="margin-top: 0.75rem; color: var(--text);">Выход реакции (Y) рассчитывается по формуле:</div>'
    '<div class="term-line l5"><div class="term-formula">Y = (m_факт / m_теор) × 100%</div></div>'
    '<div class="term-line l6" style="color: var(--text-muted);">где m_факт — фактически полученная масса продукта,<br>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;m_теор — теоретически рассчитанная масса.</div>'
    '<div class="term-line l7 term-muted" style="margin-top: 0.75rem;">Источники:</div>'
    '<div class="term-line l7 term-muted">[1] s13321-021-00577-1.pdf, стр. 3</div>'
    '<div class="term-line l7 term-muted">[2] s13321-020-00442-7.pdf, стр. 5</div>'
    '<div class="term-line l8"><span class="term-prompt">&gt;</span> <span class="term-caret">▊</span></div>'
    '</div>'
    '</div>'
    '</div>'
    '</div>'
)
st.markdown(терминал_html, unsafe_allow_html=True)

st.markdown(
    '<div class="scroll-hint" style="margin-top: 3rem;">'
    '<div class="scroll-hint-label">попробуйте сами ↓</div>'
    '<div class="scroll-hint-line"></div>'
    '</div>',
    unsafe_allow_html=True
)

вкладка1, вкладка2, вкладка3 = st.tabs(["Поиск", "Кейсы", "Архитектура"])

with вкладка1:
    st.markdown('<div class="query-label-big">Задайте вопрос базе знаний</div>', unsafe_allow_html=True)

    вопрос_пользователя = st.text_area(
        "вопрос",
        value=st.session_state.get("вопрос_пользователя", ""),
        height=130,
        placeholder="Какие методы машинного обучения используются для предсказания растворимости молекул?",
        label_visibility="collapsed"
    )

    к1, к2, к3, к4 = st.columns([2, 1.3, 1, 1.2], gap="small")
    with к1:
        выбор_кейса = st.selectbox(
            "Фильтр по кейсу",
            options=list(названия_кейсов.keys()),
            format_func=lambda к: названия_кейсов[к]
        )
    with к2:
        количество_фрагментов = st.slider("Фрагментов", 3, 10, 5)
    with к3:
        st.markdown('<div style="height: 1.8rem;"></div>', unsafe_allow_html=True)
        демо_режим = st.toggle("Демо-режим", value=False)
    with к4:
        st.markdown('<div style="height: 1.8rem;"></div>', unsafe_allow_html=True)
        кнопка = st.button("Найти ответ", type="primary", use_container_width=True)

    st.markdown('<div class="query-label-big" style="margin-top: 2.5rem;">Примеры вопросов</div>', unsafe_allow_html=True)
    примеры = [
        "Какая формула выхода реакции?",
        "Как предсказать токсичность молекулы?",
        "Что такое байесовская оптимизация?",
        "Как GNN применяются в химии?",
        "Что такое молекулярные отпечатки?"
    ]
    чипы_колонки = st.columns(len(примеры))
    for i, пример in enumerate(примеры):
        with чипы_колонки[i]:
            if st.button(пример, key=f"chip_{i}", use_container_width=True):
                st.session_state["вопрос_пользователя"] = пример
                st.rerun()

    if "результаты_поиска" not in st.session_state:
        st.session_state.результаты_поиска = None

    if кнопка and вопрос_пользователя.strip():
        if демо_режим:
            with st.spinner("Поиск в демо-базе..."):
                демо = показать_демо_ответ(вопрос_пользователя)
            st.session_state.результаты_поиска = {"тип": "демо", "данные": демо}
        else:
            try:
                with st.spinner("Векторный поиск в Qdrant..."):
                    точки = найти_похожие(вопрос_пользователя, выбор_кейса, количество_фрагментов)
                if not точки:
                    st.session_state.результаты_поиска = None
                    st.warning("Ничего не найдено. Попробуйте изменить вопрос или кейс.")
                else:
                    with st.spinner("Генерация ответа · llama-3.3-70b..."):
                        ответ = получить_ответ_от_groq(вопрос_пользователя, точки)
                    st.session_state.результаты_поиска = {
                        "тип": "rag",
                        "ответ": ответ,
                        "фрагменты": [
                            {
                                "document": т.payload["document"],
                                "page": т.payload["page"],
                                "case": т.payload["case"],
                                "text": т.payload["text"],
                                "score": float(т.score),
                            }
                            for т in точки
                        ],
                    }
            except Exception as ошибка:
                st.session_state.результаты_поиска = None
                st.error(f"Ошибка подключения: {ошибка}")
                st.info("Включите «Демо-режим» чтобы увидеть заготовленные ответы без интернета.")
    elif кнопка:
        st.warning("Поле вопроса пустое.")

    результат = st.session_state.результаты_поиска
    if результат and результат["тип"] == "демо":
        демо = результат["данные"]
        мета_html = (
            '<div class="answer-container">'
            '<div class="answer-meta">'
            '<span><span class="dot"></span>демо-режим</span>'
            f'<span>кейс · {демо.get("кейс", "")}</span>'
            '</div></div>'
        )
        st.markdown(мета_html, unsafe_allow_html=True)
        st.markdown(демо["ответ"])

        st.markdown('<div class="query-label-big" style="margin-top: 3rem;">Источники</div>', unsafe_allow_html=True)
        источники_html = ""
        for i, ист in enumerate(демо["источники"], 1):
            источники_html += f'<div class="source-row"><span class="num">{i:02d}</span><span class="doc">{ист}</span></div>'
        st.markdown(источники_html, unsafe_allow_html=True)

    elif результат and результат["тип"] == "rag":
        ответ = результат["ответ"]
        фрагменты = результат["фрагменты"]

        мета_html = (
            '<div class="answer-container">'
            '<div class="answer-meta">'
            '<span><span class="dot"></span>ответ сгенерирован</span>'
            '<span>модель · llama-3.3-70b</span>'
            f'<span>фрагментов · {len(фрагменты)}</span>'
            '</div></div>'
        )
        st.markdown(мета_html, unsafe_allow_html=True)
        st.markdown(ответ)

        st.markdown('<div class="query-label-big" style="margin-top: 3rem;">Источники</div>', unsafe_allow_html=True)
        st.markdown(построить_источники_html(фрагменты), unsafe_allow_html=True)

        st.markdown('<div class="query-label-big" style="margin-top: 3rem;">Найденные фрагменты</div>', unsafe_allow_html=True)
        переводить = st.toggle(
            "Показать перевод на русский",
            value=False,
            key="переводить_фрагменты",
            help="Перевод через LLM, кэшируется."
        )

        for i, фр in enumerate(фрагменты, 1):
            заголовок = f"{i:02d}   {фр['document']}   ·   стр. {фр['page']}   ·   score {фр['score']:.3f}"
            with st.expander(заголовок):
                st.markdown(f"**Кейс:** {получить_название_кейса(фр['case'])}")
                чистый = почистить_pdf_текст(фр["text"])

                with st.spinner("Поиск формул..."):
                    формулы = извлечь_формулы(чистый[:2000])
                if формулы:
                    st.markdown("**Формулы:**")
                    for ф in формулы:
                        латех = ф.get("latex", "")
                        описание = ф.get("описание") or ф.get("description", "")
                        if латех:
                            try:
                                st.latex(латех)
                            except Exception:
                                st.code(латех, language="latex")
                        if описание:
                            st.caption(описание)
                    st.markdown("---")

                if переводить:
                    with st.spinner("Перевод..."):
                        перевод = перевести_на_русский(чистый[:1500])
                    st.markdown(перевод)
                    if len(чистый) > 1500:
                        st.caption("Показан перевод первых 1500 символов фрагмента.")
                else:
                    усечённый = чистый[:900] + ("…" if len(чистый) > 900 else "")
                    st.markdown(усечённый)

with вкладка2:
    описания_кейсов = {
        "поиск_молекул": "Поиск перспективных лекарственных молекул с нужными свойствами среди миллионов кандидатов.",
        "токсичность": "Предсказание токсичности химических соединений до проведения экспериментов.",
        "оптимизация_реакции": "Подбор оптимальных условий реакции с минимальным числом опытов.",
        "выход_реакции": "Прогноз выхода продукта реакции по структурам реагентов и условиям.",
        "катализ": "Поиск эффективных катализаторов для химических реакций.",
        "новые_материалы": "Предсказание стабильных кристаллических структур и новых материалов с заданными свойствами.",
        "свойства_материалов": "Прогноз механических, тепловых и электронных свойств материалов.",
        "анализ_спектров": "Автоматическая расшифровка ЯМР, ИК и масс-спектров для определения структуры веществ.",
        "контроль_производства": "Мониторинг и управление качеством химического производства в реальном времени.",
        "предиктивное_обслуживание": "Прогнозирование поломок оборудования по данным датчиков.",
        "энергоэффективность": "Снижение энергопотребления химических производств с помощью оптимизации процессов.",
        "зелёная_химия": "Выбор экологически безопасных маршрутов синтеза с минимальными отходами.",
        "извлечение_данных": "Автоматическое извлечение химических данных из научных статей и патентов.",
        "лабораторные_данные": "Создание структурированных баз лабораторных экспериментов по стандарту FAIR.",
        "компетенции": "Связь методов Big Data с задачами направления «Цифровая химическая технология»."
    }

    кейсы_html = '<div class="query-label-big">15 кейсов · применение Big Data в химии</div>'
    for индекс, (ключ, данные) in enumerate(кейсы.items(), 1):
        название = данные["название"]
        описание = описания_кейсов.get(ключ, "")
        расш = расширенные_кейсы.get(ключ, {})
        методы_li = "".join(f"<li>{м}</li>" for м in расш.get("методы", []))
        данные_li = "".join(f"<li>{д}</li>" for д in расш.get("данные", []))
        вопрос_примера = расш.get("вопрос", "")
        развёрнутый = (
            f'<div class="case-expanded">'
            f'<div class="case-exp-label">Методы и подходы</div>'
            f'<ul class="case-exp-list">{методы_li}</ul>'
            f'<div class="case-exp-label">Типы данных</div>'
            f'<ul class="case-exp-list">{данные_li}</ul>'
            f'<div class="case-exp-label">Пример вопроса к базе</div>'
            f'<div class="case-exp-quote">«{вопрос_примера}»</div>'
            f'</div>'
        )
        кейсы_html += (
            f'<details class="case-details">'
            f'<summary>'
            f'<div class="case-num">{индекс:02d}</div>'
            f'<div><div class="case-title">{название}</div><div class="case-desc">{описание}</div></div>'
            f'<div class="case-toggle">+</div>'
            f'</summary>'
            f'{развёрнутый}'
            f'</details>'
        )
    st.markdown(кейсы_html, unsafe_allow_html=True)

with вкладка3:
    этапы = [
        ("01", "ЗАГРУЗКА", "575 PDF → pypdf → фрагменты ~800 символов (overlap 100)"),
        ("02", "ТЕГИ", "авто-тегирование по 15 кейсам (ключевые слова RU/EN)"),
        ("03", "ВЕКТОРЫ", "intfloat/multilingual-e5-base → 768-мерный вектор"),
        ("04", "ХРАНЕНИЕ", "Qdrant (локально, косинусная метрика) · 46 026 точек"),
        ("05", "ЗАПРОС", "векторизация вопроса + фильтр по кейсу"),
        ("06", "ПОИСК", "top-k похожих фрагментов по cosine similarity"),
        ("07", "ОТВЕТ", "Groq API / llama-3.3-70b-versatile"),
        ("08", "ВЫВОД", "ответ на русском + цитаты + [документ, стр.]")
    ]
    пайплайн_html = '<div class="query-label-big">Архитектура системы · RAG-пайплайн</div>'
    for номер, тег, описание in этапы:
        пайплайн_html += f'<div class="pipeline-step"><div class="pipeline-num">{номер}</div><div class="pipeline-tag">{тег}</div><div class="pipeline-desc">{описание}</div></div>'
    st.markdown(пайплайн_html, unsafe_allow_html=True)

    стек = [
        ("Среда", "Python 3.12", ""),
        ("Парсер PDF", "pypdf", "извлечение текста постранично"),
        ("Эмбеддинги", "sentence-transformers", "intfloat/multilingual-e5-base · 768-dim"),
        ("Векторная БД", "Qdrant", "embedded · cosine"),
        ("LLM модель", "Groq / LLaMA 3.3 70B", "versatile · temperature 0.1"),
        ("Интерфейс", "Streamlit", "wide layout · кастомный CSS"),
        ("Конфиг", "python-dotenv", "GROQ_API_KEY")
    ]
    стек_html = '<div class="query-label-big" style="margin-top: 4rem;">Технологический стек</div>'
    for ключ, значение, подсказка in стек:
        стек_html += f'<div class="tech-row"><div class="tech-key">{ключ}</div><div class="tech-val">{значение}<span class="hint">{подсказка}</span></div></div>'
    st.markdown(стек_html, unsafe_allow_html=True)
