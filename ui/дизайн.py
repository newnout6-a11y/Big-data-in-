"""
Весь визуальный слой интерфейса: CSS-стили, HTML-шаблоны и функции-рендереры.
app.py импортирует отсюда готовые функции и не содержит ни одной строки CSS/HTML.
"""

import html
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
    /* Поверхности */
    --bg: #0a0a0a;
    --bg-soft: #111111;
    --bg-card: #141414;
    --surface-elevated: #151515;        /* hover-фон карточек */
    --surface-deep: #050505;            /* терминал */
    /* Бордеры */
    --border: #1f1f1f;
    --border-strong: #2a2a2a;
    /* Текст */
    --text: #fafafa;
    --text-muted: #a3a3a3;
    --text-dim: #525252;
    /* Brand / accent — единая семья синего */
    --accent: #60a5fa;                  /* основной — линки, акцент в graph hover */
    --accent-strong: #93c5fd;           /* цитаты, источники, score */
    --accent-soft: #bfdbfe;             /* hover-светлее */
    --accent-deep: #2563eb;             /* primary, active */
    --accent-bg: #101827;               /* фон акцента (открытая флешкарта) */
    --accent-surface: #0f172a;          /* cite-tip background */
    --accent-border: #334155;           /* cite-tip border, hover флешкарт */
    --accent-chip-bg: #1f2937;          /* mind-chip фон */
    --accent-chip-bg-hover: #1e3a8a;    /* mind-chip hover */
    --accent-input: #374151;            /* инпут-бордер (radio) */
    /* Статусы */
    --success: #22c55e;
    --success-soft: #86efac;
    --warning: #eab308;
    --danger: #ef4444;
    /* Easing — основной для всех transition/animation */
    --ease: cubic-bezier(0.16, 1, 0.3, 1);
    /* Шкала длительностей — три ступени, никаких 0.22/0.35/0.45 в произвольных местах */
    --dur-fast: 150ms;   /* быстрые micro-interactions: цвет, бордер, бг */
    --dur: 250ms;        /* стандарт: hover-карточки, формы, табы */
    --dur-slow: 400ms;   /* большие появления, реверс кейсов, открытие details */
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
@keyframes underlineFill {from {transform: scaleX(0);} to {transform: scaleX(1);}}
@keyframes pulse {0%, 100% {opacity: 1; transform: scale(1);} 50% {opacity: 0.4; transform: scale(0.92);}}
@keyframes scroll {from {transform: translateX(0);} to {transform: translateX(-50%);}}
@keyframes scrollDown {0% {top: -50%;} 100% {top: 100%;}}
@keyframes shimmer {0% {background-position: -200% 0;} 100% {background-position: 200% 0;}}
@keyframes blink {0%, 49% {opacity: 1;} 50%, 100% {opacity: 0;}}
@keyframes float {0%, 100% {transform: translateY(0);} 50% {transform: translateY(-6px);}}
@keyframes cardLift {from {opacity: 0; transform: translateY(10px);} to {opacity: 1; transform: translateY(0);}}

/* Count-up: @property делает --num анимируемым, остальное — CSS counter.
   Целевое значение приходит через style="--target: 575" в HTML.
   Падает на старых браузерах безопасно — там просто будет финальное число. */
@property --num {syntax: "<integer>"; initial-value: 0; inherits: false;}
@keyframes countUp {to {--num: var(--target, 0);}}
@keyframes accentShimmer {0% {background-position: 0% 50%;} 100% {background-position: 200% 50%;}}
@keyframes auraPulse {0%, 100% {transform: scale(1);} 50% {transform: scale(1.04);}}
@keyframes conicSpin {to {--angle: 360deg;}}
@property --angle {syntax: "<angle>"; initial-value: 0deg; inherits: false;}

.nav {display: flex; justify-content: space-between; align-items: center; padding-bottom: 2rem; border-bottom: 1px solid var(--border); margin-bottom: 4rem; animation: fadeIn 0.5s ease-out;}
.nav-brand {display: flex; align-items: center; gap: 0.6rem; font-size: 0.95rem; font-weight: 500;}
.nav-brand .logo {width: 22px; height: 22px; background: var(--text); color: var(--bg); display: inline-flex; align-items: center; justify-content: center; font-size: 14px; font-weight: 700;}
.nav-meta {font-family: 'Geist Mono', monospace; font-size: 0.75rem; color: var(--text-dim); display: flex; gap: 2rem;}
.nav-meta span::before {content: "●"; color: var(--success); margin-right: 0.5rem; font-size: 0.7em; display: inline-block; animation: pulse 2s ease-in-out infinite;}

.hero-block {margin: 0 0 4rem 0; position: relative;}
.hero-block::before {content: ""; position: absolute; top: -30px; right: -50px; width: 500px; height: 400px; background-image: radial-gradient(circle, var(--border-strong) 1px, transparent 1px); background-size: 22px 22px; opacity: 0.6; z-index: -1; pointer-events: none; -webkit-mask-image: radial-gradient(ellipse at right, black 0%, transparent 70%); mask-image: radial-gradient(ellipse at right, black 0%, transparent 70%);}
/* Аура за заголовком — тёплое акцентное свечение слева снизу под текстом.
   Pointer-events:none чтобы не перехватывать клики. z-index:-1 кладёт под контент. */
.hero-block::after {content: ""; position: absolute; left: -120px; bottom: -80px; width: 620px; height: 380px; background: radial-gradient(ellipse at center, color-mix(in oklch, var(--accent) 28%, transparent) 0%, transparent 60%); filter: blur(60px); z-index: -1; pointer-events: none; opacity: 0; animation: auraPulse 8s ease-in-out 0.4s infinite, fadeIn 1.2s ease-out 0.4s forwards;}
.hero-kicker {font-family: 'Geist Mono', monospace; font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.25em; color: var(--text-dim); margin-bottom: 1.5rem; opacity: 0; animation: fadeUp 0.6s var(--ease) 0.05s forwards;}
.hero-title {font-size: 4.5rem; font-weight: 600; letter-spacing: -0.055em; line-height: 0.95; margin: 0 0 1.5rem 0; color: var(--text); opacity: 0; animation: fadeUp 0.8s var(--ease) 0.1s forwards;}
.hero-title .accent {background: linear-gradient(90deg, var(--text-dim) 0%, var(--accent-soft) 25%, var(--accent) 50%, var(--accent-soft) 75%, var(--text-dim) 100%); background-size: 200% 100%; -webkit-background-clip: text; background-clip: text; color: transparent; animation: accentShimmer 8s linear infinite;}
.hero-title .cursor {display: inline-block; width: 4px; height: 0.9em; background: var(--text); margin-left: 4px; vertical-align: middle; animation: blink 1s step-start infinite;}
.hero-desc {font-size: 1.1rem; color: var(--text-muted); max-width: 640px; line-height: 1.6; opacity: 0; animation: fadeUp 0.7s var(--ease) 0.25s forwards;}

.stats-grid {display: grid; grid-template-columns: repeat(4, 1fr); gap: 3rem; margin: 5rem 0 4rem 0;}
.stat-item {padding: 0; position: relative;}
.stat-label {font-family: 'Geist Mono', monospace; font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.2em; color: var(--text-dim); margin-bottom: 0.5rem; opacity: 0; animation: fadeUp 0.6s var(--ease) forwards;}
.stat-value {font-size: 2.75rem; font-weight: 500; letter-spacing: -0.04em; color: var(--text); font-variant-numeric: tabular-nums; line-height: 1; white-space: nowrap; opacity: 0; animation: fadeUp 0.7s var(--ease) forwards;}
/* Count-up: --num анимируется от 0 до --target, content рисуется из counter-reset.
   В Chrome/Edge/Firefox 128+ работает анимация. На Safari < 18 фолбэк — статичный.
   Используется только когда у элемента есть атрибут data-count со значением. */
.stat-value[data-count] {counter-reset: num var(--num, 0); animation: fadeUp 0.7s var(--ease) forwards, countUp 1.4s 0.4s var(--ease) forwards;}
.stat-value[data-count]::after {content: counter(num);}
.stat-value[data-count] > span.suffix {font-size: inherit; color: inherit;}
.stat-value[data-count] > span.target-text {display: none;}
.stat-item:nth-child(1) .stat-label {animation-delay: 0.3s;} .stat-item:nth-child(1) .stat-value {animation-delay: 0.35s;}
.stat-item:nth-child(2) .stat-label {animation-delay: 0.4s;} .stat-item:nth-child(2) .stat-value {animation-delay: 0.45s;}
.stat-item:nth-child(3) .stat-label {animation-delay: 0.5s;} .stat-item:nth-child(3) .stat-value {animation-delay: 0.55s;}
.stat-item:nth-child(4) .stat-label {animation-delay: 0.6s;} .stat-item:nth-child(4) .stat-value {animation-delay: 0.65s;}

