# Разбор файла app.py

## Что делает этот файл

Это главный файл приложения. Он запускает веб-интерфейс на Streamlit с тремя вкладками: «Задать вопрос», «Кейсы проекта» и «Архитектура». Пользователь вводит вопрос, система ищет похожие фрагменты в Qdrant и отправляет их вместе с вопросом в Groq API — получает ответ на русском с указанием источников.

---

## Построчный разбор

### Импорты

```python
import streamlit as st
from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue
from groq import Groq
from dotenv import load_dotenv
from cases import кейсы, получить_название_кейса
from fallback_answers import заготовленные_ответы
```

**`streamlit`** — создаёт веб-интерфейс прямо из Python-кода. Кнопки, поля ввода, вкладки — всё это одна строка кода.

**`Filter, FieldCondition, MatchValue`** — типы из Qdrant для создания фильтров. Нужны чтобы искать только среди фрагментов определённого кейса.

**`Groq`** — клиент к Groq API. Отправляем вопрос + контекст, получаем ответ от языковой модели.

**`load_dotenv`** — читает файл `.env` и загружает переменные окружения (в частности `GROQ_API_KEY`).

---

## CSS-блок (оформление интерфейса)

Сразу после импортов идёт огромный вызов:

```python
st.markdown("""
<style>
...
</style>
""", unsafe_allow_html=True)
```

В нём около 200 строк CSS — всё оформление приложения. По умолчанию Streamlit выглядит довольно просто (белый фон, стандартные виджеты Material), поэтому мы переопределяем почти каждый элемент. Визуальный стиль вдохновлён `factory.ai` — строгий монохром на чёрном, моноширинные шрифты для технических подписей.

Разберу по секциям.

### 1. Шрифты и цветовые переменные

```css
@import url('https://fonts.googleapis.com/css2?family=Geist...&family=Geist+Mono...&display=swap');

:root {
    --bg: #0a0a0a;           /* почти чёрный фон */
    --bg-soft: #111111;      /* фон карточек */
    --bg-card: #141414;      /* фон при наведении */
    --border: #1f1f1f;       /* тонкие границы */
    --border-strong: #2a2a2a;/* акцентные границы */
    --text: #fafafa;         /* основной текст */
    --text-muted: #a3a3a3;   /* приглушённый */
    --text-dim: #525252;     /* самый тёмный (подписи) */
}
```

**`@import`** — подгружает с Google Fonts шрифты `Geist` (от Vercel, для заголовков и текста) и `Geist Mono` (моноширинный, для цифр и подписей). Оба бесплатные.

**`:root`** — это корневой элемент HTML. В нём определяем **CSS-переменные** (начинаются с `--`). Дальше вместо `#0a0a0a` пишем `var(--bg)` — удобно менять всю палитру в одном месте.

Три оттенка текста (`text`, `text-muted`, `text-dim`) создают визуальную иерархию: заголовок белый, описание серое, технические подписи тёмно-серые.

### 2. Базовые стили

```css
.stApp {background: var(--bg); color: var(--text); font-family: 'Geist', ...;}
#MainMenu, footer, header {visibility: hidden;}
.block-container {padding: 3rem 4rem 4rem 4rem; max-width: 1440px;}
```

**`.stApp`** — главный контейнер Streamlit. Задаём чёрный фон, белый текст, шрифт Geist.

**`#MainMenu, footer, header`** — Streamlit добавляет свои меню сверху и снизу («Made with Streamlit», гамбургер-меню). Скрываем их, чтобы интерфейс выглядел как готовое приложение, а не как прототип.

**`.block-container`** — внутренний контейнер с контентом. Задаём отступы (3rem сверху = 48px) и максимальную ширину 1440px (чтобы на больших мониторах текст не растягивался на всю ширину).

### 3. Keyframes — определения анимаций

```css
@keyframes fadeUp {from {opacity: 0; transform: translateY(16px);} to {opacity: 1; transform: translateY(0);}}
@keyframes fadeIn {from {opacity: 0;} to {opacity: 1;}}
@keyframes pulse {0%, 100% {opacity: 1; transform: scale(1);} 50% {opacity: 0.5; transform: scale(0.85);}}
@keyframes scroll {from {transform: translateX(0);} to {transform: translateX(-50%);}}
@keyframes scrollDown {0% {top: -50%;} 100% {top: 100%;}}
@keyframes blink {0%, 49% {opacity: 1;} 50%, 100% {opacity: 0;}}
```

