"""
Весь визуальный слой интерфейса: CSS-стили, HTML-шаблоны и функции-рендереры.
app.py импортирует отсюда готовые функции и не содержит ни одной строки CSS/HTML.
"""

import re
import streamlit as st


# =====================================================================
#  CSS-стили — подключаются один раз при старте приложения
# =====================================================================

CSS_БЛОК = """
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
"""


# =====================================================================
#  Данные для визуальных блоков (только отображение)
# =====================================================================

_маркиза_слова = [
    "multilingual-e5-base", "Qdrant vector DB", "LLaMA 3.3 70B", "Groq API",
    "QSAR модели", "GNN · графовые нейросети", "Байесовская оптимизация",
    "SMILES · InChI", "Cosine similarity", "768-мерный вектор",
    "RAG retrieval", "Molecular fingerprints", "DECIMER · OSR",
    "Active learning", "Soft sensors", "Open Reaction Database"
]

_фичи = [
    ("01", "⬢", "Семантический поиск",
     "Поиск по смыслу, а не по ключевым словам. Модель multilingual-e5-base преобразует вопрос в 768-мерный вектор и находит похожие фрагменты по косинусной метрике."),
    ("02", "◈", "Кросс-языковое сопоставление",
     "Задавайте вопросы на русском — система найдёт релевантные фрагменты в англоязычных статьях и переведёт ответ обратно на русский."),
    ("03", "◇", "Прозрачные источники",
     "Каждый ответ сопровождается ссылкой на конкретный документ и номер страницы. Без галлюцинаций — только то, что есть в базе знаний."),
]

_этапы_пайплайна = [
    ("01", "ЗАГРУЗКА", "575 PDF → pypdf → фрагменты ~800 символов (overlap 100)"),
    ("02", "ТЕГИ", "авто-тегирование по 15 кейсам (ключевые слова RU/EN)"),
    ("03", "ВЕКТОРЫ", "intfloat/multilingual-e5-base → 768-мерный вектор"),
    ("04", "ХРАНЕНИЕ", "Qdrant (локально, косинусная метрика) · 46 026 точек"),
    ("05", "ЗАПРОС", "векторизация вопроса + фильтр по кейсу"),
    ("06", "ПОИСК", "top-k похожих фрагментов по cosine similarity"),
    ("07", "ОТВЕТ", "Groq API / llama-3.3-70b-versatile"),
    ("08", "ВЫВОД", "ответ на русском + цитаты + [документ, стр.]")
]

_стек_технологий = [
    ("Среда", "Python 3.12", ""),
    ("Парсер PDF", "pypdf", "извлечение текста постранично"),
    ("Эмбеддинги", "sentence-transformers", "intfloat/multilingual-e5-base · 768-dim"),
    ("Векторная БД", "Qdrant", "embedded · cosine"),
    ("LLM модель", "Groq / LLaMA 3.3 70B", "versatile · temperature 0.1"),
    ("Интерфейс", "Streamlit", "wide layout · кастомный CSS"),
    ("Конфиг", "python-dotenv", "GROQ_API_KEY")
]