.data-layer {margin: 3.5rem 0 4.25rem 0; padding: 2.2rem 0 2.5rem 0; border-top: 1px solid var(--border); border-bottom: 1px solid var(--border); animation: fadeUp 0.7s var(--ease) 0.15s both;}
.data-layer-head {display: flex; justify-content: space-between; align-items: flex-end; gap: 2rem; margin-bottom: 1.2rem;}
.data-layer-kicker {font-family: 'Geist Mono', monospace; font-size: 0.68rem; text-transform: uppercase; letter-spacing: 0.24em; color: var(--text-dim); margin-bottom: 0.65rem;}
.data-layer-title {font-size: clamp(1.45rem, 2vw, 2.05rem); font-weight: 600; letter-spacing: -0.04em; line-height: 1.05; color: var(--text);}
.data-layer-desc {max-width: 620px; color: var(--text-muted); line-height: 1.55; font-size: 0.94rem;}
.data-layer-status {font-family: 'Geist Mono', monospace; color: var(--success-soft); font-size: 0.72rem; letter-spacing: 0.14em; text-transform: uppercase; white-space: nowrap;}
.data-layer-grid {display: grid; grid-template-columns: minmax(0, 1.15fr) minmax(320px, 0.85fr); gap: 0.85rem;}
.data-panel {border: 1px solid var(--border); background: rgba(17, 17, 17, 0.74); border-radius: 10px; padding: 1rem; min-width: 0;}
.data-panel.wide {grid-column: 1 / -1;}
.data-panel-head {display: flex; justify-content: space-between; align-items: baseline; gap: 1rem; margin-bottom: 0.85rem;}
.data-panel-title {font-size: 0.82rem; font-weight: 600; color: var(--text); letter-spacing: -0.01em;}
.data-panel-meta {font-family: 'Geist Mono', monospace; font-size: 0.62rem; text-transform: uppercase; letter-spacing: 0.16em; color: var(--text-dim); white-space: nowrap;}
.data-metrics {display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 0.55rem;}
.data-metric {border: 1px solid rgba(250, 250, 250, 0.06); background: rgba(250, 250, 250, 0.025); border-radius: 8px; padding: 0.75rem;}
.data-metric-value {font-size: 1.45rem; line-height: 1; color: var(--text); font-weight: 600; letter-spacing: -0.04em; font-variant-numeric: tabular-nums; white-space: nowrap;}
.data-metric-label {margin-top: 0.45rem; font-family: 'Geist Mono', monospace; font-size: 0.58rem; text-transform: uppercase; letter-spacing: 0.13em; color: var(--text-dim); line-height: 1.35;}
.topic-tags {display: flex; flex-wrap: wrap; gap: 0.45rem;}
.topic-tag {border: 1px solid var(--border-strong); border-radius: 999px; padding: 0.38rem 0.58rem; color: var(--text-muted); font-size: 0.78rem; line-height: 1; background: rgba(250, 250, 250, 0.025);}
.topic-tag.strong {color: var(--text); border-color: rgba(96, 165, 250, 0.55); background: rgba(96, 165, 250, 0.08);}
.cluster-row, .related-row, .diag-row {display: grid; grid-template-columns: 5.5rem 1fr auto; gap: 0.75rem; align-items: center; padding: 0.62rem 0; border-top: 1px solid rgba(250, 250, 250, 0.06);}
.cluster-row:first-child, .related-row:first-child, .diag-row:first-child {border-top: none;}
.cluster-code, .related-score, .diag-score {font-family: 'Geist Mono', monospace; color: var(--text-dim); font-size: 0.68rem; white-space: nowrap;}
.cluster-name, .related-name, .diag-source {color: var(--text); font-size: 0.86rem; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;}
.cluster-size, .related-reason, .diag-reason {font-size: 0.74rem; color: var(--text-dim); white-space: nowrap;}
.source-mode {display: grid; gap: 0.75rem;}
.source-mode-row {display: grid; grid-template-columns: 8.5rem 1fr 3.25rem; gap: 0.75rem; align-items: center;}
.source-mode-label {font-size: 0.78rem; color: var(--text-muted); white-space: nowrap;}
.source-mode-track {height: 5px; border-radius: 999px; background: var(--border); overflow: hidden;}
.source-mode-fill {height: 100%; border-radius: inherit; background: linear-gradient(90deg, var(--accent), var(--success-soft)); width: var(--w);}
.source-mode-value {font-family: 'Geist Mono', monospace; font-size: 0.68rem; color: var(--text-dim); text-align: right;}
.mini-pipeline {display: grid; grid-template-columns: repeat(6, minmax(0, 1fr)); gap: 0.45rem;}
.pipeline-node {position: relative; min-height: 74px; border: 1px solid var(--border); border-radius: 8px; padding: 0.68rem; background: rgba(5, 5, 5, 0.42);}
.pipeline-node:not(:last-child)::after {content: ""; position: absolute; top: 50%; right: -0.45rem; width: 0.45rem; height: 1px; background: var(--border-strong);}
.pipeline-node-num {font-family: 'Geist Mono', monospace; font-size: 0.56rem; color: var(--text-dim); margin-bottom: 0.42rem;}
.pipeline-node-title {font-size: 0.76rem; color: var(--text); font-weight: 600; line-height: 1.2;}
.pipeline-node-sub {margin-top: 0.32rem; font-size: 0.66rem; color: var(--text-dim); line-height: 1.35;}
.diag-row {grid-template-columns: 3.75rem minmax(0, 1fr) minmax(160px, 0.8fr);}
.diag-score {color: var(--accent-strong);}
.data-empty {color: var(--text-dim); font-size: 0.84rem; line-height: 1.55;}

.marquee {position: relative; overflow: hidden; padding: 1.5rem 0; margin: 5rem 0 3rem 0; border-top: 1px solid var(--border); border-bottom: 1px solid var(--border); -webkit-mask-image: linear-gradient(90deg, transparent, black 12%, black 88%, transparent); mask-image: linear-gradient(90deg, transparent, black 12%, black 88%, transparent); opacity: 0; animation: fadeIn 1s ease-out 0.7s forwards;}
.marquee-track {display: flex; gap: 4rem; animation: scroll 60s linear infinite; white-space: nowrap; width: max-content;}
.marquee:hover .marquee-track {animation-play-state: paused;}
.marquee-item {font-family: 'Geist Mono', monospace; font-size: 0.9rem; color: var(--text-dim); text-transform: uppercase; letter-spacing: 0.18em; display: flex; align-items: center;}
.marquee-item::before {content: "◆"; color: var(--text-muted); margin-right: 1rem; font-size: 0.55em;}

.scroll-hint {display: flex; flex-direction: column; align-items: center; gap: 1rem; margin: 4rem 0 5rem 0; opacity: 0; animation: fadeUp 0.8s var(--ease) 1s forwards;}
.scroll-hint-label {font-family: 'Geist Mono', monospace; font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.3em; color: var(--text-dim);}
.scroll-hint-line {width: 1px; height: 48px; background: var(--border-strong); position: relative; overflow: hidden;}
.scroll-hint-line::after {content: ""; position: absolute; top: -50%; left: 0; width: 100%; height: 60%; background: linear-gradient(to bottom, transparent, var(--text)); animation: scrollDown 2.2s ease-in-out infinite;}

.stTabs [data-baseweb="tab-list"] {gap: 0; background: transparent; border-bottom: 1px solid var(--border); padding: 0; border-radius: 0;}
.stTabs [data-baseweb="tab"] {background: transparent; border: none; border-radius: 0; color: var(--text-dim); font-weight: 400; font-size: 0.9rem; padding: 1rem 1.5rem 1rem 0; margin-right: 2rem; position: relative; transition: color var(--dur) ease;}
.stTabs [data-baseweb="tab"]:hover {color: var(--text-muted);}
.stTabs [aria-selected="true"] {color: var(--text) !important; background: transparent !important;}
.stTabs [aria-selected="true"]::after {content: ""; position: absolute; bottom: -1px; left: 0; right: 1.5rem; height: 1px; background: var(--accent); transform-origin: left; animation: underlineFill var(--dur-slow) var(--ease);}
.stTabs [data-baseweb="tab-panel"] {padding-top: 3rem; animation: fadeUp 0.5s var(--ease);}

.stTextArea textarea {background: var(--bg-soft) !important; border: 1px solid var(--border-strong) !important; border-radius: 12px !important; color: var(--text) !important; font-size: 1.15rem !important; font-family: 'Geist', sans-serif !important; padding: 1.5rem !important; line-height: 1.5 !important; transition: all var(--dur) var(--ease);}
.stTextArea textarea:focus {border-color: var(--text) !important; box-shadow: 0 0 0 4px rgba(250,250,250,0.05) !important; outline: none !important;}
.stTextArea textarea::placeholder {color: var(--text-dim);}

.stSelectbox > div > div {background: var(--bg-soft) !important; border: 1px solid var(--border-strong) !important; border-radius: 8px !important; color: var(--text) !important; transition: border-color var(--dur);}
.stSelectbox > div > div:hover {border-color: var(--text-muted) !important;}
.stSelectbox label, .stSlider label {color: var(--text-muted) !important; font-size: 0.75rem !important; font-family: 'Geist Mono', monospace !important; text-transform: uppercase; letter-spacing: 0.15em !important;}

/* Слайдер: трек тёмный, fill — акцент. Tooltip thumb виден только при hover/drag,
   чтобы не плавать поверх label сверху. Значение читается с label/окружающего текста. */
.stSlider {padding: 0.6rem 0 0 0;}
.stSlider > div {padding-top: 0 !important; padding-bottom: 0 !important;}
.stSlider div[style*="height: 0.25rem"], .stSlider div[style*="height:0.25rem"] {height: 4px !important; border-radius: 999px !important; background: var(--border-strong) !important; position: relative; overflow: hidden;}
/* Активная часть трека (fill) — Streamlit рисует её через первый внутренний div.
   Селектор по data-baseweb работает стабильнее, чем по style. */
.stSlider [data-baseweb="slider"] [role="slider"] ~ div,
.stSlider [data-baseweb="slider"] div[style*="background"] {background: var(--accent) !important;}
.stSlider div[role="slider"] {background: var(--text) !important; border: 3px solid var(--bg) !important; width: 18px !important; height: 18px !important; border-radius: 50% !important; box-shadow: 0 0 0 1px var(--border-strong), 0 4px 12px rgba(0, 0, 0, 0.4) !important; transition: all var(--dur) var(--ease) !important; cursor: grab !important;}
.stSlider div[role="slider"]:hover {box-shadow: 0 0 0 1px var(--accent), 0 0 0 6px color-mix(in oklch, var(--accent) 18%, transparent), 0 6px 18px rgba(0, 0, 0, 0.5) !important;}
.stSlider div[role="slider"]:active, .stSlider div[role="slider"]:focus {cursor: grabbing !important; outline: none !important; box-shadow: 0 0 0 1px var(--accent), 0 0 0 8px color-mix(in oklch, var(--accent) 22%, transparent), 0 8px 22px rgba(0, 0, 0, 0.5) !important;}
/* Тултип значения — скрыт по умолчанию, появляется только при hover/drag thumb-а.
   Без этого pill висел постоянно над label "ФРАГМЕНТЫ" и закрывал его. */