**`@keyframes`** — описывает что происходит во время анимации. Сами по себе ничего не делают — их нужно применить через `animation: имя длительность` к конкретному элементу.

Здесь определены 9 анимаций:

- **`fadeUp`** — элемент всплывает снизу (сдвиг 16px + fade-in). Используется для hero, статов, табов.
- **`fadeIn`** — простое появление с прозрачности.
- **`pulse`** — пульсация (для зелёных точек «живой» индикации).
- **`scroll`** — горизонтальный сдвиг на -50% (для бесконечной маркизы).
- **`scrollDown`** — вертикальное движение сверху вниз (для бегущего градиента в scroll-hint).
- **`blink`** — моргание (для курсора `▊` в конце заголовка).

### 4. Герой-секция

```css
.hero-block {margin: 0 0 4rem 0; position: relative;}
.hero-block::before {
    content: "";
    position: absolute;
    top: -30px; right: -50px;
    width: 500px; height: 400px;
    background-image: radial-gradient(circle, var(--border-strong) 1px, transparent 1px);
    background-size: 22px 22px;
    opacity: 0.6;
    -webkit-mask-image: radial-gradient(ellipse at right, black 0%, transparent 70%);
}
```

**`::before`** — виртуальный элемент перед содержимым. Создаём точечный фон:

- **`radial-gradient(circle, var(--border-strong) 1px, transparent 1px)`** — один кружок диаметром 1px.
- **`background-size: 22px 22px`** — повторяем этот паттерн каждые 22px.
- **`mask-image`** — маска, которая скрывает точки по радиальному градиенту (ближе к центру — видны, по краям — исчезают). Получается «облако точек» в правом верхнем углу.

```css
.hero-title {font-size: 4.5rem; font-weight: 600; letter-spacing: -0.055em;}
.hero-title .cursor {display: inline-block; width: 4px; height: 0.9em; background: var(--text); animation: blink 1s step-start infinite;}
```

**`letter-spacing: -0.055em`** — отрицательный трекинг. Большие заголовки выглядят лучше когда буквы чуть сжаты (стандартный трюк дизайна).

**`.cursor`** — мигающий прямоугольник после заголовка. `step-start` + бесконечная анимация `blink` — даёт эффект курсора терминала.

**Staggered появление:** элементы героя появляются последовательно за счёт разных `animation-delay`:

```css
.hero-kicker {animation-delay: 0.05s;}
.hero-title  {animation-delay: 0.1s;}
.hero-desc   {animation-delay: 0.25s;}
```

### 5. Статистика (4 метрики)

```css
.stats-grid {display: grid; grid-template-columns: repeat(4, 1fr); gap: 3rem;}
.stat-value {font-size: 2.75rem; font-variant-numeric: tabular-nums;}

.stat-item:nth-child(1) .stat-label {animation-delay: 0.3s;}
.stat-item:nth-child(2) .stat-label {animation-delay: 0.4s;}
.stat-item:nth-child(3) .stat-label {animation-delay: 0.5s;}
.stat-item:nth-child(4) .stat-label {animation-delay: 0.6s;}
```

**`grid-template-columns: repeat(4, 1fr)`** — четыре равных колонки.

**`font-variant-numeric: tabular-nums`** — моноширинные цифры. В обычном шрифте `1` уже чем `8`, и числа прыгают. `tabular-nums` делает все цифры одинаковой ширины — числа в таблицах выглядят ровно.

**`:nth-child(N)`** с разными `animation-delay` — каждая карточка появляется на 0.1 секунды позже предыдущей (**staggered animation**, классический приём).

### 6. Маркиза — бесконечная прокрутка

```css
.marquee {
    overflow: hidden;
    -webkit-mask-image: linear-gradient(90deg, transparent, black 12%, black 88%, transparent);
}
.marquee-track {
    display: flex;
    animation: scroll 60s linear infinite;
    width: max-content;
}
.marquee:hover .marquee-track {animation-play-state: paused;}
```

**Как работает:** внутренний трек с технологиями шире вьюпорта в 2 раза (потому что в HTML я дублирую список два раза через цикл). Анимация `scroll` сдвигает его на -50% за 60 секунд — к моменту когда первая половина уходит влево, на её месте уже вторая копия. Зацикливание незаметно.

