"""
Весь визуальный слой интерфейса: CSS-стили, HTML-шаблоны и функции-рендереры.
app.py импортирует отсюда готовые функции и не содержит ни одной строки CSS/HTML.
"""

import re
import streamlit as st
import streamlit.components.v1 as _components


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
    --accent: #60a5fa;
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
@keyframes cardLift {from {opacity: 0; transform: translateY(10px);} to {opacity: 1; transform: translateY(0);}}

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
.stTabs [aria-selected="true"]::after {content: ""; position: absolute; bottom: -1px; left: 0; right: 1.5rem; height: 1px; background: var(--accent); animation: slideInRight 0.3s cubic-bezier(0.16, 1, 0.3, 1);}
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
.stSlider div[role="slider"]:hover {box-shadow: 0 0 0 1px var(--text), 0 0 0 8px rgba(250, 250, 250, 0.1), 0 6px 18px rgba(0, 0, 0, 0.5) !important;}
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
.source-row .num {color: #93c5fd; min-width: 4rem; font-weight: 500;}
.source-row .doc {color: var(--text); flex: 1; word-break: break-word; text-decoration: none; border-bottom: 1px dashed transparent; transition: border-color 0.2s ease, color 0.2s ease;}
.source-row a.doc:hover {color: #93c5fd; border-bottom-color: #93c5fd;}
.source-row a.doc::after {content: " ↗"; color: var(--text-dim); font-size: 0.75rem; opacity: 0.6;}
.source-row .pages {color: var(--text-dim); white-space: nowrap;}

.cite {position: relative; display: inline; color: #93c5fd; cursor: pointer; font-weight: 500; padding: 0 3px; border-radius: 3px; transition: background 0.15s ease; text-decoration: none;}
.cite:hover {background: rgba(147, 197, 253, 0.22); box-shadow: 0 0 0 1px rgba(147, 197, 253, 0.4);}
/* Тултип цитаты — position: fixed в правом нижнем углу viewport.
   Раньше был position: absolute привязанный к маркеру, но тогда:
   - При маркере близко к правому краю — тултип обрезался справа.
   - При маркере в верхней части страницы — тултип обрезался сверху.
   - При длинной цитате — нельзя было прокрутить (gap между маркером
     и тултипом курсор пересекал, hover терялся).

   Fixed-positioning в углу viewport решает все три проблемы:
   тултип всегда полностью виден, не зависит от расположения маркера,
   pointer-events: auto при hover работает корректно. Подсветка
   маркера (box-shadow + bg) даёт визуальную обратную связь, что
   именно эта цитата сейчас открыта. */
.cite-tip {
    visibility: hidden;
    opacity: 0;
    position: fixed;
    bottom: 2rem;
    right: 2rem;
    top: auto;
    left: auto;
    width: 420px;
    max-width: calc(100vw - 4rem);
    max-height: min(60vh, 480px);
    overflow-y: auto;
    background: #0f172a;
    border: 1px solid #334155;
    padding: 1.1rem 1.25rem;
    border-radius: 12px;
    font-family: 'Inter', system-ui, sans-serif;
    font-weight: 400;
    color: var(--text);
    line-height: 1.55;
    box-shadow: 0 24px 48px -8px rgba(0, 0, 0, 0.7), 0 0 0 1px rgba(147, 197, 253, 0.08);
    z-index: 1000;
    pointer-events: none;
    text-align: left;
    transform: translateY(8px);
    /* transition-delay 0.25s ТОЛЬКО при скрытии — даёт время перевести курсор
       с маркера на тултип. Появление мгновенное (delay 0s в hover-правиле).
       Без этого тултип закрывался бы сразу при уходе курсора с маркера, и
       прокрутить или выделить текст в тултипе было бы невозможно. */
    transition: opacity 0.2s ease 0.25s, visibility 0s ease 0.45s, transform 0.2s ease 0.25s;
}
/* Двойной триггер: тултип видим если курсор на маркере ИЛИ на самом тултипе.
   Работает потому что при position: fixed тултип получает свои hover-события
   независимо от родителя. transition-delay: 0s — появление без задержки. */
.cite:hover .cite-tip,
.cite-tip:hover {
    visibility: visible;
    opacity: 1;
    pointer-events: auto;
    transform: translateY(0);
    transition: opacity 0.2s ease, visibility 0s, transform 0.2s ease;
}
.cite-doc {display: block; font-family: 'Geist Mono', monospace; font-size: 0.7rem; color: var(--text-dim); margin-bottom: 0.55rem; text-transform: uppercase; letter-spacing: 0.06em; word-break: break-word;}
.cite-text {display: block; color: var(--text); font-size: 0.86rem; word-break: break-word;}

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
div[data-testid="stAlert"] > div,
[data-testid="stAlertContainer"],
[data-testid="stAlertContentInfo"],
[data-testid="stAlertContentWarning"] {background: #111 !important; border-color: var(--border) !important; color: var(--text-muted) !important;}
[data-testid="stAlertContentInfo"] svg,
[data-testid="stAlertContentWarning"] svg {color: var(--text-dim) !important;}

.quiet-note {border: 1px solid var(--border); background: #111; border-radius: 8px; padding: 1rem 1.15rem; color: var(--text-muted); line-height: 1.65; margin: 0.75rem 0 1rem 0;}
.quiet-note strong {color: var(--text);}

.action-feedback {border: 1px solid var(--border); background: #111; border-radius: 8px; padding: 0.85rem 1rem; margin: 0.75rem 0 1.2rem 0; animation: fadeUp 0.25s cubic-bezier(0.16, 1, 0.3, 1);}
.action-title {font-weight: 600; color: var(--text); letter-spacing: -0.02em;}

.flashcards-grid {display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 0.85rem; margin: 1.2rem 0 1.5rem 0;}
details.study-flashcard {background: var(--bg-soft); border: 1px solid var(--border); border-radius: 8px; overflow: hidden; animation: cardLift 0.35s cubic-bezier(0.16, 1, 0.3, 1) both; transition: border-color 0.22s ease, transform 0.22s ease, background 0.22s ease;}
details.study-flashcard:hover {border-color: #334155; background: #151515; transform: translateY(-2px);}
details.study-flashcard[open] {border-color: #2563eb; background: #101827;}
details.study-flashcard summary {list-style: none; cursor: pointer; padding: 1rem 1.1rem; min-height: 118px; display: flex; flex-direction: column; gap: 0.55rem;}
details.study-flashcard summary::-webkit-details-marker {display: none;}
.flashcard-index {font-family: 'Geist Mono', monospace; font-size: 0.62rem; letter-spacing: 0.16em; color: var(--text-dim); text-transform: uppercase;}
.flashcard-front {font-size: 1rem; color: var(--text); line-height: 1.45; font-weight: 600; letter-spacing: -0.02em;}
.flashcard-back {border-top: 1px solid var(--border); padding: 1rem 1.1rem; color: var(--text-muted); line-height: 1.65;}
.flashcard-source {font-family: 'Geist Mono', monospace; font-size: 0.68rem; color: #93c5fd; margin-top: 0.8rem; line-height: 1.5;}
.flashcard-source a {color: #93c5fd; text-decoration: none; border-bottom: 1px dashed rgba(147, 197, 253, 0.45);}
.flashcard-source a:hover {color: #bfdbfe; border-bottom-color: #bfdbfe;}

.mind-card {background:#141414;border:1px solid #222;border-radius:8px;padding:1.1rem 1.2rem;margin-bottom:0.8rem;transition:border-color 0.22s ease, background 0.22s ease, transform 0.22s ease, box-shadow 0.22s ease;}
.mind-card.is-hub {border-color:#2563eb;}
.mind-card:hover {border-color:#60a5fa !important;background:#101827;transform:translateY(-3px);box-shadow:0 16px 30px -22px rgba(96,165,250,0.9);}
.mind-chip {background:#1f2937;padding:2px 8px;border-radius:4px;font-size:0.75rem;color:#93c5fd;margin:0 4px 4px 0;display:inline-block;transition:background 0.2s ease,color 0.2s ease;}
.mind-card:hover .mind-chip {background:#1e3a8a;color:#bfdbfe;}

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

/* ============================================================
   Адаптация для мобильных и планшетов
   Главные принципы: уменьшить padding, схлопнуть многоколоночные
   гриды в 1-2 колонки, уменьшить размеры шрифтов, разрешить
   горизонтальный скролл для tabs.
   ============================================================ */

@media (max-width: 768px) {
    /* Контейнер: минимальные поля */
    .block-container {padding: 1.25rem 1rem 2rem 1rem !important;}

    /* Навигация: вертикально */
    .nav {flex-direction: column; align-items: flex-start; gap: 0.85rem; padding-bottom: 1.25rem; margin-bottom: 2.25rem;}
    .nav-meta {gap: 1.25rem; font-size: 0.7rem; flex-wrap: wrap;}

    /* Hero: меньше шрифт, прячем фон-точки */
    .hero-block {margin: 0 0 2.5rem 0;}
    .hero-block::before {display: none;}
    .hero-kicker {font-size: 0.6rem; letter-spacing: 0.18em; margin-bottom: 1rem;}
    .hero-title {font-size: 2.4rem; line-height: 1.05; margin: 0 0 1.1rem 0;}
    .hero-desc {font-size: 0.95rem; line-height: 1.55;}

    /* Статистика: 4 → 2 колонки */
    .stats-grid {grid-template-columns: repeat(2, 1fr); gap: 1.5rem 1.25rem; margin: 3rem 0 2.5rem 0;}
    .stat-value {font-size: 1.85rem;}
    .stat-label {font-size: 0.65rem; letter-spacing: 0.16em;}

    /* Маркиза */
    .marquee {margin: 3rem 0 2rem 0; padding: 1.1rem 0;}
    .marquee-track {gap: 2.5rem;}
    .marquee-item {font-size: 0.72rem; letter-spacing: 0.12em;}
    .marquee-item::before {margin-right: 0.6rem;}

    /* Подсказка скролла */
    .scroll-hint {margin: 2rem 0 3rem 0;}
    .scroll-hint-line {height: 36px;}

    /* Tabs: горизонтальный скролл вместо обрезки */
    .stTabs [data-baseweb="tab-list"] {overflow-x: auto; flex-wrap: nowrap; -webkit-overflow-scrolling: touch; scrollbar-width: none;}
    .stTabs [data-baseweb="tab-list"]::-webkit-scrollbar {display: none;}
    .stTabs [data-baseweb="tab"] {padding: 0.85rem 0; margin-right: 1.5rem; font-size: 0.85rem; white-space: nowrap; flex-shrink: 0;}
    .stTabs [aria-selected="true"]::after {right: 0;}
    .stTabs [data-baseweb="tab-panel"] {padding-top: 2rem;}

    /* Формы */
    .stTextArea textarea {font-size: 1rem !important; padding: 1.1rem !important;}
    .stButton button[kind="primary"] {height: 48px; width: 100%; padding: 0 1.4rem;}
    .stSelectbox label, .stSlider label {font-size: 0.7rem !important;}

    /* Ответ */
    .answer-container {margin-top: 2.25rem; padding-top: 1.6rem;}
    .answer-meta {font-size: 0.68rem; gap: 1rem; flex-wrap: wrap; margin-bottom: 1.5rem;}
    .answer-body {font-size: 0.98rem; line-height: 1.65;}

    /* Источники: вертикальная компоновка чтобы длинные имена не обрезались */
    .source-row {flex-direction: column; align-items: flex-start; gap: 0.35rem; padding: 0.85rem 0; font-size: 0.78rem;}
    .source-row:hover {padding-left: 0;}
    .source-row .num {min-width: auto;}
    .source-row .pages {white-space: normal;}

    /* Тултипы цитат на мобильном: position: fixed по центру viewport.
       Раньше при position: absolute с left: -10px тултип уходил за правый
       край экрана, если маркер стоит ближе к концу строки. position: fixed
       привязывает тултип к viewport, а не к маркеру — обрезка невозможна.
       Стрелочку прячем: с fixed-positioning она бы указывала никуда.
       pointer-events: auto обязательно — иначе на тачскрине палец проходит
       сквозь тултип и его нельзя прокрутить если контент длиннее экрана. */
    .cite-tip {
        position: fixed !important;
        top: 50% !important;
        bottom: auto !important;
        left: 0.75rem !important;
        right: 0.75rem !important;
        width: auto !important;
        max-width: none !important;
        transform: translateY(-50%) !important;
        max-height: 75vh !important;
        overflow-y: auto !important;
        pointer-events: auto !important;
        -webkit-overflow-scrolling: touch !important;
        font-size: 0.88rem;
        padding: 1rem 1.1rem;
    }
    .cite-tip::after {display: none !important;}

    /* Фичи: 3 → 1 колонка */
    .features-grid {grid-template-columns: 1fr; gap: 1rem; margin: 2.5rem 0;}
    .feature-card {padding: 1.5rem;}
    .feature-icon {width: 36px; height: 36px; margin-bottom: 1.1rem;}
    .flashcards-grid {grid-template-columns: 1fr;}
    details.study-flashcard summary {min-height: auto;}

    /* Tech-row: 2 фиксированные колонки → 1 колонка с двумя строками */
    .tech-row {grid-template-columns: 1fr; padding: 0.95rem 0; gap: 0.35rem;}
    .tech-row:hover {padding-left: 0;}
    .tech-val .hint {display: block; margin-left: 0; margin-top: 0.15rem;}

    /* Pipeline: 3 фиксированные колонки → 2 колонки + перенос описания */
    .pipeline-step {grid-template-columns: 36px 1fr; row-gap: 0.35rem; column-gap: 0.85rem; padding: 0.95rem 0; font-size: 0.85rem;}
    .pipeline-step .pipeline-num {grid-row: 1; grid-column: 1;}
    .pipeline-step .pipeline-tag {grid-row: 1; grid-column: 2; font-size: 0.72rem;}
    .pipeline-step .pipeline-desc {grid-row: 2; grid-column: 1 / span 2; font-size: 0.85rem;}
    .pipeline-step:hover {padding-left: 0;}

    /* Кейсы: компактнее */
    details.case-details summary {grid-template-columns: 38px 1fr 28px; padding: 1.25rem 0; gap: 0.75rem;}
    details.case-details summary:hover {padding-left: 0;}
    .case-num {font-size: 0.72rem;}
    .case-title {font-size: 1rem;}
    .case-desc {font-size: 0.88rem;}
    .case-toggle {font-size: 1.4rem;}
    .case-expanded {padding: 0.5rem 0 1.5rem 38px;}
    .case-exp-list li {font-size: 0.88rem;}
    .case-exp-quote {font-size: 0.9rem; padding: 0.85rem 1rem;}

    /* Терминал: меньше высота для scroll-pinned анимации */
    .terminal-stage {height: 200vh;}
    .terminal-sticky {top: 5vh;}
    .terminal-head {padding: 0.7rem 1rem;}
    .terminal-title {font-size: 0.7rem; margin-left: 0.6rem;}
    .terminal-body {padding: 1rem 1.1rem; font-size: 0.78rem; line-height: 1.7;}
    .term-formula {padding: 0.6rem 0.8rem; font-size: 0.85rem;}

    /* Streamlit-экспандеры */
    .streamlit-expanderHeader p, [data-testid="stExpander"] summary p {font-size: 0.78rem !important;}
    .streamlit-expanderContent, [data-testid="stExpander"] [data-testid="stExpanderDetails"] {padding: 1rem !important;}

    hr {margin: 1.75rem 0 !important;}
}

/* Совсем узкие телефоны (≤ 480px) */
@media (max-width: 480px) {
    .hero-title {font-size: 2rem;}
    .stat-value {font-size: 1.6rem;}
    .feature-card {padding: 1.25rem;}
    .case-title {font-size: 0.95rem;}
    .case-desc {font-size: 0.85rem;}
}

/* Русификация загрузчика файлов */
[data-testid="stFileUploaderDropzoneInstructions"] span:first-child {font-size: 0;}
[data-testid="stFileUploaderDropzoneInstructions"] span:first-child::after {content: "Перетащите файлы сюда"; font-size: 1rem; color: var(--text); font-family: 'Geist', sans-serif;}
[data-testid="stFileUploaderDropzoneInstructions"] span:last-child {font-size: 0;}
[data-testid="stFileUploaderDropzoneInstructions"] span:last-child::after {content: "До 200 МБ · PDF, DOCX, TXT, MD, PPTX"; font-size: 0.8rem; color: var(--text-dim); font-family: 'Geist Mono', monospace;}
[data-testid="stFileUploaderDropzone"] [data-testid="stBaseButton-secondary"],
[data-testid="stFileUploaderDropzone"] [data-testid="stBaseButton-secondary"] p,
[data-testid="stFileUploaderDropzone"] [data-testid="stBaseButton-secondary"] span {color: transparent !important;}
[data-testid="stFileUploaderDropzone"] [data-testid="stBaseButton-secondary"] {position: relative !important;}
[data-testid="stFileUploaderDropzone"] [data-testid="stBaseButton-secondary"]::before {content: "Выбрать файлы"; position: absolute; left: 50%; top: 50%; transform: translate(-50%, -50%); color: var(--text-muted); font-size: 0.85rem; white-space: nowrap; pointer-events: none;}

/* Единый стиль предупреждений */
[data-testid="stAlertContainer"] [data-baseweb="notification"] {background-color: var(--bg-soft) !important; border-left-color: var(--border-strong) !important;}
[data-testid="stAlertContentWarning"] {background-color: transparent !important;}
[data-testid="stAlertContentWarning"] svg {color: var(--text-dim) !important;}
[data-testid="stAlertContentWarning"] p, [data-testid="stAlertContentWarning"] div {color: var(--text-muted) !important;}
[data-testid="stGraphVizChart"] {background: transparent !important; border-radius: 10px; overflow: hidden; width: 100% !important;}
[data-testid="stGraphVizChart"] svg {background: transparent !important; width: 100% !important; height: auto !important; max-width: 100% !important;}
div[role="radiogroup"] {display: flex !important; flex-direction: row !important; gap: 0.6rem !important; flex-wrap: wrap !important; background: transparent !important; align-items: center !important;}
div[role="radiogroup"] label {display: flex !important; align-items: center !important; gap: 0.55rem !important; cursor: pointer !important; padding: 0.3rem 0 !important; margin: 0 !important;}
div[role="radiogroup"] label > div:first-child {flex-shrink: 0 !important;}
div[role="radiogroup"] label > div:first-child * {background: transparent !important; border-color: #374151 !important; box-shadow: none !important; outline: none !important;}
div[role="radiogroup"] label > div:first-child > div {width: 17px !important; height: 17px !important; border-radius: 50% !important; border: 2px solid #374151 !important; background: transparent !important; display: flex !important; align-items: center !important; justify-content: center !important; transition: border-color 0.25s ease !important; box-shadow: none !important;}
div[role="radiogroup"] label > div:first-child > div > div {width: 7px !important; height: 7px !important; border-radius: 50% !important; background: transparent !important; transition: background 0.25s ease !important; border: none !important;}
div[role="radiogroup"] label:has(input:checked) > div:first-child > div {border-color: #2563eb !important; box-shadow: 0 0 0 3px rgba(37,99,235,0.15) !important;}
div[role="radiogroup"] label:has(input:checked) > div:first-child > div > div {background: #2563eb !important;}
div[role="radiogroup"] label p {color: var(--text-dim) !important; font-size: 0.85rem !important; margin: 0 !important; transition: color 0.2s ease !important;}
div[role="radiogroup"] label:has(input:checked) p {color: #f0f0f0 !important;}
</style>
"""


# =====================================================================
#  Данные для визуальных блоков (только отображение)
# =====================================================================

_маркиза_слова = [
    "multilingual-e5-base", "Qdrant · векторная БД", "LLaMA 3.3 70B", "Groq API",
    "QSAR модели", "GNN · графовые нейросети", "Байесовская оптимизация",
    "SMILES · InChI", "Косинусная близость", "768-мерный вектор",
    "RAG-поиск", "Молекулярные отпечатки", "DECIMER · OSR",
    "Активное обучение", "Программные сенсоры", "Open Reaction Database"
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

def ссылка_на_scholar(имя_файла):
    """Делает ссылку на Google Scholar по имени документа.
    Комиссия может проверить что статья реально существует."""
    from urllib.parse import quote_plus
    основа = имя_файла
    for расширение in (".pdf", ".docx", ".doc"):
        if основа.lower().endswith(расширение):
            основа = основа[: -len(расширение)]
            break
    запрос = основа.replace("_", " ").replace("-", " ").strip()
    return f"https://scholar.google.com/scholar?q={quote_plus(запрос)}"


def красивое_имя_файла(имя):
    """Убирает .pdf, подчёркивания, лишние тире — делает заголовок читаемым."""
    без_расширения = имя[:-4] if имя.lower().endswith(".pdf") else имя
    чистое = без_расширения.replace("_", " ").replace("--", " — ")
    чистое = re.sub(r"\s+", " ", чистое).strip()
    if len(чистое) > 80:
        чистое = чистое[:77] + "…"
    return чистое


def построить_источники_html(фрагменты):
    """Группирует фрагменты по документу. В первой колонке вместо порядкового
    номера показывает список номеров маркеров [N] из этой группы — чтобы у
    каждого маркера в тексте была видимая строка-подтверждение в источниках,
    даже когда несколько маркеров ведут на один и тот же документ."""
    группы = {}
    порядок = []
    for номер_маркера, фр in enumerate(фрагменты, 1):
        имя = фр["document"]
        стр = фр["page"]
        if имя not in группы:
            группы[имя] = {"страницы": [], "маркеры": [], "url": фр.get("citation_url")}
            порядок.append(имя)
        if стр not in группы[имя]["страницы"]:
            группы[имя]["страницы"].append(стр)
        группы[имя]["маркеры"].append(номер_маркера)
        if not группы[имя].get("url") and фр.get("citation_url"):
            группы[имя]["url"] = фр.get("citation_url")

    строки = ""
    for док in порядок:
        страницы = ", ".join(str(p) for p in sorted(группы[док]["страницы"]))
        маркеры = ", ".join(str(n) for n in группы[док]["маркеры"])
        имя = красивое_имя_файла(док)
        url = группы[док].get("url") or ссылка_на_scholar(док)
        title = "Открыть документ" if группы[док].get("url") else "Открыть в Google Scholar"
        строки += (
            f'<div class="source-row">'
            f'<span class="num">[{маркеры}]</span>'
            f'<a class="doc" href="{url}" target="_blank" rel="noopener" '
            f'title="{title}">{имя}</a>'
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


def показать_статистику():
    """Строка ключевых цифр корпуса между маркизой и фичами."""
    _stats = [
        ("48 K+", "химических статей"),
        ("70B", "параметров в LLM"),
        ("Hybrid", "поисковый движок"),
        ("Auto", "сбор данных"),
    ]
    _items = "".join(
        f"<div style='text-align:center'>"
        f"<div style='font-family:\"Geist Mono\",monospace;font-size:2.2rem;font-weight:700;"
        f"color:#fafafa;letter-spacing:-0.04em;line-height:1'>{v}</div>"
        f"<div style='font-family:\"Geist Mono\",monospace;font-size:0.62rem;text-transform:uppercase;"
        f"letter-spacing:0.22em;color:#525252;margin-top:0.5rem'>{l}</div>"
        f"</div>"
        for v, l in _stats
    )
    html = (
        f"<div style='display:flex;justify-content:center;align-items:center;"
        f"gap:clamp(2rem,6vw,5rem);padding:3.5rem 0 2rem 0;flex-wrap:wrap'>"
        f"{_items}</div>"
    )
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


def показать_переход():
    """Трёхколоночный блок: шаги → скролл-хинт → возможности."""
    _шаги = [
        ("01", "Загрузи документы"),
        ("02", "Задай вопрос"),
        ("03", "Исследуй граф"),
    ]
    _фичи = [
        ("RAG", "поиск по корпусу"),
        ("Quiz", "интерактивный квиз"),
        ("Graph", "граф концептов"),
    ]
    _стиль_метка = (
        "font-family:'Geist Mono',monospace;font-size:0.6rem;text-transform:uppercase;"
        "letter-spacing:0.22em;color:#525252"
    )
    _стиль_текст = (
        "font-family:'Geist Mono',monospace;font-size:0.78rem;color:#a3a3a3;margin-top:0.15rem"
    )
    _лево = "".join(
        f"<div style='text-align:right;margin-bottom:1.4rem'>"
        f"<div style='{_стиль_метка}'>{n}</div>"
        f"<div style='{_стиль_текст}'>{t}</div>"
        f"</div>"
        for n, t in _шаги
    )
    _право = "".join(
        f"<div style='text-align:left;margin-bottom:1.4rem'>"
        f"<div style='{_стиль_метка}'>{n}</div>"
        f"<div style='{_стиль_текст}'>{t}</div>"
        f"</div>"
        for n, t in _фичи
    )
    html = (
        f"<div style='display:grid;grid-template-columns:1fr auto 1fr;gap:3rem;"
        f"align-items:center;padding:3rem 2rem;margin-top:3rem'>"
        f"<div style='display:flex;flex-direction:column;align-items:flex-end'>{_лево}</div>"
        f"<div class='scroll-hint' style='margin:0'>"
        f"<div class='scroll-hint-label'>попробуйте сами ↓</div>"
        f"<div class='scroll-hint-line'></div>"
        f"</div>"
        f"<div style='display:flex;flex-direction:column;align-items:flex-start'>{_право}</div>"
        f"</div>"
    )
    st.markdown(html, unsafe_allow_html=True)


def показать_пайплайн():
    """Интерактивная схема RAG-пайплайна с анимацией по клику."""
    _html = """
<!DOCTYPE html><html><head><meta charset="utf-8">
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{background:transparent;font-family:Inter,-apple-system,'Helvetica Neue',sans-serif;padding:0.45rem 0 1.45rem;color:#fafafa}
.wrap{border:1px solid #222;background:#0b0b0b;border-radius:12px;overflow:hidden;box-shadow:0 18px 46px -34px rgba(0,0,0,.9)}
.top{padding:.9rem 1rem;border-bottom:1px solid #1f1f1f;display:flex;align-items:center;justify-content:space-between;gap:1rem;background:#0d0d0d}
.label{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:.56rem;text-transform:uppercase;letter-spacing:.24em;color:#525252}
.live{display:flex;align-items:center;gap:.45rem;font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:.62rem;color:#737373;text-transform:uppercase;letter-spacing:.14em}
.live:before{content:"";width:6px;height:6px;border-radius:50%;background:#22c55e;box-shadow:0 0 8px rgba(34,197,94,.55);animation:pulse 3.5s ease-in-out infinite}
.pipeline{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:.55rem;padding:1rem}
.step{position:relative;border:1px solid #1f1f1f;background:#111;border-radius:10px;padding:.95rem .8rem;min-height:96px;cursor:pointer;transition:all .38s cubic-bezier(.16,1,.3,1);overflow:hidden;user-select:none}
.step:after{content:"";position:absolute;inset:0;background:linear-gradient(115deg,transparent,rgba(250,250,250,.06),transparent);transform:translateX(-130%);transition:transform 1.35s ease}
.step:hover{border-color:#2a2a2a;background:#151515;transform:translateY(-2px)}
.step:hover:after{transform:translateX(130%)}
.step.active{border-color:#737373;background:#171717;box-shadow:0 0 0 1px rgba(250,250,250,.05),0 16px 34px -30px rgba(250,250,250,.42);transform:translateY(-3px)}
.step.done{border-color:#2a2a2a;background:#101010;opacity:.58}
.snum{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:.52rem;letter-spacing:.22em;color:#525252;margin-bottom:.45rem}
.stitle{font-size:.98rem;font-weight:700;color:#e5e7eb;letter-spacing:-.025em;margin-bottom:.24rem;position:relative;z-index:1}
.ssub{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:.6rem;color:#5f5f5f;position:relative;z-index:1}
.step.active .stitle{color:#fafafa}
.stage{display:grid;grid-template-columns:1.05fr 1.35fr;gap:0;border-top:1px solid #1f1f1f;min-height:206px}
.screen{padding:1rem 1.1rem;border-right:1px solid #1f1f1f;background:#080808}
.screen-title{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:.58rem;letter-spacing:.18em;text-transform:uppercase;color:#525252;margin-bottom:.85rem}
.terminal{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:.72rem;line-height:1.65;color:#a3a3a3}
.term-line{opacity:0;transform:translateY(6px);animation:lineIn 1.2s ease forwards}
.term-line:nth-child(2){animation-delay:.8s}.term-line:nth-child(3){animation-delay:1.6s}.term-line:nth-child(4){animation-delay:2.4s}.term-line:nth-child(5){animation-delay:3.2s}
.prompt{color:#22c55e}.val{color:#e5e7eb}.muted{color:#525252}
.visual{position:relative;padding:1rem 1.1rem;background:#0a0a0a;overflow:hidden}
.visual:before{content:"";position:absolute;inset:0;background-image:linear-gradient(rgba(250,250,250,.025) 1px,transparent 1px),linear-gradient(90deg,rgba(250,250,250,.025) 1px,transparent 1px);background-size:28px 28px;opacity:.65}
.panel{position:relative;z-index:1;border:1px solid #222;background:rgba(17,17,17,.88);border-radius:10px;padding:.95rem;min-height:170px}
.panel-head{display:flex;justify-content:space-between;align-items:center;margin-bottom:.8rem;font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:.58rem;text-transform:uppercase;letter-spacing:.16em;color:#a3a3a3}
.bar{height:4px;border-radius:999px;background:#1f1f1f;overflow:hidden;margin:.52rem 0}
.bar span{display:block;height:100%;background:linear-gradient(90deg,#525252,#a3a3a3);animation:load 6s cubic-bezier(.16,1,.3,1) forwards}
.packet{border:1px solid #2a2a2a;border-radius:8px;padding:.65rem .75rem;color:#d4d4d4;font-size:.78rem;line-height:1.45;background:#101010;animation:cardIn 1.2s ease both}
.matrix{display:grid;grid-template-columns:repeat(8,1fr);gap:4px;margin-top:.6rem}
.cell{height:18px;border-radius:3px;background:#242424;animation:cell 2.2s ease infinite alternate}
.hits{display:grid;gap:.45rem;margin-top:.55rem}
.hit{display:grid;grid-template-columns:38px 1fr 46px;gap:.55rem;align-items:center;border:1px solid #2a2a2a;background:#101010;border-radius:7px;padding:.5rem;color:#d4d4d4;font-size:.68rem;animation:cardIn 1.2s ease both}
.score{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;color:#a3a3a3}
.tokens{display:flex;flex-wrap:wrap;gap:.35rem;margin-top:.65rem}
.tok{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:.64rem;background:#151515;color:#d4d4d4;border:1px solid #2a2a2a;border-radius:999px;padding:.22rem .45rem;animation:cardIn 1.2s ease both}
.answer{font-size:.78rem;color:#d4d4d4;line-height:1.55}
.cite{color:#93c5fd}
.dots{display:flex;gap:5px;justify-content:center;padding:.75rem 0 .95rem;border-top:1px solid #1f1f1f;background:#0b0b0b}
.dot{width:6px;height:6px;border-radius:50%;background:#242424;transition:all .35s}
.dot.done{background:#525252}.dot.cur{background:#fafafa;box-shadow:0 0 10px rgba(250,250,250,.35)}
@keyframes pulse{0%,100%{opacity:1;transform:scale(1)}50%{opacity:.35;transform:scale(.82)}}
@keyframes lineIn{to{opacity:1;transform:translateY(0)}}
@keyframes load{from{width:0}to{width:var(--w,88%)}}
@keyframes cardIn{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:translateY(0)}}
@keyframes cell{from{opacity:.32;transform:scaleY(.55)}to{opacity:1;transform:scaleY(1)}}
@media(max-width:760px){.pipeline{grid-template-columns:1fr}.stage{grid-template-columns:1fr}.screen{border-right:none;border-bottom:1px solid #1f1f1f}}
</style></head><body>
<div class="wrap">
  <div class="top"><div class="label">архитектура · RAG-пайплайн · нажми на шаг</div><div class="live">демо запущено</div></div>
  <div class="pipeline" id="pl"></div>
  <div class="stage">
    <div class="screen"><div class="screen-title">журнал выполнения</div><div class="terminal" id="log"></div></div>
    <div class="visual"><div class="panel" id="panel"></div></div>
  </div>
  <div class="dots" id="dots"></div>
</div>
<script>
const S=[
  {n:'01',t:'Запрос',s:'вопрос пользователя',h:'входной запрос',log:['> Какая формула выхода реакции?','нормализация: русский текст, 42 символа','маршрут: химия + документы'],panel:'<div class="panel-head"><span>сырой запрос</span><span>0 мс</span></div><div class="packet">Какая формула выхода реакции?</div><div class="bar" style="--w:72%"><span></span></div><div class="packet muted">удалены лишние пробелы · выбран режим поиска · запрос подготовлен</div>'},
  {n:'02',t:'Эмбеддинг',s:'multilingual-e5',h:'кодирование',log:['загрузка: intfloat/multilingual-e5-base','запрос превращается в 768-мерный вектор','нормализация вектора для cosine similarity'],panel:'<div class="panel-head"><span>вектор запроса</span><span>768 измерений</span></div><div class="packet">запрос: Какая формула выхода реакции?</div><div class="matrix">'+Array.from({length:32},(_,i)=>`<div class="cell" style="animation-delay:${i*0.025}s"></div>`).join('')+'</div><div class="bar" style="--w:91%"><span></span></div>'},
  {n:'03',t:'Поиск',s:'Qdrant top-k',h:'поиск',log:['коллекция: тетрадь + корпус','HNSW-поиск по косинусной близости','возвращены top-k фрагменты: 5'],panel:'<div class="panel-head"><span>найденные фрагменты</span><span>142 мс</span></div><div class="hits"><div class="hit"><span>[1]</span><span>фрагмент из документа · страница из индекса</span><span class="score">0.84</span></div><div class="hit"><span>[2]</span><span>фрагмент из документа · страница из индекса</span><span class="score">0.79</span></div><div class="hit"><span>[3]</span><span>фрагмент из документа · страница из индекса</span><span class="score">0.73</span></div></div>'},
  {n:'04',t:'Генерация',s:'LLaMA 3.3 70B',h:'синтез ответа',log:['сбор контекста: вопрос + 5 фрагментов','модель: llama-3.3-70b-versatile','ответ формируется с маркерами цитат'],panel:'<div class="panel-head"><span>контекст в модель</span><span>5 фрагментов</span></div><div class="tokens"><span class="tok">ВОПРОС</span><span class="tok">[1] формула</span><span class="tok">[2] определение</span><span class="tok">правила ответа</span><span class="tok">только с цитатами</span></div><div class="bar" style="--w:86%"><span></span></div><div class="packet">модель собирает ответ только из найденного контекста</div>'},
  {n:'05',t:'Ответ',s:'цитаты и страницы',h:'интерфейс',log:['проверка маркеров [N]','подстановка документов и страниц','отрисовка ответа и источников'],panel:'<div class="panel-head"><span>готовый ответ</span><span>интерфейс</span></div><div class="answer">Ответ получает маркеры <span class="cite">[N]</span>, а интерфейс подставляет документ и страницу из найденного фрагмента.</div><div class="hits"><div class="hit"><span>[N]</span><span>открыть реальный источник</span><span class="score">ссылка</span></div></div>'}
];
let tmr=null;
const pl=document.getElementById('pl'),log=document.getElementById('log'),panel=document.getElementById('panel'),dts=document.getElementById('dots');
S.forEach((s,i)=>{
  const d=document.createElement('div');d.className='step';d.id='s'+i;
  d.innerHTML=`<div class="snum">${s.n}</div><div class="stitle">${s.t}</div><div class="ssub">${s.s}</div>`;
  d.onclick=()=>go(i);pl.appendChild(d);
  const dt=document.createElement('div');dt.className='dot';dt.id='d'+i;dts.appendChild(dt);
});
function reset(){S.forEach((_,i)=>{document.getElementById('s'+i).className='step';document.getElementById('d'+i).className='dot';});}
function render(i){
  const s=S[i];
  log.innerHTML=s.log.map((x,k)=>`<div class="term-line"><span class="${k===0?'prompt':'muted'}">${k===0?'':'['+s.h+'] '}</span><span class="val">${x}</span></div>`).join('');
  panel.innerHTML=s.panel;
}
function go(from){
  if(tmr)clearTimeout(tmr);
  reset();
  function tick(i){
    if(i>=S.length){tmr=setTimeout(()=>go(0),1600);return;}
    if(i>from){document.getElementById('s'+(i-1)).className='step done';document.getElementById('d'+(i-1)).className='dot done';}
    document.getElementById('s'+i).className='step active';
    document.getElementById('d'+i).className='dot cur';
    render(i);
    tmr=setTimeout(()=>tick(i+1),6750);
  }
  tick(from);
}
go(0);
</script></body></html>
"""
    _components.html(_html, height=440, scrolling=False)


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


def показать_анимацию_действия(заголовок, шаги):
    """Короткая визуальная обратная связь после действия пользователя."""
    st.markdown(
        '<div class="action-feedback">'
        f'<div class="action-title">{заголовок}</div>'
        '</div>',
        unsafe_allow_html=True,
    )


def показать_тихую_заметку(текст):
    """Нейтральная заметка вместо яркого Streamlit alert."""
    st.markdown(f'<div class="quiet-note">{текст}</div>', unsafe_allow_html=True)


def прокрутить_к_якорю(anchor_id):
    """Плавно прокручивает страницу Streamlit к уже отрисованному HTML-якорю."""
    safe_id = re.sub(r"[^a-zA-Z0-9_\-]", "", str(anchor_id or ""))
    if not safe_id:
        return
    _components.html(
        f"""
<script>
const go = () => {{
  const doc = window.parent.document;
  const el = doc.getElementById("{safe_id}");
  if (el) el.scrollIntoView({{behavior: "smooth", block: "start"}});
}};
setTimeout(go, 80);
setTimeout(go, 360);
</script>
""",
        height=1,
        scrolling=False,
    )


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