_описания_кейсов = {
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

_расширенные_кейсы = {
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


# =====================================================================
#  Утилиты форматирования HTML
# =====================================================================

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


# =====================================================================
#  Функции-рендереры секций
# =====================================================================

def применить_стили():
    """Подключает CSS один раз в начале страницы."""
    st.markdown(CSS_БЛОК, unsafe_allow_html=True)


def показать_шапку(документов=575, фрагментов="46 026", кейсов=15, размерность=768):
    """Навигация + hero-блок + сетка статистики."""
    html = (
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
        f'<div class="stat-item"><div class="stat-label">Документов</div><div class="stat-value">{документов}</div></div>'
        f'<div class="stat-item"><div class="stat-label">Фрагментов</div><div class="stat-value">{фрагментов}</div></div>'
        f'<div class="stat-item"><div class="stat-label">Кейсов</div><div class="stat-value">{кейсов}</div></div>'
        f'<div class="stat-item"><div class="stat-label">Размерность</div><div class="stat-value">{размерность}</div></div>'
        '</div>'
    )
    st.markdown(html, unsafe_allow_html=True)


def показать_маркизу():
    """Бегущая строка с ключевыми технологиями (двойной прогон для бесшовного цикла)."""
    html = '<div class="marquee"><div class="marquee-track">'
    for _ in range(2):
        for слово in _маркиза_слова:
            html += f'<div class="marquee-item">{слово}</div>'
    html += '</div></div>'
    st.markdown(html, unsafe_allow_html=True)


def показать_подсказку_скролла(текст="прокрутите чтобы увидеть больше", отступ_сверху_rem=None):
    """Вертикальная анимированная полоса с подписью."""
    стиль = f' style="margin-top: {отступ_сверху_rem}rem;"' if отступ_сверху_rem is not None else ''
    html = (
        f'<div class="scroll-hint"{стиль}>'
        f'<div class="scroll-hint-label">{текст}</div>'
        '<div class="scroll-hint-line"></div>'
        '</div>'
    )
    st.markdown(html, unsafe_allow_html=True)


def показать_фичи():
    """Сетка из трёх карточек с возможностями системы."""
    html = (
        '<div class="query-label-big" style="margin-bottom: 1.5rem;">Возможности системы</div>'
        '<div class="features-grid">'
    )
    for badge, icon, заголовок, описание in _фичи:
        html += (
            '<div class="feature-card">'
            f'<div class="feature-badge">{badge}</div>'
            f'<div class="feature-icon">{icon}</div>'
            f'<div class="feature-title">{заголовок}</div>'
            f'<div class="feature-desc">{описание}</div>'
            '</div>'
        )
    html += '</div>'
    st.markdown(html, unsafe_allow_html=True)


def показать_терминал():
    """Терминал-демо с scroll-pinned анимацией печати."""
    html = (
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
    st.markdown(html, unsafe_allow_html=True)


def показать_заголовок(текст, отступ_сверху_rem=None):
    """Мелкая моноширинная метка (query-label-big) перед блоком."""
    стиль = f' style="margin-top: {отступ_сверху_rem}rem;"' if отступ_сверху_rem is not None else ''
    st.markdown(f'<div class="query-label-big"{стиль}>{текст}</div>', unsafe_allow_html=True)


def показать_вертикальный_отступ(rem=1.8):
    """Пустой div заданной высоты — используется для выравнивания кнопок по сетке."""
    st.markdown(f'<div style="height: {rem}rem;"></div>', unsafe_allow_html=True)


def показать_мета_демо(название_кейса):
    """Заголовок блока ответа в демо-режиме."""
    html = (
        '<div class="answer-container">'
        '<div class="answer-meta">'
        '<span><span class="dot"></span>демо-режим</span>'
        f'<span>кейс · {название_кейса}</span>'
        '</div></div>'
    )
    st.markdown(html, unsafe_allow_html=True)


def показать_мета_rag(число_фрагментов, модель="llama-3.3-70b"):
    """Заголовок блока ответа в RAG-режиме."""
    html = (
        '<div class="answer-container">'
        '<div class="answer-meta">'
        '<span><span class="dot"></span>ответ сгенерирован</span>'
        f'<span>модель · {модель}</span>'
        f'<span>фрагментов · {число_фрагментов}</span>'
        '</div></div>'
    )
    st.markdown(html, unsafe_allow_html=True)


def показать_источники_rag(фрагменты):
    """Источники RAG-ответа: группировка по документу со списком страниц."""
    st.markdown(построить_источники_html(фрагменты), unsafe_allow_html=True)


def показать_источники_демо(источники):
    """Источники из демо-режима — плоский список строк."""
    html = ""
    for i, ист in enumerate(источники, 1):
        html += (
            f'<div class="source-row">'
            f'<span class="num">{i:02d}</span>'
            f'<span class="doc">{ист}</span>'
            f'</div>'
        )
    st.markdown(html, unsafe_allow_html=True)


def показать_кейсы(кейсы):
    """15 кейсов как expandable <details>-элементы с названием, методами и примером вопроса."""
    html = '<div class="query-label-big">15 кейсов · применение Big Data в химии</div>'
    for индекс, (ключ, данные) in enumerate(кейсы.items(), 1):
        название = данные["название"]
        описание = _описания_кейсов.get(ключ, "")
        расш = _расширенные_кейсы.get(ключ, {})
        методы_li = "".join(f"<li>{м}</li>" for м in расш.get("методы", []))
        данные_li = "".join(f"<li>{д}</li>" for д in расш.get("данные", []))
        вопрос_примера = расш.get("вопрос", "")
        развёрнутый = (
            '<div class="case-expanded">'
            '<div class="case-exp-label">Методы и подходы</div>'
            f'<ul class="case-exp-list">{методы_li}</ul>'
            '<div class="case-exp-label">Типы данных</div>'
            f'<ul class="case-exp-list">{данные_li}</ul>'
            '<div class="case-exp-label">Пример вопроса к базе</div>'
            f'<div class="case-exp-quote">«{вопрос_примера}»</div>'
            '</div>'
        )
        html += (
            '<details class="case-details">'
            '<summary>'
            f'<div class="case-num">{индекс:02d}</div>'
            f'<div><div class="case-title">{название}</div><div class="case-desc">{описание}</div></div>'
            '<div class="case-toggle">+</div>'
            '</summary>'
            f'{развёрнутый}'
            '</details>'
        )
    st.markdown(html, unsafe_allow_html=True)


def показать_архитектуру():
    """Вкладка «Архитектура»: пайплайн из 8 этапов + таблица стека."""
    html = '<div class="query-label-big">Архитектура системы · RAG-пайплайн</div>'
    for номер, тег, описание in _этапы_пайплайна:
        html += (
            '<div class="pipeline-step">'
            f'<div class="pipeline-num">{номер}</div>'
            f'<div class="pipeline-tag">{тег}</div>'
            f'<div class="pipeline-desc">{описание}</div>'
            '</div>'
        )
    st.markdown(html, unsafe_allow_html=True)

    стек_html = '<div class="query-label-big" style="margin-top: 4rem;">Технологический стек</div>'
    for ключ, значение, подсказка in _стек_технологий:
        стек_html += (
            '<div class="tech-row">'
            f'<div class="tech-key">{ключ}</div>'
            f'<div class="tech-val">{значение}<span class="hint">{подсказка}</span></div>'
            '</div>'
        )
    st.markdown(стек_html, unsafe_allow_html=True)