**`mask-image: linear-gradient(90deg, transparent, black 12%, black 88%, transparent)`** — края маркизы плавно растворяются в фоне (не обрезаются резко). Чёрный цвет в маске = видимая часть, прозрачный = скрытая.

**`:hover { animation-play-state: paused }`** — при наведении мышки маркиза замирает, чтобы можно было прочитать слова.

### 7. Scroll-hint — подсказка прокрутки

```css
.scroll-hint-line {width: 1px; height: 48px; background: var(--border-strong); position: relative; overflow: hidden;}
.scroll-hint-line::after {
    content: "";
    position: absolute;
    top: -50%; left: 0;
    width: 100%; height: 60%;
    background: linear-gradient(to bottom, transparent, var(--text));
    animation: scrollDown 2.2s ease-in-out infinite;
}
```

Вертикальная линия 1px × 48px. Внутри неё — `::after` с градиентом, который двигается сверху вниз по анимации `scrollDown` (от `top: -50%` до `top: 100%`). Создаётся эффект «бегущего огонька» вниз — подсказка пользователю, что нужно скроллить.

### 8. Табы

```css
.stTabs [data-baseweb="tab-list"] {border-bottom: 1px solid var(--border);}
.stTabs [data-baseweb="tab"] {background: transparent; color: var(--text-dim);}
.stTabs [aria-selected="true"] {color: var(--text) !important;}
.stTabs [aria-selected="true"]::after {
    content: "";
    position: absolute;
    bottom: -1px;
    height: 1px;
    background: var(--text);
    animation: slideInRight 0.3s;
}
```

Стандартные табы Streamlit переопределены до **«газетного» стиля**: просто подписи с подчёркиванием. Активная вкладка — белый текст, под ней — белая линия длиной во весь текст (через `::after`), появляющаяся с анимацией `slideInRight`.

**`[data-baseweb="tab"]`** — селектор по атрибуту. Streamlit использует библиотеку BaseWeb для виджетов, она ставит такие атрибуты на элементы.

### 9. Поля ввода и выпадающие списки

```css
.stTextArea textarea {
    background: var(--bg-soft) !important;
    border: 1px solid var(--border-strong) !important;
    border-radius: 12px !important;
    padding: 1.5rem !important;
}
.stTextArea textarea:focus {
    border-color: var(--text) !important;
    box-shadow: 0 0 0 4px rgba(250,250,250,0.05) !important;
}
```

**`!important`** — принудительно перебивает стандартные стили Streamlit (у них приоритет выше, и без `!important` нас игнорируют).

**`box-shadow` при фокусе** — классический приём: вместо кричащего синего outline ставим **мягкое 4-пиксельное свечение** вокруг поля белым цветом с прозрачностью 5%. Заметно, но не резко.

### 10. Слайдер

Самая сложная часть — Streamlit рендерит слайдер через хитрую структуру BaseWeb. Селекторы выглядят страшно, но работают:

```css
/* Сам трек (тонкая линия 3px) */
.stSlider div[style*="height: 0.25rem"] {
    height: 3px !important;
    border-radius: 2px !important;
    background: var(--border-strong) !important;
}

/* Круглый thumb */
.stSlider div[role="slider"] {
    background: var(--text) !important;
    border: 3px solid var(--bg) !important;
    width: 20px !important;
    height: 20px !important;
    border-radius: 50% !important;
    box-shadow: 0 0 0 1px var(--border-strong), 0 4px 12px rgba(0, 0, 0, 0.4) !important;
    cursor: grab !important;
}
.stSlider div[role="slider"]:hover {
    transform: translate(0, -5px) scale(1.08) !important;
    box-shadow: 0 0 0 1px var(--text), 0 0 0 6px rgba(250, 250, 250, 0.08), 0 6px 18px rgba(0, 0, 0, 0.5) !important;
}

/* Бейдж с цифрой над thumb */
.stSlider [data-testid="stSliderThumbValue"] {
    background: var(--text) !important;
    color: var(--bg) !important;
    border-radius: 6px !important;
    top: -34px !important;
}
.stSlider [data-testid="stSliderThumbValue"]::after {
    content: "";
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 4px solid var(--text);
}
```

**Селектор `div[style*="height: 0.25rem"]`** — ищет `div`, у которого в атрибуте `style` содержится строка `height: 0.25rem`. Это единственный надёжный способ найти сам трек слайдера в Streamlit, потому что классы у BaseWeb динамические (`st-emotion-cache-xxxxx`).