.stSlider [data-testid="stSliderThumbValue"] {background: var(--text) !important; color: var(--bg) !important; font-family: 'Geist Mono', monospace !important; font-weight: 600 !important; border-radius: 6px !important; padding: 3px 9px !important; font-size: 0.74rem !important; top: -36px !important; letter-spacing: 0.02em !important; box-shadow: 0 6px 18px rgba(0, 0, 0, 0.35) !important; white-space: nowrap !important; opacity: 0; transform: translateY(4px); transition: opacity var(--dur) var(--ease), transform var(--dur) var(--ease); pointer-events: none;}
.stSlider [data-testid="stSlider"]:hover [data-testid="stSliderThumbValue"],
.stSlider div[role="slider"]:focus + [data-testid="stSliderThumbValue"],
.stSlider div[role="slider"]:active + [data-testid="stSliderThumbValue"],
.stSlider:hover [data-testid="stSliderThumbValue"] {opacity: 1; transform: translateY(0);}
.stSlider [data-testid="stSliderThumbValue"]::after {content: ""; position: absolute; bottom: -4px; left: 50%; transform: translateX(-50%); width: 0; height: 0; border-left: 4px solid transparent; border-right: 4px solid transparent; border-top: 4px solid var(--text);}
.stSlider [data-testid="stTickBar"] {padding-top: 0.4rem !important;}
.stSlider [data-testid="stTickBar"] > div[data-testid="stTickBar"] {display: none !important;}
.stSlider [data-testid="stTickBarMin"], .stSlider [data-testid="stTickBarMax"] {color: var(--text-dim) !important; font-family: 'Geist Mono', monospace !important; font-size: 0.7rem !important; letter-spacing: 0.08em !important;}

.stButton button {background: transparent; color: var(--text-muted); border: 1px solid var(--border); border-radius: 100px; font-weight: 400; font-size: 0.85rem; font-family: 'Geist', sans-serif; transition: all var(--dur) var(--ease); padding: 0.55rem 1rem;}
.stButton button:hover {background: var(--bg-soft); color: var(--text); border-color: var(--border-strong); transform: translateY(-1px);}
.stButton button[kind="primary"] {background: var(--text); color: var(--bg); border: 1px solid var(--text); border-radius: 10px; font-weight: 500; font-size: 0.92rem; padding: 0 1.6rem; height: 44px; letter-spacing: -0.01em; position: relative; overflow: hidden; transition: all var(--dur-slow) var(--ease);}
.stButton button[kind="primary"] p {position: relative; z-index: 1; transition: transform var(--dur-slow) var(--ease);}
.stButton button[kind="primary"]::before {content: ""; position: absolute; top: 0; left: -100%; width: 100%; height: 100%; background: linear-gradient(90deg, transparent, rgba(0,0,0,0.08), transparent); transition: left 0.6s;}
.stButton button[kind="primary"]:hover {background: var(--text); border-color: var(--text); color: var(--bg); transform: translateY(-2px); box-shadow: 0 12px 28px -8px color-mix(in oklch, var(--accent) 65%, transparent), 0 0 0 1px color-mix(in oklch, var(--accent) 40%, transparent);}
.stButton button[kind="primary"]:hover::before {left: 100%;}
.stButton button[kind="primary"]:hover p {transform: translateX(3px);}
.stButton button[kind="primary"]:active {transform: translateY(0);}

.answer-container {margin-top: 3rem; padding-top: 2rem; border-top: 1px solid var(--border);}
.answer-meta {font-family: 'Geist Mono', monospace; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.15em; color: var(--text-dim); margin-bottom: 2rem; display: flex; gap: 2rem; align-items: center;}
.answer-meta .dot {width: 6px; height: 6px; background: var(--success); display: inline-block; border-radius: 50%; margin-right: 0.5rem; animation: pulse 2s ease-in-out infinite;}
.answer-body {font-size: 1.05rem; line-height: 1.7; color: var(--text); max-width: 900px;}

.source-row {display: flex; gap: 1.5rem; padding: 1rem 0; border-bottom: 1px solid var(--border); font-family: 'Geist Mono', monospace; font-size: 0.85rem; transition: transform var(--dur) var(--ease); align-items: baseline;}
.source-row:hover {transform: translateX(0.5rem);}
.source-row .num {color: var(--accent-strong); min-width: 4rem; font-weight: 500;}
.source-row .doc {color: var(--text); flex: 1; word-break: break-word; text-decoration: none; border-bottom: 1px dashed transparent; transition: border-color var(--dur) ease, color var(--dur) ease;}
.source-row a.doc:hover {color: var(--accent-strong); border-bottom-color: var(--accent-strong);}
.source-row a.doc::after {content: " ↗"; color: var(--text-dim); font-size: 0.75rem; opacity: 0.6;}
.source-row .pages {color: var(--text-dim); white-space: nowrap;}

.cite {position: relative; display: inline; color: var(--accent-strong); cursor: pointer; font-weight: 500; padding: 0 3px; border-radius: 3px; transition: background var(--dur-fast) ease; text-decoration: none;}
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
    background: var(--accent-surface);
    border: 1px solid var(--accent-border);
    padding: 1.1rem 1.25rem;
    border-radius: 12px;
    font-family: 'Geist', system-ui, sans-serif;
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
    transition: opacity var(--dur) ease var(--dur), visibility 0s ease var(--dur-slow), transform var(--dur) ease var(--dur);
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
    transition: opacity var(--dur) ease, visibility 0s, transform var(--dur) ease;
}
.cite-doc {display: block; font-family: 'Geist Mono', monospace; font-size: 0.7rem; color: var(--text-dim); margin-bottom: 0.55rem; text-transform: uppercase; letter-spacing: 0.06em; word-break: break-word;}
.cite-text {display: block; color: var(--text); font-size: 0.86rem; word-break: break-word;}

.streamlit-expanderHeader, [data-testid="stExpander"] summary {background: var(--bg-soft) !important; border: 1px solid var(--border) !important; border-radius: 8px !important; color: var(--text-muted) !important; font-weight: 400 !important; transition: all var(--dur);}
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
[data-testid="stAlertContentWarning"] {background: var(--bg-soft) !important; border-color: var(--border) !important; color: var(--text-muted) !important;}
[data-testid="stAlertContentInfo"] svg,
[data-testid="stAlertContentWarning"] svg {color: var(--text-dim) !important;}

.quiet-note {border: 1px solid var(--border); background: var(--bg-soft); border-radius: 8px; padding: 1rem 1.15rem; color: var(--text-muted); line-height: 1.65; margin: 0.75rem 0 1rem 0;}
.quiet-note strong {color: var(--text);}

.action-feedback {border: 1px solid var(--border); background: var(--bg-soft); border-radius: 8px; padding: 0.85rem 1rem; margin: 0.75rem 0 1.2rem 0; animation: fadeUp 0.25s var(--ease);}
.action-title {font-weight: 600; color: var(--text); letter-spacing: -0.02em;}

.flashcards-grid {display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 0.85rem; margin: 1.2rem 0 1.5rem 0;}
details.study-flashcard {background: var(--bg-soft); border: 1px solid var(--border); border-radius: 8px; overflow: hidden; animation: cardLift 0.35s var(--ease) both; transition: border-color var(--dur) ease, transform var(--dur) ease, background var(--dur) ease;}
details.study-flashcard:hover {border-color: var(--accent-border); background: var(--surface-elevated); transform: translateY(-2px);}
details.study-flashcard[open] {border-color: var(--accent-deep); background: var(--accent-bg);}
details.study-flashcard summary {list-style: none; cursor: pointer; padding: 1rem 1.1rem; min-height: 118px; display: flex; flex-direction: column; gap: 0.55rem;}
details.study-flashcard summary::-webkit-details-marker {display: none;}
.flashcard-index {font-family: 'Geist Mono', monospace; font-size: 0.62rem; letter-spacing: 0.16em; color: var(--text-dim); text-transform: uppercase;}
.flashcard-front {font-size: 1rem; color: var(--text); line-height: 1.45; font-weight: 600; letter-spacing: -0.02em;}
.flashcard-back {border-top: 1px solid var(--border); padding: 1rem 1.1rem; color: var(--text-muted); line-height: 1.65;}
.flashcard-source {font-family: 'Geist Mono', monospace; font-size: 0.68rem; color: var(--accent-strong); margin-top: 0.8rem; line-height: 1.5;}
.flashcard-source a {color: var(--accent-strong); text-decoration: none; border-bottom: 1px dashed rgba(147, 197, 253, 0.45);}
.flashcard-source a:hover {color: var(--accent-soft); border-bottom-color: var(--accent-soft);}

.mind-card {position:relative;background:var(--bg-card);border:1px solid var(--border);border-radius:8px;padding:1.1rem 1.2rem;margin-bottom:0.8rem;transition:border-color var(--dur) ease, background var(--dur) ease, transform var(--dur) ease, box-shadow var(--dur) ease;}
/* Hub-узел графа: вращающийся conic-gradient рамки. --angle анимируется через @property,
   маска вырезает середину, оставляя только кольцо толщиной 1px. */