**Две тени у thumb:** первая — `0 0 0 1px var(--border-strong)` даёт тонкую линию по краю (как ободок), вторая — `0 4px 12px` даёт мягкую тень снизу. При hover добавляется третья тень `0 0 0 6px rgba(250, 250, 250, 0.08)` — светящееся кольцо вокруг thumb.

**Бейдж с `::after`** — стрелочка-хвостик у tooltip. Трюк через границы: элемент с нулевой шириной/высотой, у которого три прозрачные границы и одна цветная — визуально получается треугольник.

### 11. Кнопки

```css
.stButton button[kind="primary"] {
    background: var(--text);
    color: var(--bg);
    border-radius: 10px;
    position: relative;
    overflow: hidden;
}
.stButton button[kind="primary"]::before {
    content: "";
    position: absolute;
    left: -100%;
    width: 100%; height: 100%;
    background: linear-gradient(90deg, transparent, rgba(0,0,0,0.08), transparent);
    transition: left 0.6s;
}
.stButton button[kind="primary"]:hover::before {left: 100%;}
.stButton button[kind="primary"]:hover p {transform: translateX(3px);}
```

**Кнопка «Найти ответ»** — белая, с двумя эффектами при hover:

1. **Блик-полоска** — `::before` с градиентом лежит за левым краем (`left: -100%`). При hover `left: 100%` — полоска пролетает через кнопку слева направо за 0.6 секунды. Классический «shine» эффект.
2. **Текст сдвигается вправо на 3px** — тонкий намёк, что сейчас что-то произойдёт.

### 12. Ответ и источники

```css
.answer-meta .dot {
    width: 6px; height: 6px;
    background: #22c55e;
    border-radius: 50%;
    animation: pulse 2s ease-in-out infinite;
}

.source-row {
    display: flex;
    padding: 1rem 0;
    border-bottom: 1px solid var(--border);
    transition: padding-left 0.2s ease;
}
.source-row:hover {padding-left: 0.5rem;}
```

**`.dot` с анимацией pulse** — живой зелёный маркер «система отвечает». То же решение, что в статусе «система активна» в навигации.

**Трюк `transition: padding-left`** — при наведении на строку источника левый отступ увеличивается на 0.5rem. Выглядит будто строка «отъезжает» вправо навстречу курсору. Используется везде в этом проекте: в кейсах, табах, pipeline-шагах, tech-rows.

### 13. Раскрывающиеся кейсы

```css
details.case-details {border-bottom: 1px solid var(--border);}
details.case-details summary {
    list-style: none;
    cursor: pointer;
    display: grid;
    grid-template-columns: 60px 1fr 40px;
    padding: 1.75rem 0;
}
details.case-details summary::-webkit-details-marker {display: none;}

.case-toggle {
    font-size: 1.6rem;
    transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1);
    transform-origin: center;
}
details[open] .case-toggle {
    transform: rotate(45deg);
    color: var(--text);
}
```

**`<details>/<summary>`** — встроенные HTML5-теги. Клик по `<summary>` раскрывает содержимое `<details>`. JavaScript не нужен, браузер всё делает сам.

**`summary::-webkit-details-marker {display: none}`** — прячем стандартный треугольничек-маркер, который браузер добавляет автоматически. Вместо него мы рисуем свой «+» через `.case-toggle`.

**Плюс превращается в крестик:** у знака `+` в закрытом состоянии `transform` не задан. У открытого `details[open]` — `transform: rotate(45deg)`. Получается `×`. Анимация — плавная, через `cubic-bezier` easing.

### 14. Фичи-грид (3 карточки)

```css
.features-grid {display: grid; grid-template-columns: repeat(3, 1fr); gap: 1.5rem;}
.feature-card {
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 2rem;
    transition: all 0.35s cubic-bezier(0.16, 1, 0.3, 1);
    position: relative;
    overflow: hidden;
}
.feature-card::before {
    content: "";
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 1px;
    background: linear-gradient(90deg, transparent, var(--text-muted), transparent);
    opacity: 0;
}
.feature-card:hover {
    transform: translateY(-3px);
    background: var(--bg-card);
}
.feature-card:hover::before {opacity: 0.6;}
.feature-card:hover .feature-icon {
    background: var(--text);
    color: var(--bg);
}
```

Каждая карточка (Семантический поиск, Кросс-языковое сопоставление, Прозрачные источники) при hover:

- поднимается на 3px
- фон светлеет (`bg-soft` → `bg-card`)
- иконка инвертируется: белый квадрат с чёрным символом
- сверху появляется **градиентная полоска-блик** через `::before`

### 15. Терминал-демо (scroll-pinning)

Самая технологически сложная часть. Имитирует живую работу системы, но привязана к скроллу колеса мыши.

**HTML-структура:**

```html
<div class="terminal-stage">       <!-- высокий контейнер, 280vh -->
    <div class="terminal-sticky">   <!-- position: sticky, top: 8vh -->
        <div class="terminal">
            <!-- шапка с точками -->
            <!-- 8 строк .term-line.l1 … .l8 -->
        </div>
    </div>
</div>
```

**CSS:**

```css
.terminal-stage {
    height: 280vh;
    view-timeline-name: --term-scroll;
    view-timeline-axis: block;
}
.terminal-sticky {
    position: sticky;
    top: 8vh;
}

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
    /* ... до .l8 */
}
```

**Как это работает:**

1. **`terminal-stage`** — высокий контейнер 280vh (почти 3 экрана). Пользователю приходится прокрутить через него много колесом.
2. **`view-timeline-name: --term-scroll`** — объявляем **именованную шкалу времени**, привязанную к прокрутке этого контейнера через вьюпорт. Стандарт CSS Scroll-Driven Animations (2024).
3. **`position: sticky; top: 8vh`** — терминал «залипает» в 8% от верха экрана. Пока stage не доскроллен до конца, терминал не уезжает с экрана.
4. **`animation-timeline: --term-scroll`** на строках — вместо привязки к времени (0.5 секунды), анимация привязана к **позиции скролла** через stage.
5. **`animation-range: cover 5% cover 12%`** — когда stage находится на 5–12% своей «cover»-фазы (т.е. пользователь прокрутил столько), анимация `termReveal` играет от 0% до 100%.

Каждая строка занимает свой диапазон:

| Строка | Диапазон скролла | Что появляется |
|--------|------------------|----------------|
| `.l1`  | 5–12%            | `[qdrant] векторизация запроса` |
| `.l2`  | 12–19%           | `найдено 5 фрагментов · 142ms` |
| `.l3`  | 19–26%           | `[groq] llama-3.3-70b генерация` |
| `.l4`  | 26–33%           | «Выход реакции рассчитывается…» |
| `.l5`  | 33–40%           | Блок с формулой |
| `.l6`  | 40–47%           | Расшифровка переменных |
| `.l7`  | 47–54%           | Источники |
| `.l8`  | 54–62%           | Финальный промпт `> ▊` |

**Эффект:** пользователь крутит колесо — терминал стоит на месте, а строки постепенно появляются как будто система их генерирует в реальном времени. Доскроллил через всю stage — терминал «отлипает» и страница продолжает идти.

**Обратимость:** анимации на scroll-timeline **двунаправленные**. Если пользователь скроллит назад (вверх), строки исчезают в обратном порядке.

**Fallback для старых браузеров:**

```css
@supports not (animation-timeline: view()) {
    .term-line.l1 {animation-delay: 1.4s;}
    .term-line.l2 {animation-delay: 2.5s;}
    /* ... */
}
```

`@supports` проверяет поддержку CSS-свойства. Если браузер не знает `animation-timeline: view()` (Firefox, Safari на момент написания), используется обычная анимация по таймеру.

Работает нативно в Chrome/Edge 115+ (это 90%+ пользователей на 2026 год).

---

## Python-логика приложения

### Системный промпт

```python
системный_промпт = """Ты — ассистент базы знаний «Навигатор цифровой химии»...."""
```

Это инструкция для языковой модели. Она получает этот текст каждый раз при запросе. Ключевые правила:
1. Отвечать ТОЛЬКО на русском
2. Использовать ТОЛЬКО предоставленный CONTEXT (не выдумывать)
3. Указывать источники в конце
4. Если формула — вывести отдельным блоком

---

### Кэширование ресурсов

```python
@st.cache_resource
def загрузить_модель():
    return SentenceTransformer("intfloat/multilingual-e5-base")

@st.cache_resource
def загрузить_qdrant():
    папка = os.path.join(...)
    return QdrantClient(path=папка)
```

**`@st.cache_resource`** — важный декоратор Streamlit. Без него модель и база переподключались бы заново при КАЖДОМ нажатии кнопки (занимало бы 10–30 секунд). С этим декоратором они загружаются один раз и сохраняются в памяти.