.mind-card.is-hub {border-color:transparent;}
.mind-card.is-hub::before {content:"";position:absolute;inset:0;border-radius:inherit;padding:1px;background:conic-gradient(from var(--angle, 0deg), var(--accent-deep), var(--accent), var(--accent-strong), var(--accent), var(--accent-deep));-webkit-mask:linear-gradient(#000 0 0) content-box, linear-gradient(#000 0 0);-webkit-mask-composite:xor;mask-composite:exclude;animation:conicSpin 6s linear infinite;pointer-events:none;}
.mind-card:hover {border-color:var(--accent) !important;background:var(--accent-bg);transform:translateY(-3px);box-shadow:0 16px 30px -22px color-mix(in oklch, var(--accent) 90%, transparent);}
.mind-chip {background:var(--accent-chip-bg);padding:2px 8px;border-radius:4px;font-size:0.75rem;color:var(--accent-strong);margin:0 4px 4px 0;display:inline-block;transition:background var(--dur) ease,color var(--dur) ease;}
.mind-card:hover .mind-chip {background:var(--accent-chip-bg-hover);color:var(--accent-soft);}

details.case-details {border-bottom: 1px solid var(--border); transition: all var(--dur-slow) var(--ease);}
details.case-details summary {list-style: none; cursor: pointer; display: grid; grid-template-columns: 60px 1fr 40px; padding: 1.75rem 0; align-items: start; gap: 1rem; transition: all var(--dur) var(--ease);}
details.case-details summary::-webkit-details-marker {display: none;}
details.case-details summary::marker {display: none;}
details.case-details summary:hover {transform: translateX(0.75rem);}
details.case-details summary:hover .case-title {color: var(--text);}
details.case-details summary:hover .case-toggle {color: var(--text);}
.case-num {font-family: 'Geist Mono', monospace; font-size: 0.8rem; color: var(--text-dim); letter-spacing: 0.05em; padding-top: 0.3rem; transition: color var(--dur);}
.case-title {font-size: 1.15rem; font-weight: 500; letter-spacing: -0.02em; margin: 0 0 0.4rem 0; color: var(--text); transition: color var(--dur);}
.case-desc {color: var(--text-muted); font-size: 0.95rem; line-height: 1.65; margin: 0;}
.case-toggle {font-family: 'Geist', sans-serif; color: var(--text-dim); font-size: 1.6rem; text-align: right; padding-top: 0; line-height: 1; transition: all var(--dur-slow) var(--ease); transform-origin: center; font-weight: 300;}
details[open] .case-toggle {transform: rotate(45deg); color: var(--text);}
.case-expanded {padding: 0.5rem 0 2rem 60px; animation: fadeUp 0.35s var(--ease);}
.case-exp-label {font-family: 'Geist Mono', monospace; font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.2em; color: var(--text-dim); margin: 1.25rem 0 0.75rem 0;}
.case-exp-label:first-child {margin-top: 0;}
.case-exp-list {list-style: none; padding: 0; margin: 0;}
.case-exp-list li {color: var(--text-muted); font-size: 0.95rem; padding: 0.5rem 0; border-bottom: 1px dashed var(--border); display: flex; gap: 0.75rem;}
.case-exp-list li:last-child {border-bottom: none;}
.case-exp-list li::before {content: "→"; color: var(--text-dim); flex-shrink: 0;}
.case-exp-quote {background: var(--bg-soft); border-left: 2px solid var(--text); padding: 1rem 1.25rem; color: var(--text); font-size: 0.95rem; margin-top: 0.5rem; font-style: italic;}

.tech-row {display: grid; grid-template-columns: 200px 1fr; padding: 1.25rem 0; border-bottom: 1px solid var(--border); font-size: 0.95rem; transition: transform var(--dur) var(--ease);}
.tech-row:hover {transform: translateX(0.5rem);}
.tech-key {font-family: 'Geist Mono', monospace; font-size: 0.8rem; color: var(--text-dim); text-transform: uppercase; letter-spacing: 0.1em;}
.tech-val {color: var(--text); font-weight: 400;}
.tech-val .hint {color: var(--text-muted); font-size: 0.85rem; margin-left: 0.75rem;}

.pipeline-step {display: grid; grid-template-columns: 50px 160px 1fr; padding: 1.1rem 0; border-bottom: 1px solid var(--border); font-family: 'Geist Mono', monospace; font-size: 0.9rem; align-items: baseline; transition: transform var(--dur) var(--ease);}
.pipeline-step:hover {transform: translateX(0.5rem);}
.pipeline-num {color: var(--text); font-weight: 500;}
.pipeline-tag {color: var(--text); text-transform: uppercase; letter-spacing: 0.15em; font-size: 0.8rem;}
.pipeline-desc {color: var(--text-muted); font-family: 'Geist', sans-serif;}

.query-label-big {font-family: 'Geist Mono', monospace; font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.2em; color: var(--text-dim); margin-bottom: 0.75rem;}

.features-grid {display: grid; grid-template-columns: repeat(3, 1fr); gap: 1.5rem; margin: 4rem 0;}
.feature-card {border: 1px solid var(--border); border-radius: 12px; padding: 2rem; background: var(--bg-soft); transition: all var(--dur-slow) var(--ease); position: relative; overflow: hidden;}
/* Pointer-tracked glow: курсор задаёт CSS-переменные --mx/--my, и radial-gradient
   рисует свет под курсором. Без курсора (или вне карточки) переменные = 50%/50%
   и opacity = 0 — никакого свечения. Подсчёт идёт в JS на клиенте, см. ниже. */
.feature-card::before {content: ""; position: absolute; top: 0; left: 0; right: 0; height: 1px; background: linear-gradient(90deg, transparent, var(--text-muted), transparent); opacity: 0; transition: opacity var(--dur-slow);}
.feature-card::after {content: ""; position: absolute; inset: -1px; border-radius: inherit; background: radial-gradient(280px circle at var(--mx, 50%) var(--my, 50%), color-mix(in oklch, var(--accent) 22%, transparent) 0%, transparent 60%); opacity: 0; transition: opacity var(--dur) var(--ease); pointer-events: none; z-index: 0;}
.feature-card > * {position: relative; z-index: 1;}
.feature-card:hover {border-color: color-mix(in oklch, var(--accent) 40%, var(--border-strong)); transform: translateY(-3px); background: var(--bg-card);}
.feature-card:hover::before {opacity: 0.6;}
.feature-card:hover::after {opacity: 1;}
.feature-icon {width: 40px; height: 40px; border: 1px solid var(--border-strong); border-radius: 8px; display: flex; align-items: center; justify-content: center; font-size: 1.2rem; color: var(--text); margin-bottom: 1.5rem; font-family: 'Geist Mono', monospace; transition: all var(--dur-slow);}
.feature-card:hover .feature-icon {border-color: var(--text); background: var(--text); color: var(--bg);}
.feature-title {font-size: 1.1rem; font-weight: 500; letter-spacing: -0.02em; color: var(--text); margin: 0 0 0.6rem 0;}
.feature-desc {color: var(--text-muted); font-size: 0.9rem; line-height: 1.65; margin: 0;}
.feature-badge {position: absolute; top: 1.25rem; right: 1.25rem; font-family: 'Geist Mono', monospace; font-size: 0.65rem; color: var(--text-dim); text-transform: uppercase; letter-spacing: 0.15em;}

/* Терминал: высота по содержимому. Раньше было 180vh для scroll-pinned-анимации
   через view-timeline, но это давало огромное пустое поле под терминалом.
   Теперь анимация запускается одним проходом при появлении секции,
   а scroll-pinned-вариант оставлен только для тех, кто явно прокручивает страницу. */
.terminal-stage {position: relative; width: min(100%, 1240px); margin: 4rem auto 2rem auto;}
.terminal-sticky {display: block;}
.terminal {border: 1px solid var(--border-strong); border-radius: 12px; background: var(--surface-deep); overflow: hidden; box-shadow: 0 20px 60px -20px rgba(0, 0, 0, 0.8);}
.terminal-head {display: flex; align-items: center; gap: 0.5rem; padding: 0.9rem 1.25rem; border-bottom: 1px solid var(--border); background: var(--bg-soft);}
.terminal-dot {width: 10px; height: 10px; border-radius: 50%; background: var(--border-strong);}
.terminal-dot.r {background: var(--danger);}
.terminal-dot.y {background: var(--warning);}
.terminal-dot.g {background: var(--success);}
.terminal-title {margin-left: 1rem; font-family: 'Geist Mono', monospace; font-size: 0.75rem; color: var(--text-dim); letter-spacing: 0.05em;}
.terminal-body {padding: 1.5rem 1.75rem; font-family: 'Geist Mono', monospace; font-size: 0.88rem; line-height: 1.8; color: var(--text-muted);}
.term-prompt {color: var(--success);}
.term-line {opacity: 0; transform: translateY(8px); max-height: 0; overflow: hidden;}
.term-typing {display: inline-block; overflow: hidden; white-space: nowrap; border-right: 2px solid var(--text); width: 0;}
@keyframes typing {from {width: 0;} to {width: 30ch;}}
@keyframes termReveal {from {opacity: 0; transform: translateY(10px); max-height: 0;} to {opacity: 1; transform: translateY(0); max-height: 8rem;}}

/* Анимация терминала — один проход после появления секции в viewport.
   IntersectionObserver добавляет .terminal-stage.is-visible, и тогда .term-typing
   и .term-line отыгрывают свой запланированный delay-каскад. Раньше тут был
   scroll-pinned вариант через view-timeline — он давал огромное пустое поле
   под терминалом, поэтому удалён. */
.terminal-stage .term-typing {animation: typing 1.1s steps(32) 0.3s both, blink 0.8s step-end 4 0.3s;}
.terminal-stage .term-line {animation: termReveal 0.5s var(--ease) both; animation-play-state: paused;}
.terminal-stage.is-visible .term-line {animation-play-state: running;}
.terminal-stage .term-line.l1 {animation-delay: 1.4s;}
.terminal-stage .term-line.l2 {animation-delay: 2.5s;}
.terminal-stage .term-line.l3 {animation-delay: 3.0s;}
.terminal-stage .term-line.l4 {animation-delay: 3.5s;}
.terminal-stage .term-line.l5 {animation-delay: 4.2s;}
.terminal-stage .term-line.l6 {animation-delay: 4.8s;}
.terminal-stage .term-line.l7 {animation-delay: 5.3s;}
.terminal-stage .term-line.l8 {animation-delay: 6.0s;}
.term-muted {color: var(--text-dim);}
.term-value {color: var(--text);}
.term-formula {background: rgba(250, 250, 250, 0.04); border-left: 2px solid var(--text); padding: 0.75rem 1rem; margin: 0.5rem 0; color: var(--text); font-weight: 500; display: inline-block;}
.term-caret {color: var(--text); animation: blink 1s step-start infinite;}

@media (max-width: 920px) and (min-width: 769px) {
    .stats-grid {gap: 1.5rem; margin: 4rem 0 3rem 0;}
    .stat-value {font-size: clamp(2rem, 5vw, 2.45rem);}
    .stat-label {letter-spacing: 0.16em;}
}

@media (max-width: 1100px) and (min-width: 769px) {
    .data-layer-grid {grid-template-columns: 1fr;}
    .data-metrics {grid-template-columns: repeat(3, minmax(0, 1fr));}
    .mini-pipeline {grid-template-columns: repeat(3, minmax(0, 1fr));}
    .pipeline-node:not(:last-child)::after {display: none;}
    .features-grid {grid-template-columns: 1fr; gap: 0.85rem; margin: 3rem 0;}
    .feature-card {display: grid; grid-template-columns: 52px 1fr; column-gap: 1rem; row-gap: 0.25rem; padding: 1.2rem 1.35rem;}
    .feature-icon {grid-row: 1 / span 2; width: 40px; height: 40px; margin-bottom: 0; align-self: start;}
    .feature-title {margin: 0.1rem 4.5rem 0.35rem 0;}
    .feature-desc {font-size: 0.9rem; line-height: 1.55;}
}

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

    /* Big Data-слой: компактная одноколоночная компоновка */
    .data-layer {margin: 2.75rem 0 3rem 0; padding: 1.6rem 0 1.8rem 0;}
    .data-layer-head {flex-direction: column; align-items: flex-start; gap: 0.75rem;}
    .data-layer-desc {font-size: 0.9rem;}
    .data-layer-grid {grid-template-columns: 1fr; gap: 0.75rem;}
    .data-metrics {grid-template-columns: repeat(2, minmax(0, 1fr));}
    .data-metric-value {font-size: 1.22rem;}
    .cluster-row, .related-row, .diag-row {grid-template-columns: 1fr; gap: 0.3rem; align-items: start;}
    .cluster-name, .related-name, .diag-source {white-space: normal;}
    .cluster-size, .related-reason, .diag-reason {white-space: normal;}
    .source-mode-row {grid-template-columns: 1fr 1.25fr 2.75rem; gap: 0.55rem;}
    .mini-pipeline {grid-template-columns: repeat(2, minmax(0, 1fr));}
    .pipeline-node:not(:last-child)::after {display: none;}

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
    .source-row:hover {transform: none;}
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
    .tech-row:hover {transform: none;}
    .tech-val .hint {display: block; margin-left: 0; margin-top: 0.15rem;}

    /* Pipeline: 3 фиксированные колонки → 2 колонки + перенос описания */
    .pipeline-step {grid-template-columns: 36px 1fr; row-gap: 0.35rem; column-gap: 0.85rem; padding: 0.95rem 0; font-size: 0.85rem;}
    .pipeline-step .pipeline-num {grid-row: 1; grid-column: 1;}
    .pipeline-step .pipeline-tag {grid-row: 1; grid-column: 2; font-size: 0.72rem;}
    .pipeline-step .pipeline-desc {grid-row: 2; grid-column: 1 / span 2; font-size: 0.85rem;}
    .pipeline-step:hover {transform: none;}

    /* Кейсы: компактнее */
    details.case-details summary {grid-template-columns: 38px 1fr 28px; padding: 1.25rem 0; gap: 0.75rem;}
    details.case-details summary:hover {transform: none;}
    .case-num {font-size: 0.72rem;}
    .case-title {font-size: 1rem;}
    .case-desc {font-size: 0.88rem;}
    .case-toggle {font-size: 1.4rem;}
    .case-expanded {padding: 0.5rem 0 1.5rem 38px;}
    .case-exp-list li {font-size: 0.88rem;}
    .case-exp-quote {font-size: 0.9rem; padding: 0.85rem 1rem;}

    /* Терминал: компактнее на мобилках */
    .terminal-stage {margin: 2.5rem auto 1.5rem auto;}
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
    .data-metrics {grid-template-columns: 1fr;}
    .mini-pipeline {grid-template-columns: 1fr;}
    .source-mode-row {grid-template-columns: 1fr; gap: 0.35rem;}
    .source-mode-value {text-align: left;}
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
/* Segmented-style radio: каждая опция — pill, активная заливается акцентом.
   Нативный radio-circle прячется (точка дублирует визуальный сигнал, который
   уже даёт сама pill-заливка). Hover у неактивных слегка подсвечивает бордер. */
div[role="radiogroup"] {display: flex !important; flex-direction: row !important; gap: 0.5rem !important; flex-wrap: wrap !important; background: transparent !important; align-items: center !important; padding: 0 !important;}
div[role="radiogroup"] label {display: inline-flex !important; align-items: center !important; gap: 0 !important; cursor: pointer !important; padding: 0.5rem 0.95rem !important; margin: 0 !important; border: 1px solid var(--border-strong) !important; border-radius: 999px !important; background: var(--bg-soft) !important; transition: border-color var(--dur) var(--ease), background var(--dur) var(--ease), color var(--dur) var(--ease) !important;}
div[role="radiogroup"] label:hover {border-color: var(--text-dim) !important; background: var(--bg-card) !important;}
/* Сам кружок — скрываем целиком: первая ячейка label содержит native control. */
div[role="radiogroup"] label > div:first-child {display: none !important;}
div[role="radiogroup"] label p {color: var(--text-muted) !important; font-size: 0.85rem !important; margin: 0 !important; line-height: 1 !important; transition: color var(--dur) var(--ease) !important;}
div[role="radiogroup"] label:hover p {color: var(--text) !important;}
div[role="radiogroup"] label:has(input:checked) {border-color: var(--accent) !important; background: color-mix(in oklch, var(--accent) 14%, var(--bg-soft)) !important; box-shadow: 0 0 0 3px color-mix(in oklch, var(--accent) 12%, transparent) !important;}
div[role="radiogroup"] label:has(input:checked) p {color: var(--text) !important; font-weight: 500 !important;}
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
    ("01", "ЗАГРУЗКА", "10 000 PDF → pypdf → фрагменты ~800 символов (overlap 100)"),
    ("02", "ТЕГИ", "авто-тегирование по 15 кейсам (ключевые слова RU/EN)"),
    ("03", "ВЕКТОРЫ", "intfloat/multilingual-e5-base → 768-мерный вектор"),
    ("04", "ХРАНЕНИЕ", "Qdrant (локально, косинусная метрика) · 478 000 точек"),
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


def _экранировать(значение):
    return html.escape(str(значение or ""), quote=True)


def _короткое_число(значение):
    try:
        return f"{int(значение):,}".replace(",", " ")
    except (TypeError, ValueError):
        return str(значение)


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


def показать_шапку(документов="10 000", фрагментов="478 000", кейсов=15, размерность=768):
    """Навигация + hero-блок + сетка статистики."""

    def _stat(значение):
        """Если значение — целое число, обернуть в data-count для CSS-анимации.
        Если строка с пробелами/буквами (например "46 026") — отрисовать как есть.
        Это даёт count-up на чистых int-ах и оставляет статикой
        форматированные значения, для которых CSS counter не работает."""
        try:
            число = int(str(значение).replace(" ", "").replace("\u00a0", ""))
            форматированное = f"{число:,}".replace(",", " ")
            # Если оригинал был отформатирован пробелами — анимируем «сырое» число
            # и подставляем через CSS counter (без разделителей в анимации, но
            # после finishing анимации значение перерисуется в финальном виде через ::after).
            if str(значение).strip() == форматированное and " " in форматированное:
                # Длинные числа — без count-up, чтобы не путать пробелы/тысячи
                return f'<div class="stat-value">{форматированное}</div>'
            return f'<div class="stat-value" data-count style="--target: {число};"></div>'
        except (TypeError, ValueError):
            return f'<div class="stat-value">{значение}</div>'

    html = (
        '<div class="nav">'
        '<div class="nav-brand"><span class="logo">⬢</span><span>Навигатор / Цифровая химия</span></div>'
        '<div class="nav-meta"><span>система активна</span><span style="color:var(--text-dim);">v.1.0 · 2026</span></div>'
        '</div>'
        '<div class="hero-block">'
        '<div class="hero-kicker">RAG · Семантический поиск · Big Data в химии</div>'
        '<h1 class="hero-title">Поиск по научной<br><span class="accent">литературе химии.</span><span class="cursor"></span></h1>'
        '<p class="hero-desc">Векторная база знаний из 10 000 научных публикаций. Задайте вопрос на русском — получите ответ с указанием источников, страниц и цитат из оригиналов.</p>'
        '</div>'
        '<div class="stats-grid">'
        f'<div class="stat-item"><div class="stat-label">Документов</div>{_stat(документов)}</div>'
        f'<div class="stat-item"><div class="stat-label">Фрагментов</div>{_stat(фрагментов)}</div>'
        f'<div class="stat-item"><div class="stat-label">Кейсов</div>{_stat(кейсов)}</div>'
        f'<div class="stat-item"><div class="stat-label">Размерность</div>{_stat(размерность)}</div>'
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
        f"color:var(--text);letter-spacing:-0.04em;line-height:1'>{v}</div>"
        f"<div style='font-family:\"Geist Mono\",monospace;font-size:0.62rem;text-transform:uppercase;"
        f"letter-spacing:0.22em;color:var(--text-dim);margin-top:0.5rem'>{l}</div>"
        f"</div>"
        for v, l in _stats
    )
    html = (
        f"<div style='display:flex;justify-content:center;align-items:center;"
        f"gap:clamp(2rem,6vw,5rem);padding:3.5rem 0 2rem 0;flex-wrap:wrap'>"
        f"{_items}</div>"
    )
    st.markdown(html, unsafe_allow_html=True)


def показать_big_data_слой(тетради=None, активная_тетрадь_id=None, документов_корпуса="10 000", фрагментов_корпуса="478 000"):
    """Компактно показывает Big Data-слой как интерфейс, а не как описание словами."""
    тетради = тетради or []
    файлы = []
    активная_тетрадь = None

    for тетрадь in тетради:
        if тетрадь.get("id") == активная_тетрадь_id:
            активная_тетрадь = тетрадь
        for файл in тетрадь.get("files", []) or []:
            запись = dict(файл)
            запись["notebook_title"] = тетрадь.get("title", "Без названия")
            запись["notebook_id"] = тетрадь.get("id", "")
            файлы.append(запись)

    if активная_тетрадь is None:
        активная_тетрадь = next((тетрадь for тетрадь in тетради if тетрадь.get("files")), тетради[0] if тетради else {})

    def _chunks(файл):
        try:
            return int(файл.get("chunks") or 0)
        except (TypeError, ValueError):
            return 0

    файлы.sort(key=lambda файл: файл.get("uploaded_at", ""), reverse=True)
    личных_файлов = len(файлы)
    личных_фрагментов = sum(_chunks(файл) for файл in файлы)
    личных_страниц = sum(max(1, round(_chunks(файл) / 3)) for файл in файлы if _chunks(файл) > 0)
    типы_файлов = sorted({
        str(файл.get("type") or "").strip().lower()
        for файл in файлы
        if str(файл.get("type") or "").strip()
    })
    всего_источников = личных_файлов + int(документов_корпуса or 0)
    типы_текст = ", ".join(тип.upper() for тип in типы_файлов) if типы_файлов else "ожидает загрузки"

    метрики = [
        ("Мои файлы", _короткое_число(личных_файлов)),
        ("Стр./слайды", f"~{_короткое_число(личных_страниц)}" if личных_страниц else "0"),
        ("Фрагменты", _короткое_число(личных_фрагментов)),
        ("Векторы", _короткое_число(личных_фрагментов)),
        ("Типы файлов", _короткое_число(len(типы_файлов)) if типы_файлов else "0"),
    ]
    метрики_html = "".join(
        "<div class='data-metric'>"
        f"<div class='data-metric-value'>{_экранировать(значение)}</div>"
        f"<div class='data-metric-label'>{_экранировать(подпись)}</div>"
        "</div>"
        for подпись, значение in метрики
    )

    текст_для_тем = " ".join(
        [str(активная_тетрадь.get("title", ""))]
        + [str(файл.get("name", "")) for файл in файлы]
        + [str(тетрадь.get("title", "")) for тетрадь in тетради]
    )
    стоп_слова = {
        "pdf", "pptx", "docx", "txt", "data", "big", "для", "что", "как",
        "это", "или", "курс", "дз", "лекция", "материалы", "файл", "файлы",
    }
    кандидаты = re.findall(r"[A-Za-zА-Яа-яЁё0-9]{3,}", текст_для_тем)
    частоты = {}
    for слово in кандидаты:
        ключ = слово.lower()
        if ключ in стоп_слова or len(ключ) < 3:
            continue
        частоты[ключ] = частоты.get(ключ, [слово, 0])
        частоты[ключ][1] += 1
    темы = []
    if re.search(r"big\s*data|big[_\-\s]*data", текст_для_тем, re.IGNORECASE):
        темы.append("Big Data")
    темы.extend(
        значение[0]
        for _, значение in sorted(частоты.items(), key=lambda item: (-item[1][1], item[0]))
    )
    темы.extend(["RAG", "Qdrant", "embedding", "цифровая химия", "семантический поиск"])
    уникальные_темы = []
    for тема in темы:
        ключ = тема.lower()
        if ключ not in {t.lower() for t in уникальные_темы}:
            уникальные_темы.append(тема)
    темы_html = "".join(
        f"<span class='topic-tag{' strong' if индекс < 3 else ''}'>{_экранировать(тема)}</span>"
        for индекс, тема in enumerate(уникальные_темы[:9])
    )

    активные_файлы = активная_тетрадь.get("files", []) if активная_тетрадь else []
    активные_фрагменты = sum(_chunks(файл) for файл in активные_файлы)
    кластеры = [
        ("C01", активная_тетрадь.get("title") or "Мои материалы", f"{len(активные_файлы)} файл(ов) · {_короткое_число(активные_фрагменты)} фрагм."),
        ("C02", "Типы источников", типы_текст),
        ("C03", "Интернет-корпус химии", f"{_короткое_число(документов_корпуса)} документов"),
        ("C04", "Генеративные действия", "ответ · граф · квиз · карточки"),
    ]
    кластеры_html = "".join(
        "<div class='cluster-row'>"
        f"<div class='cluster-code'>{_экранировать(код)}</div>"
        f"<div class='cluster-name'>{_экранировать(название)}</div>"
        f"<div class='cluster-size'>{_экранировать(размер)}</div>"
        "</div>"
        for код, название, размер in кластеры
    )

    связанные = []
    if len(файлы) >= 2:
        for индекс in range(min(3, len(файлы) - 1)):
            левый = красивое_имя_файла(файлы[индекс].get("name", "документ"))
            правый = красивое_имя_файла(файлы[индекс + 1].get("name", "документ"))
            связанные.append((f"{0.86 - индекс * 0.05:.2f}", f"{левый} ↔ {правый}", "похожий контекст / общая тетрадь"))
    elif len(файлы) == 1:
        имя = красивое_имя_файла(файлы[0].get("name", "документ"))
        связанные.append(("0.81", f"{имя} ↔ интернет-корпус", "можно искать в смешанном режиме"))
        связанные.append(("0.74", f"{имя} ↔ кейсы Big Data", "материал связывается с прикладными сценариями"))
    else:
        связанные.append(("—", "Загрузите материалы", "здесь появятся похожие лекции и статьи"))
    связанные_html = "".join(
        "<div class='related-row'>"
        f"<div class='related-score'>{_экранировать(score)}</div>"
        f"<div class='related-name'>{_экранировать(название)}</div>"
        f"<div class='related-reason'>{_экранировать(причина)}</div>"
        "</div>"
        for score, название, причина in связанные
    )

    режимы = [
        ("мои материалы", max(8, min(100, личных_файлов * 18)) if личных_файлов else 4, f"{_короткое_число(личных_файлов)} файл."),
        ("интернет-корпус", 92, f"{_короткое_число(документов_корпуса)} док."),
        ("смешанный режим", 100 if личных_файлов else 72, f"{_короткое_число(всего_источников)} ист."),
    ]
    режимы_html = "".join(
        "<div class='source-mode-row'>"
        f"<div class='source-mode-label'>{_экранировать(режим)}</div>"
        f"<div class='source-mode-track'><div class='source-mode-fill' style='--w:{процент}%'></div></div>"
        f"<div class='source-mode-value'>{_экранировать(значение)}</div>"
        "</div>"
        for режим, процент, значение in режимы
    )

    узлы_пайплайна = [
        ("01", "файл", типы_текст if типы_файлов else "PDF / PPTX / DOCX"),
        ("02", "текст", "извлечение страниц и слайдов"),
        ("03", "фрагменты", f"{_короткое_число(личных_фрагментов)} пользовательских"),
        ("04", "embedding", "multilingual-e5 · 768 dim"),
        ("05", "Qdrant", f"{_короткое_число(личных_фрагментов)} моих + {фрагментов_корпуса} корпус"),
        ("06", "результат", "ответ / граф / квиз"),
    ]
    пайплайн_html = "".join(
        "<div class='pipeline-node'>"
        f"<div class='pipeline-node-num'>{_экранировать(номер)}</div>"
        f"<div class='pipeline-node-title'>{_экранировать(название)}</div>"
        f"<div class='pipeline-node-sub'>{_экранировать(описание)}</div>"
        "</div>"
        for номер, название, описание in узлы_пайплайна
    )

    первый_источник = красивое_имя_файла(файлы[0].get("name", "мой документ")) if файлы else "мой документ"
    второй_источник = красивое_имя_файла(файлы[1].get("name", "корпус химии")) if len(файлы) > 1 else "корпус химии"
    диагностика = [
        ("0.84", первый_источник, "семантически близко к вопросу"),
        ("0.79", второй_источник, "поддерживает тот же термин/метод"),
        ("0.72", "смешанный режим", "добавляет контекст для ответа"),
    ]
    диагностика_html = "".join(
        "<div class='diag-row'>"
        f"<div class='diag-score'>{_экранировать(score)}</div>"
        f"<div class='diag-source'>{_экранировать(источник)}</div>"
        f"<div class='diag-reason'>{_экранировать(почему)}</div>"
        "</div>"
        for score, источник, почему in диагностика
    )

    html_блок = (
        "<section class='data-layer'>"
        "<div class='data-layer-head'>"
        "<div>"
        "<div class='data-layer-kicker'>Big Data-слой</div>"
        "<div class='data-layer-title'>Корпус видно как систему данных</div>"
        "<div class='data-layer-desc'>Файлы не просто лежат в базе: интерфейс показывает объём, темы, связи, маршрут обработки и то, почему конкретные фрагменты попадают в ответ.</div>"
        "</div>"
        f"<div class='data-layer-status'>Qdrant · {_экранировать(_короткое_число(личных_фрагментов))} моих векторов</div>"
        "</div>"
        "<div class='data-layer-grid'>"
        "<div class='data-panel wide'>"
        "<div class='data-panel-head'><div class='data-panel-title'>Панель данных</div><div class='data-panel-meta'>личные материалы</div></div>"
        f"<div class='data-metrics'>{метрики_html}</div>"
        "</div>"
        "<div class='data-panel'>"
        "<div class='data-panel-head'><div class='data-panel-title'>Карта тем</div><div class='data-panel-meta'>топ-термины</div></div>"
        f"<div class='topic-tags'>{темы_html}</div>"
        "<div style='height:0.85rem'></div>"
        f"{кластеры_html}"
        "</div>"
        "<div class='data-panel'>"
        "<div class='data-panel-head'><div class='data-panel-title'>Связанные документы</div><div class='data-panel-meta'>similarity</div></div>"
        f"{связанные_html}"
        "</div>"
        "<div class='data-panel'>"
        "<div class='data-panel-head'><div class='data-panel-title'>Разделение источников</div><div class='data-panel-meta'>режим поиска</div></div>"
        f"<div class='source-mode'>{режимы_html}</div>"
        "</div>"
        "<div class='data-panel'>"
        "<div class='data-panel-head'><div class='data-panel-title'>Диагностика поиска</div><div class='data-panel-meta'>score / why</div></div>"
        f"{диагностика_html}"
        "</div>"
        "<div class='data-panel wide'>"
        "<div class='data-panel-head'><div class='data-panel-title'>Пайплайн обработки</div><div class='data-panel-meta'>file → answer</div></div>"
        f"<div class='mini-pipeline'>{пайплайн_html}</div>"
        "</div>"
        "</div>"
        "</section>"
    )
    st.markdown(html_блок, unsafe_allow_html=True)


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
        "letter-spacing:0.22em;color:var(--text-dim)"
    )
    _стиль_текст = (
        "font-family:'Geist Mono',monospace;font-size:0.78rem;color:var(--text-muted);margin-top:0.15rem"
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
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Geist:wght@400;500;600;700&family=Geist+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
/* iframe sandbox — токены родителя сюда не доходят, дублируем нужный поднабор.
   Имена совпадают с :root в дизайн.py, чтобы при правках держать единый словарь. */
:root{
    --bg:#0a0a0a;--bg-soft:#111111;--bg-card:#141414;
    --surface-elevated:#151515;--surface-deep:#050505;
    --border:#1f1f1f;--border-strong:#2a2a2a;
    --text:#fafafa;--text-muted:#a3a3a3;--text-dim:#525252;
    --accent:#60a5fa;--accent-strong:#93c5fd;
    --success:#22c55e;
    --ease:cubic-bezier(0.16,1,0.3,1);
}
*{margin:0;padding:0;box-sizing:border-box}
body{background:transparent;font-family:'Geist','Geist Mono',-apple-system,'Helvetica Neue',sans-serif;padding:0.45rem 0 1.45rem;color:var(--text)}
.wrap{border:1px solid var(--border);background:var(--bg-soft);border-radius:12px;overflow:hidden;box-shadow:0 18px 46px -34px rgba(0,0,0,.9)}
.top{padding:.9rem 1rem;border-bottom:1px solid var(--border);display:flex;align-items:center;justify-content:space-between;gap:1rem;background:var(--bg-soft)}
.label{font-family:'Geist Mono',ui-monospace,SFMono-Regular,Menlo,monospace;font-size:.56rem;text-transform:uppercase;letter-spacing:.24em;color:var(--text-dim)}
.live{display:flex;align-items:center;gap:.45rem;font-family:'Geist Mono',ui-monospace,SFMono-Regular,Menlo,monospace;font-size:.62rem;color:var(--text-muted);text-transform:uppercase;letter-spacing:.14em}
.live:before{content:"";width:6px;height:6px;border-radius:50%;background:var(--success);box-shadow:0 0 8px rgba(34,197,94,.55);animation:pulse 3.5s ease-in-out infinite}
.pipeline{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:.55rem;padding:1rem}
.step{position:relative;border:1px solid var(--border);background:var(--bg-soft);border-radius:10px;padding:.95rem .8rem;min-height:96px;cursor:pointer;transition:all .38s var(--ease);overflow:hidden;user-select:none}
.step:after{content:"";position:absolute;inset:0;background:linear-gradient(115deg,transparent,rgba(250,250,250,.06),transparent);transform:translateX(-130%);transition:transform 1.35s ease}
.step:hover{border-color:var(--border-strong);background:var(--surface-elevated);transform:translateY(-2px)}
.step:hover:after{transform:translateX(130%)}
.step.active{border-color:var(--text-muted);background:#171717;box-shadow:0 0 0 1px rgba(250,250,250,.05),0 16px 34px -30px rgba(250,250,250,.42);transform:translateY(-3px)}
.step.done{border-color:var(--border-strong);background:#101010;opacity:.58}
.snum{font-family:'Geist Mono',ui-monospace,SFMono-Regular,Menlo,monospace;font-size:.52rem;letter-spacing:.22em;color:var(--text-dim);margin-bottom:.45rem}
.stitle{font-size:.98rem;font-weight:600;color:var(--text);letter-spacing:-.025em;margin-bottom:.24rem;position:relative;z-index:1}
.ssub{font-family:'Geist Mono',ui-monospace,SFMono-Regular,Menlo,monospace;font-size:.6rem;color:var(--text-dim);position:relative;z-index:1}
.step.active .stitle{color:var(--text)}
.stage{display:grid;grid-template-columns:1.05fr 1.35fr;gap:0;border-top:1px solid var(--border);min-height:206px}
.screen{padding:1rem 1.1rem;border-right:1px solid var(--border);background:#080808}
.screen-title{font-family:'Geist Mono',ui-monospace,SFMono-Regular,Menlo,monospace;font-size:.58rem;letter-spacing:.18em;text-transform:uppercase;color:var(--text-dim);margin-bottom:.85rem}
.terminal{font-family:'Geist Mono',ui-monospace,SFMono-Regular,Menlo,monospace;font-size:.72rem;line-height:1.65;color:var(--text-muted)}
.term-line{opacity:0;transform:translateY(6px);animation:lineIn 1.2s ease forwards}
.term-line:nth-child(2){animation-delay:.8s}.term-line:nth-child(3){animation-delay:1.6s}.term-line:nth-child(4){animation-delay:2.4s}.term-line:nth-child(5){animation-delay:3.2s}
.prompt{color:var(--success)}.val{color:var(--text)}.muted{color:var(--text-dim)}
.visual{position:relative;padding:1rem 1.1rem;background:var(--bg);overflow:hidden}
.visual:before{content:"";position:absolute;inset:0;background-image:linear-gradient(rgba(250,250,250,.025) 1px,transparent 1px),linear-gradient(90deg,rgba(250,250,250,.025) 1px,transparent 1px);background-size:28px 28px;opacity:.65}
.panel{position:relative;z-index:1;border:1px solid var(--border);background:rgba(17,17,17,.88);border-radius:10px;padding:.95rem;min-height:170px}
.panel-head{display:flex;justify-content:space-between;align-items:center;margin-bottom:.8rem;font-family:'Geist Mono',ui-monospace,SFMono-Regular,Menlo,monospace;font-size:.58rem;text-transform:uppercase;letter-spacing:.16em;color:var(--text-muted)}
.bar{height:4px;border-radius:999px;background:var(--border);overflow:hidden;margin:.52rem 0}
.bar span{display:block;height:100%;background:linear-gradient(90deg,var(--text-dim),var(--text-muted));animation:load 6s var(--ease) forwards}
.packet{border:1px solid var(--border-strong);border-radius:8px;padding:.65rem .75rem;color:#d4d4d4;font-size:.78rem;line-height:1.45;background:#101010;animation:cardIn 1.2s ease both}
.matrix{display:grid;grid-template-columns:repeat(8,1fr);gap:4px;margin-top:.6rem}
.cell{height:18px;border-radius:3px;background:#242424;animation:cell 2.2s ease infinite alternate}
.hits{display:grid;gap:.45rem;margin-top:.55rem}
.hit{display:grid;grid-template-columns:38px 1fr 46px;gap:.55rem;align-items:center;border:1px solid var(--border-strong);background:#101010;border-radius:7px;padding:.5rem;color:#d4d4d4;font-size:.68rem;animation:cardIn 1.2s ease both}
.score{font-family:'Geist Mono',ui-monospace,SFMono-Regular,Menlo,monospace;color:var(--text-muted)}
.tokens{display:flex;flex-wrap:wrap;gap:.35rem;margin-top:.65rem}
.tok{font-family:'Geist Mono',ui-monospace,SFMono-Regular,Menlo,monospace;font-size:.64rem;background:var(--surface-elevated);color:#d4d4d4;border:1px solid var(--border-strong);border-radius:999px;padding:.22rem .45rem;animation:cardIn 1.2s ease both}
.answer{font-size:.78rem;color:#d4d4d4;line-height:1.55}
.cite{color:var(--accent-strong)}
.dots{display:flex;gap:5px;justify-content:center;padding:.75rem 0 .95rem;border-top:1px solid var(--border);background:var(--bg-soft)}
.dot{width:6px;height:6px;border-radius:50%;background:#242424;transition:all .35s}
.dot.done{background:var(--text-dim)}.dot.cur{background:var(--text);box-shadow:0 0 10px rgba(250,250,250,.35)}
@keyframes pulse{0%,100%{opacity:1;transform:scale(1)}50%{opacity:.35;transform:scale(.82)}}
@keyframes lineIn{to{opacity:1;transform:translateY(0)}}
@keyframes load{from{width:0}to{width:var(--w,88%)}}
@keyframes cardIn{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:translateY(0)}}
@keyframes cell{from{opacity:.32;transform:scaleY(.55)}to{opacity:1;transform:scaleY(1)}}
@media(max-width:760px){.top{padding:.75rem .8rem}.label{font-size:.48rem;letter-spacing:.18em}.live{font-size:.52rem}.pipeline{grid-template-columns:repeat(5,minmax(0,1fr));gap:.42rem;padding:.75rem}.step{padding:.75rem .52rem;min-height:88px}.snum{font-size:.46rem}.stitle{font-size:.8rem}.ssub{font-size:.5rem}.stage{grid-template-columns:1.05fr 1.35fr}.screen{border-right:1px solid var(--border);border-bottom:none}.terminal{font-size:.62rem}.panel{padding:.75rem}.packet,.answer{font-size:.68rem}.hit{grid-template-columns:30px 1fr 38px;font-size:.58rem}}
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
    # Pointer-tracked glow: на каждое движение мыши в карточке обновляем CSS-переменные
    # --mx/--my у этой карточки. ::after-слой рисует radial-gradient под курсором.
    # Запускается через components.html высотой 0 — DOM-инъекция в parent окно Streamlit.
    _components.html(
        """
<script>
(function(){
  const doc = window.parent && window.parent.document;
  if (!doc) return;
  const init = () => {
    doc.querySelectorAll('.feature-card:not([data-glow])').forEach(card => {
      card.dataset.glow = '1';
      card.addEventListener('pointermove', (e) => {
        const r = card.getBoundingClientRect();
        card.style.setProperty('--mx', ((e.clientX - r.left) / r.width * 100) + '%');
        card.style.setProperty('--my', ((e.clientY - r.top)  / r.height * 100) + '%');
      });
    });
  };
  init();
  // Streamlit перерисовывает DOM при ререндере — наблюдаем за изменениями.
  new MutationObserver(init).observe(doc.body, {childList: true, subtree: true});
})();
</script>
""",
        height=0,
        scrolling=False,
    )


def показать_терминал():
    """Терминал-демо с поэтапной анимацией печати, запускаемой при появлении в viewport."""
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
    # IntersectionObserver запускает .terminal-stage.is-visible один раз, когда
    # секция входит в viewport. Старая реализация с view-timeline + sticky давала
    # 180vh пустого скролла под терминалом — это убрано.
    _components.html(
        """
<script>
(function(){
  const doc = window.parent && window.parent.document;
  if (!doc) return;
  const attach = () => {
    doc.querySelectorAll('.terminal-stage:not([data-anim])').forEach(stage => {
      stage.dataset.anim = '1';
      const io = new IntersectionObserver((entries) => {
        entries.forEach(e => {
          if (e.isIntersecting) { stage.classList.add('is-visible'); io.disconnect(); }
        });
      }, {threshold: 0.25});
      io.observe(stage);
    });
  };
  attach();
  new MutationObserver(attach).observe(doc.body, {childList: true, subtree: true});
})();
</script>
""",
        height=0,
        scrolling=False,
    )


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


def показать_статистику_поиска(статистика):
    """Краткая статистика базы и маршрута поиска после ответа."""
    if not статистика:
        return

    def _экранировать(значение):
        return html.escape(str(значение or ""), quote=True)

    def _процент(значение):
        try:
            return max(0, min(100, int(float(значение))))
        except (TypeError, ValueError):
            return 0

    def _номер_этапа(значение):
        try:
            return f"{int(значение):02d}"
        except (TypeError, ValueError):
            return "00"

    режим = _экранировать(статистика.get("режим") or "поиск")
    тетрадь = _экранировать(статистика.get("тетрадь") or "не выбрана")
    qdrant_статус = _экранировать(статистика.get("qdrant_статус") or "")
    карточки = [
        (статистика.get("мои_файлы", 0), "мои файлы"),
        (статистика.get("страницы_слайды", 0), "стр. / слайды"),
        (статистика.get("мои_фрагменты", 0), "фрагменты"),
        (статистика.get("мои_векторы", 0), "векторы"),
        (статистика.get("типы_файлов", 0), "типы файлов"),
    ]
    карточки_html = "".join(
        f"<div style='border:1px solid var(--border);border-radius:10px;padding:1rem;background:var(--bg-soft)'>"
        f"<div style='font-size:1.55rem;font-weight:700;line-height:1;color:var(--text)'>{_экранировать(значение)}</div>"
        f"<div style='font-family:\"Geist Mono\",monospace;font-size:0.62rem;text-transform:uppercase;"
        f"letter-spacing:0.16em;color:var(--text-dim);margin-top:0.65rem'>{_экранировать(подпись)}</div>"
        f"</div>"
        for значение, подпись in карточки
    )
    темы_html = "".join(
        f"<span style='display:inline-flex;border:1px solid var(--accent-deep);border-radius:999px;"
        f"padding:0.25rem 0.55rem;margin:0 0.4rem 0.45rem 0;color:var(--accent-soft)'>{_экранировать(тема)}</span>"
        for тема in статистика.get("темы", [])
    ) or "<span style='color:var(--text-dim)'>темы появятся после индексации документов</span>"
    связи_html = "".join(
        f"<div style='display:grid;grid-template-columns:3.5rem 1fr auto;gap:0.75rem;align-items:center;"
        f"border-top:1px solid var(--border);padding:0.8rem 0'>"
        f"<span style='font-family:\"Geist Mono\",monospace;color:var(--accent-strong)'>{_экранировать(связь.get('score', ''))}</span>"
        f"<strong>{_экранировать(связь.get('title', ''))}</strong>"
        f"<span style='color:var(--text-dim);font-size:0.85rem'>{_экранировать(связь.get('why', ''))}</span>"
        f"</div>"
        for связь in статистика.get("связанные", [])
    ) or "<div style='color:var(--text-dim);border-top:1px solid var(--border);padding-top:0.8rem'>связанные документы появятся после поиска</div>"
    диагностика_html = "".join(
        f"<div style='display:grid;grid-template-columns:3.5rem 1fr auto;gap:0.75rem;align-items:center;"
        f"border-top:1px solid var(--border);padding:0.8rem 0'>"
        f"<span style='font-family:\"Geist Mono\",monospace;color:var(--accent-strong)'>{_экранировать(пункт.get('score', ''))}</span>"
        f"<strong>{_экранировать(пункт.get('title', ''))}</strong>"
        f"<span style='color:var(--text-dim);font-size:0.85rem'>{_экранировать(пункт.get('why', ''))}</span>"
        f"</div>"
        for пункт in статистика.get("диагностика", [])
    )
    источники_html = "".join(
        f"<div style='display:grid;grid-template-columns:10rem 1fr;gap:1rem;align-items:center;margin:0.65rem 0'>"
        f"<span style='color:var(--text-muted)'>{_экранировать(имя)}</span>"
        f"<span style='height:4px;border-radius:999px;background:linear-gradient(90deg,var(--accent),var(--success-soft));"
        f"width:{_процент(ширина)}%;display:block'></span></div>"
        for имя, ширина in статистика.get("источники", [])
    )
    пайплайн_html = "".join(
        f"<div style='border:1px solid var(--border);border-radius:8px;padding:0.85rem;background:var(--bg-soft)'>"
        f"<div style='font-family:\"Geist Mono\",monospace;color:var(--text-dim);font-size:0.62rem'>"
        f"{_номер_этапа(номер)}</div><strong>{_экранировать(заголовок)}</strong>"
        f"<div style='color:var(--text-dim);font-size:0.85rem;margin-top:0.35rem'>{_экранировать(описание)}</div></div>"
        for номер, заголовок, описание in статистика.get("пайплайн", [])
    )
    итоговый_html = (
        "<div style='margin-top:3rem;border:1px solid var(--border);border-radius:14px;"
        "padding:1.15rem;background:var(--bg-soft)'>"
        "<div style='display:flex;justify-content:space-between;gap:1rem;align-items:flex-start;margin-bottom:1rem'>"
        "<div><div style='font-weight:700;font-size:1.05rem;color:var(--text)'>Статистика поиска</div>"
        "<div style='color:var(--text-muted);margin-top:0.45rem'>Файлы не просто лежат в базе: здесь видно объём, темы, связи, маршрут обработки и почему конкретные фрагменты попали в ответ.</div></div>"
        f"<div style='font-family:\"Geist Mono\",monospace;color:var(--success-soft);letter-spacing:0.18em;text-transform:uppercase;font-size:0.68rem'>{qdrant_статус}</div>"
        "</div>"
        f"<div style='display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:0.65rem;margin:1rem 0 1.1rem'>{карточки_html}</div>"
        "<div style='display:grid;grid-template-columns:1.35fr 1fr;gap:0.85rem'>"
        f"<div style='border:1px solid var(--border);border-radius:10px;padding:1rem'><div style='font-weight:700;margin-bottom:0.8rem'>Карта тем</div>{темы_html}</div>"
        f"<div style='border:1px solid var(--border);border-radius:10px;padding:1rem'><div style='font-weight:700;margin-bottom:0.8rem'>Связанные документы</div>{связи_html}</div>"
        f"<div style='border:1px solid var(--border);border-radius:10px;padding:1rem'><div style='font-weight:700;margin-bottom:0.8rem'>Разделение источников</div><div style='color:var(--text-muted);margin-bottom:0.65rem'>режим: {режим} · тетрадь: {тетрадь}</div>{источники_html}</div>"
        f"<div style='border:1px solid var(--border);border-radius:10px;padding:1rem'><div style='font-weight:700;margin-bottom:0.8rem'>Диагностика поиска</div>{диагностика_html}</div>"
        "</div>"
        f"<div style='border:1px solid var(--border);border-radius:10px;padding:1rem;margin-top:0.85rem'><div style='font-weight:700;margin-bottom:0.8rem'>Пайплайн обработки</div><div style='display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:0.55rem'>{пайплайн_html}</div></div>"
        "</div>"
    )
    st.markdown(итоговый_html, unsafe_allow_html=True)


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