---

### Функция `найти_похожие`

```python
def найти_похожие(вопрос, выбранный_кейс, количество):
    модель = загрузить_модель()
    клиент = загрузить_qdrant()
    вектор = модель.encode("query: " + вопрос, normalize_embeddings=True).tolist()
```

**`"query: " + вопрос`** — префикс `query:` обязателен для модели e5. Документы хранятся с префиксом `passage:`. Без префиксов качество поиска падает.

```python
    если_фильтр = None
    if выбранный_кейс != "все":
        если_фильтр = Filter(
            must=[FieldCondition(key="case", match=MatchValue(value=выбранный_кейс))]
        )
```

**Что это:** Если пользователь выбрал конкретный кейс (не "Все кейсы"), создаём фильтр. Qdrant вернёт только фрагменты, у которых в поле `case` стоит нужное значение.

```python
    результаты = клиент.search(
        collection_name="химия",
        query_vector=вектор,
        limit=количество,
        query_filter=если_фильтр,
        with_payload=True
    )
```

**`клиент.search`** — главный метод поиска в Qdrant. Принимает вектор вопроса, возвращает `количество` самых похожих фрагментов.

**`with_payload=True`** — вернуть не только векторы, но и метаданные (текст, документ, страница).

---

### Функция `получить_ответ_от_groq`

```python
    контекст = ""
    for i, фр in enumerate(фрагменты, 1):
        контекст += f"[{i}] Документ: {фр.payload['document']}, стр. {фр.payload['page']}\n"
        контекст += фр.payload["text"] + "\n\n"
```

**Что делает:** Собирает все найденные фрагменты в один текст. Каждый фрагмент подписан номером, именем документа и страницей.

```python
    ответ = клиент_groq.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": системный_промпт},
            {"role": "user", "content": f"CONTEXT:\n{контекст}\n\nQUESTION:\n{вопрос}"}
        ],
        temperature=0.1,
        max_tokens=1500
    )
```

**`temperature=0.1`** — почти детерминированные ответы. 0 = всегда одинаково, 1 = творчески (нам не нужно).

**`max_tokens=1500`** — ограничение длины ответа (~1000–1200 слов максимум).

**Структура запроса:** Системный промпт + пользовательское сообщение с CONTEXT и QUESTION. Модель "видит" реальные фрагменты из документов и отвечает по ним.

---

### Интерфейс: вкладки

```python
вкладка1, вкладка2, вкладка3 = st.tabs(["💬 Задать вопрос", "📚 Кейсы проекта", "🏗️ Архитектура"])
```

Создаёт три вкладки одной строкой. Пользователь переключается между ними кликом.

---

### Кнопки-примеры

```python
        if st.button(пример, key=пример, use_container_width=True):
            st.session_state["вопрос_пользователя"] = пример
```

При клике на пример вопроса он записывается в `st.session_state` — это словарь, который хранит данные между перезагрузками интерфейса. При следующем рендере поле ввода покажет этот вопрос.

---

### Демо-режим

```python
        if демо_режим:
            демо = показать_демо_ответ(вопрос_пользователя)
            st.markdown(демо["ответ"])
```

Если включён демо-режим — вместо обращения к Qdrant и Groq показываем заранее подготовленный ответ из `fallback_answers.py`. Не нужен интернет. Использовать на защите если что-то упало.

---

### Показ результатов

```python
                        for i, фр in enumerate(фрагменты, 1):
                            with st.expander(f"Фрагмент {i} — {фр.payload['document']} ..."):
                                st.markdown(f"**Релевантность:** {фр.score:.3f}")
                                st.text(фр.payload["text"][:600] + ...)
```

**`st.expander`** — сворачиваемый блок. Пользователь видит заголовок, и может раскрыть чтобы прочитать сам фрагмент из документа.

**`фр.score`** — число от 0 до 1. Показывает насколько фрагмент похож на вопрос. Выше 0.7 — очень хорошо.

**`[:600]`** — показываем только первые 600 символов (чтобы не перегружать экран).

---

## Как запустить

```
streamlit run app.py
```

Откроется браузер на `http://localhost:8501`

**Перед запуском:**
1. Заполни `.env` (GROQ_API_KEY)
2. Убедись что `qdrant_db/` существует (значит `embed_and_load.py` уже запускался)

