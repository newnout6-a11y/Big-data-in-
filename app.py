import math
import os
import re
import json
from datetime import datetime

import streamlit as st
from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue, Range
from groq import Groq
from dotenv import load_dotenv

import дизайн
from cases import кейсы, получить_название_кейса
from fallback_answers import заготовленные_ответы
from taxonomy import ДОМЕНЫ, название_домена, название_субдомена
from классификатор import (
    подготовить_прототипы,
    проверить_scope,
    примеры_in_scope_вопросов,
    SCOPE_ПОРОГ_ПО_УМОЛЧАНИЮ,
)

load_dotenv()

st.set_page_config(
    page_title="Навигатор цифровой химии",
    page_icon="⬢",
    layout="wide",
    initial_sidebar_state="collapsed"
)

дизайн.применить_стили()


системный_промпт = """Ты — ассистент базы знаний «Навигатор цифровой химии».

Правила:
1. Отвечай ТОЛЬКО на русском языке, даже если CONTEXT на английском.
2. Используй только факты из CONTEXT ниже. Не придумывай.
3. Если в CONTEXT есть хотя бы частичная информация по вопросу — ОБЯЗАТЕЛЬНО дай развёрнутый ответ на её основе, перечисли все релевантные методы, молекулы, формулы, определения, подходы из контекста. Отвечай активно: если есть хоть одна формула, одно определение, один факт по теме — используй его в ответе. Не отказывайся без крайней нужды.
4. ВАЖНО про маркеры: в CONTEXT каждый фрагмент начинается с метки вида «[1] Документ: …» — это МОИ нумерованные метки для цитирования, НЕ библиография и НЕ список литературы. Всегда смотри на САМ ТЕКСТ фрагмента после метки. Отказ по правилу 5 возможен ТОЛЬКО если внутри всех фрагментов нет ничего кроме плоских списков литературы вида «Smith J. // Nature. 2020. V. 45. P. 123» или «Крупнов А.А. // Кинетика и катализ. 2019. Т. 60. С. 181» — то есть когда текст фрагмента состоит из авторов, журналов и страниц без содержательных утверждений.
5. Если CONTEXT содержательно не относится к вопросу (говорит о принципиально другой теме без единой формулы или факта по вопросу) — скажи: «В базе нет данных для ответа на этот вопрос» — и на этом остановись, больше ничего не добавляй.
6. Химические термины и названия методов оставляй в оригинале и давай русский перевод в скобках при первом упоминании.
7. ОБЯЗАТЕЛЬНО ставь маркер [N] сразу после каждого утверждения в теле ответа, где N — номер фрагмента из CONTEXT, из которого взят факт. Один маркер — на одно предложение или короткий абзац. Можно ставить несколько маркеров [1][3], если факт подтверждается двумя фрагментами. Без маркеров ответ считается неполным. ВАЖНО: маркер ставь ТОЛЬКО на конкретный факт, формулу, число, термин или цитату — НЕ ставь маркер на общие фразы-связки типа «Формула имеет вид», «Рассмотрим подробнее», «Это применяется для...», «Аналогично...», «Таким образом...». Перед тем как поставить [N], мысленно убедись, что в фрагменте N действительно содержится именно это утверждение или формула — если не уверен, лучше не ставь маркер совсем, чем поставь неточный.
8. НЕ добавляй в конец ответа раздел «Источники:» — система отрисует его сама из метаданных фрагментов. Просто пиши маркеры [N] по тексту.
9. Главные формулы (определения, ключевые уравнения, формулы из условия) ОБЯЗАТЕЛЬНО оборачивай в БЛОЧНЫЕ двойные доллары $$...$$ — каждая на отдельной строке с пустыми строками до и после. Inline-доллары $...$ используй ТОЛЬКО для одиночных коротких символов внутри текста (одна переменная $\\eta$, $m_i$, $\\sigma$, индекс или греческая буква). КАТЕГОРИЧЕСКИ НЕ ставь главную формулу inline — она будет сжата в строку и нечитаема. Используй ТОЛЬКО стандартный LaTeX-синтаксис: \\sigma вместо σ, \\sum_{i=1}^{n} вместо ∑, \\in вместо ∈, \\mathcal{N}(v) для множеств, h^{(t+1)}_v для индексов и степеней, \\cdot вместо *, \\frac{a}{b} для дробей. Не используй Unicode-математику и псевдо-LaTeX типа h_v^(t+1).
10. ЗАПРЕЩЕНО приводить формулы, уравнения и численные константы, которых НЕТ в CONTEXT — даже если ты эту формулу знаешь из общих знаний. Если формулы в CONTEXT нет, опиши процесс словами или скажи: «Формула для этого в найденных фрагментах не приведена». Каждая формула в ответе должна быть подкреплена маркером [N] из CONTEXT, где она реально присутствует."""


@st.cache_resource
def загрузить_модель():
    return SentenceTransformer("intfloat/multilingual-e5-base")


@st.cache_resource
def загрузить_qdrant():
    папка = os.path.join(os.path.dirname(os.path.abspath(__file__)), "qdrant_db")
    return QdrantClient(path=папка)


@st.cache_resource
def выбрать_коллекцию():
    """Выбираем активную коллекцию: knowledge (новая схема) > химия (старая)."""
    клиент = загрузить_qdrant()
    try:
        имена = {к.name for к in клиент.get_collections().collections}
    except Exception:
        имена = set()
    if "knowledge" in имена:
        return "knowledge", True
    return "химия", False


@st.cache_resource
def прототипы_доменов():
    модель = загрузить_модель()
    return подготовить_прототипы(модель)


def похоже_на_библиографию(текст):
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


_МУСОРНЫЕ_МАРКЕРЫ = (

    "licensed under a creative commons",
    "creativecommons.org/licenses",
    "view article online",
    "cc by license",
    "cc by-nc",
    "all rights reserved",
    "rights reserved",
    "published by elsevier",
    "open access article",
    "this journal is ©",
    "this is an open access",

    "научно-технический вестник",
    "scientific and technical journal",
    "scientific and technical bulletin",
    "issn 2",
    "issn 0",
    "issn 1",
    "doi: 10.",

    "поступила в редакцию",
    "принята к печати",
    "адрес для переписки",
    "received:",
    "accepted:",
    "corresponding author",

    "конфликт интересов",
    "конфликта интересов",
    "conflict of interest",
    "competing interests",
    "финансирование исследования",
    "благодарности.",
    "acknowledgments",
    "acknowledgements",

    "список литературы",
    "references",
    "библиографический список",
)


_PDF_ЗАМЕНЫ = (
    ("¼", "="),
    ("þ", "+"),
    ("ð", "("),
    ("Þ", ")"),
    ("¦", "|"),
    ("\u00ad", ""),
    ("\ufb01", "fi"),
    ("\ufb02", "fl"),
)


def почистить_pdf_артефакты(текст):
    if not текст:
        return текст
    для_замены = текст
    for плохой, хороший in _PDF_ЗАМЕНЫ:
        для_замены = для_замены.replace(плохой, хороший)
    return для_замены


def похоже_на_мусор(текст):
    т = текст.lower().strip()
    if len(т) < 60:
        return True
    if any(маркер in т for маркер in _МУСОРНЫЕ_МАРКЕРЫ):
        return True

    числовых = sum(1 for с in т if с.isdigit() or с in " .,()/-+|")
    if числовых / len(т) > 0.45:
        return True


    слова_букв = re.findall(r"[а-яёa-z]{3,}", т)
    длина_букв = sum(len(с) for с in слова_букв)
    if длина_букв / len(т) < 0.40:
        return True
    return False


def _вынести_маркеры_из_формул(текст):
    def обработать_блок(m):
        блок = m.group(0)
        маркеры = re.findall(r"\[\d+\]", блок)
        if not маркеры:
            return блок


        чистый = re.sub(r"\[\d+\]", "", блок)
        return чистый + "".join(маркеры)


    текст = re.sub(r"\$\$.+?\$\$", обработать_блок, текст, flags=re.DOTALL)
    текст = re.sub(r"\$[^$\n]+?\$", обработать_блок, текст)
    return текст


def вставить_цитаты_в_ответ(текст, фрагменты):
    if not фрагменты:
        return текст


    очищенный = re.sub(
        r"\n+\s*(?:#+\s+)?\*?\*?(?:Источники|Sources|References)\s*:?\*?\*?\s*[:\n].*$",
        "",
        текст,
        flags=re.IGNORECASE | re.DOTALL,
    ).rstrip()


    очищенный = _вынести_маркеры_из_формул(очищенный)


    безопасный = (
        очищенный.replace("&", "&amp;")
                 .replace("<", "&lt;")
                 .replace(">", "&gt;")
    )

    def _экранировать_атрибут(s):
        return (s.replace("&", "&amp;")
                 .replace("<", "&lt;")
                 .replace(">", "&gt;")
                 .replace('"', "&quot;")
                 .replace("\n", " ")
                 .strip())

    def замена(совпадение):
        n = int(совпадение.group(1))
        if not (1 <= n <= len(фрагменты)):
            return совпадение.group(0)
        фр = фрагменты[n - 1]
        полный_текст = фр.get("text", "") if isinstance(фр, dict) else фр.payload.get("text", "")
        документ = фр.get("document", "") if isinstance(фр, dict) else фр.payload.get("document", "")
        страница = фр.get("page", "") if isinstance(фр, dict) else фр.payload.get("page", "")
        цитата = полный_текст[:800]
        if len(полный_текст) > 800:
            цитата += "…"
        doc_attr = _экранировать_атрибут(f"{документ}, стр. {страница}")
        text_attr = _экранировать_атрибут(цитата)
        return (
            f'<span class="cite">'
            f'[{n}]'
            f'<span class="cite-tip">'
            f'<span class="cite-doc">{doc_attr}</span>'
            f'<span class="cite-text">{text_attr}</span>'
            f'</span></span>'
        )

    return re.sub(r"\[(\d+)\]", замена, безопасный)


def _построить_фильтр(выбранный_кейс, домен=None, субдомен=None, год_от=None, язык=None, источник=None):
    must = []
    if выбранный_кейс and выбранный_кейс != "все":
        must.append(FieldCondition(key="case", match=MatchValue(value=выбранный_кейс)))
    if домен and домен != "все":
        must.append(FieldCondition(key="domain", match=MatchValue(value=домен)))
    if субдомен and субдомен != "все":
        must.append(FieldCondition(key="subdomain", match=MatchValue(value=субдомен)))
    if язык and язык != "все":
        must.append(FieldCondition(key="language", match=MatchValue(value=язык)))
    if источник and источник != "все":
        must.append(FieldCondition(key="source", match=MatchValue(value=источник)))
    if год_от:
        must.append(FieldCondition(key="year", range=Range(gte=год_от)))
    return Filter(must=must) if must else None


def _recency_boost(год, λ=0.0667):
    """Множитель свежести: статья этого года → 1.0, на 5 лет старше → ~0.72."""
    if not год:
        return 1.0
    разница = max(0, datetime.utcnow().year - int(год))
    return math.exp(-λ * разница)


def найти_похожие(
    вопрос,
    выбранный_кейс,
    количество,
    *,
    домен=None,
    субдомен=None,
    год_от=None,
    язык=None,
    источник=None,
    recency_weight=0.0,
):
    модель = загрузить_модель()
    клиент = загрузить_qdrant()
    коллекция, новая_схема = выбрать_коллекцию()

    вектор = модель.encode("query: " + вопрос, normalize_embeddings=True).tolist()

    if новая_схема:
        фильтр = _построить_фильтр(
            выбранный_кейс=None,  # case в новой схеме менее приоритетен
            домен=домен, субдомен=субдомен,
            год_от=год_от, язык=язык, источник=источник,
        )
    else:
        фильтр = _построить_фильтр(выбранный_кейс=выбранный_кейс)

    ответ = клиент.query_points(
        collection_name=коллекция,
        query=вектор,
        limit=количество * 3,
        query_filter=фильтр,
        with_payload=True,
    )

    for точка in ответ.points:
        точка.payload["text"] = почистить_pdf_артефакты(точка.payload.get("text", ""))

    МИН_СХОДСТВО = 0.72
    кандидаты = [т for т in ответ.points if т.score >= МИН_СХОДСТВО]
    кандидаты = [
        т for т in кандидаты
        if not похоже_на_библиографию(т.payload["text"])
        and not похоже_на_мусор(т.payload["text"])
    ]

    if recency_weight > 0:
        for т in кандидаты:
            бст = _recency_boost(т.payload.get("year"))
            т.score = float(т.score) * (1.0 + recency_weight * (бст - 1.0))
        кандидаты.sort(key=lambda т: т.score, reverse=True)

    return кандидаты[:количество]


def _ключи_groq():
    ключи = []
    for имя_переменной in ("GROQ_API_KEY", "GROQ_API_KEY_2", "GROQ_API_KEY_3"):
        к = os.getenv(имя_переменной)
        if к and к.strip():
            ключи.append(к.strip())
    return ключи


def _это_rate_limit(ошибка):
    текст = str(ошибка).lower()
    return "429" in текст or "rate_limit" in текст or "rate limit" in текст or "tokens per day" in текст


def вызвать_groq(параметры_запроса, резервная_модель="llama-3.1-8b-instant"):
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
    текст = отрезать_источники(текст)
    текст = убрать_неверные_маркеры(текст, фрагменты)
    return текст


def убрать_неверные_маркеры(ответ, фрагменты, абс_порог=0.65, дельта=0.015, ratio=0.97):
    if not фрагменты or "[" not in ответ:
        return ответ

    маркеры = []
    for m in re.finditer(r"\[(\d+)\]", ответ):
        n = int(m.group(1))
        if not (1 <= n <= len(фрагменты)):
            continue

        start = m.start()
        границы = [
            ответ.rfind(sep, 0, start)
            for sep in (". ", "! ", "? ", "\n", ": ", "; ", ", ")
        ]
        начало = max(границы) + 2 if any(b >= 0 for b in границы) else 0
        утв_сырой = ответ[начало:start].strip()


        утв = re.sub(r"\[\d+\]", "", утв_сырой).strip()

        if len(утв) < 20:
            continue
        маркеры.append({"start": m.start(), "end": m.end(), "n": n, "утв": утв})

    if not маркеры:
        return ответ

    try:
        модель = загрузить_модель()
        уник_утв = list({м["утв"] for м in маркеры})
        тексты_ф = [
            (фр.get("text") if isinstance(фр, dict) else фр.payload.get("text", ""))
            for фр in фрагменты
        ]

        emb_утв = модель.encode(
            ["query: " + t for t in уник_утв], normalize_embeddings=True
        )
        emb_ф = модель.encode(
            ["passage: " + t for t in тексты_ф], normalize_embeddings=True
        )
        матрица = emb_утв @ emb_ф.T
        индекс = {t: i for i, t in enumerate(уник_утв)}

        для_удаления = []
        for м in маркеры:
            i = индекс[м["утв"]]
            sim = float(матрица[i, м["n"] - 1])
            max_sim = float(матрица[i].max())
            если_слабый = sim < абс_порог
            если_отстаёт_абсолютно = sim < max_sim - дельта
            если_отстаёт_относительно = sim < max_sim * ratio
            if если_слабый or если_отстаёт_абсолютно or если_отстаёт_относительно:
                для_удаления.append((м["start"], м["end"]))
    except Exception:
        return ответ

    if not для_удаления:
        return ответ


    для_удаления.sort(reverse=True)
    чистый = ответ
    for start, end in для_удаления:
        if start > 0 and чистый[start - 1] == " ":
            start -= 1
        чистый = чистый[:start] + чистый[end:]

    чистый = re.sub(r" {2,}", " ", чистый)
    return чистый


def отрезать_источники(текст):
    совпадение = re.search(
        r"\n\s*(?:\*\*\s*|#+\s+)?(?:Источники|Sources|Ссылки)(?:\s*\*\*|\s*:|\s*\n)",
        текст,
        re.IGNORECASE,
    )
    if not совпадение:
        return текст.strip()
    return текст[:совпадение.start()].rstrip()


def почистить_pdf_текст(текст):
    результат = re.sub(r"(\w)-\s*\n\s*(\w)", r"\1\2", текст)
    результат = re.sub(r"\n(?!\s*\n)", " ", результат)
    результат = re.sub(r"\s*\b\d+\s+of\s+\d+\b\s*", " ", результат)
    результат = re.sub(r" {2,}", " ", результат)
    return результат.strip()


_МАТЕМАТИЧЕСКИЕ_СИМВОЛЫ = set("Σ∑∏∫∈∉≤≥≠≈∞αβγθσμπλ∗·×→∂∇√∝⊂⊃⊆⊇∪∩⟨⟩⇒⇔")


def содержит_математику(текст):
    if any(с in _МАТЕМАТИЧЕСКИЕ_СИМВОЛЫ for с in текст):
        return True
    if re.search(r"\b[a-zA-Zα-ωΑ-Ω]\s*\([a-zA-Z0-9,\s]+\)\s*=", текст):
        return True
    if re.search(r"\b\w+\s*=\s*[\w\-+\d/·*().\[\]]{5,}", текст) and re.search(r"[_^]|\b\d+\b", текст):
        return True
    return False


@st.cache_data(show_spinner=False)
def перевести_на_русский(текст):
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


дизайн.показать_шапку()
дизайн.показать_маркизу()
дизайн.показать_подсказку_скролла()
дизайн.показать_фичи()
дизайн.показать_терминал()
дизайн.показать_подсказку_скролла(текст="попробуйте сами ↓", отступ_сверху_rem=3)


вкладка1, вкладка2, вкладка3 = st.tabs(["Поиск", "Кейсы", "Архитектура"])

with вкладка1:
    дизайн.показать_заголовок("Задайте вопрос базе знаний")

    вопрос_пользователя = st.text_area(
        "вопрос",
        value=st.session_state.get("вопрос_пользователя", ""),
        height=130,
        placeholder="Какие методы машинного обучения используются для предсказания растворимости молекул?",
        label_visibility="collapsed"
    )

    _, новая_схема = выбрать_коллекцию()

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
        дизайн.показать_вертикальный_отступ()
        демо_режим = st.toggle("Демо-режим", value=False)
    with к4:
        дизайн.показать_вертикальный_отступ()
        кнопка = st.button("Найти ответ", type="primary", use_container_width=True)

    выбор_домена = "все"
    выбор_субдомена = "все"
    выбор_года_от = None
    выбор_языка = "все"
    вес_свежести = 0.0
    if новая_схема:
        with st.expander("Расширенные фильтры (домен, год, язык, свежесть)", expanded=False):
            ф1, ф2, ф3, ф4, ф5 = st.columns([1.4, 1.4, 1, 1, 1.2], gap="small")
            with ф1:
                варианты_доменов = ["все"] + list(ДОМЕНЫ.keys())
                выбор_домена = st.selectbox(
                    "Область",
                    options=варианты_доменов,
                    format_func=lambda к: "Все области" if к == "все" else название_домена(к),
                )
            with ф2:
                if выбор_домена != "все":
                    варианты_суб = ["все"] + list(ДОМЕНЫ[выбор_домена]["subdomains"].keys())
                else:
                    варианты_суб = ["все"]
                выбор_субдомена = st.selectbox(
                    "Подобласть",
                    options=варианты_суб,
                    format_func=lambda к: (
                        "Все" if к == "все" else название_субдомена(выбор_домена, к)
                    ),
                    disabled=(выбор_домена == "все"),
                )
            with ф3:
                выбор_года_от = st.number_input(
                    "Не раньше",
                    min_value=1990, max_value=datetime.utcnow().year,
                    value=2018, step=1,
                )
            with ф4:
                выбор_языка = st.selectbox(
                    "Язык",
                    options=["все", "ru", "en", "mixed"],
                )
            with ф5:
                вес_свежести = st.slider("Бонус свежести", 0.0, 1.0, 0.2, 0.05,
                                          help="Чем выше — тем сильнее свежие статьи буст в поиске")

    дизайн.показать_заголовок("Примеры вопросов", отступ_сверху_rem=2.5)
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
                if новая_схема:
                    модель_e5 = загрузить_модель()
                    метки_p, прото_p, негативы_p = прототипы_доменов()
                    in_scope, авто_дом, авто_суб, скор_scope = проверить_scope(
                        вопрос_пользователя, модель_e5,
                        метки_p, прото_p, негативы_p,
                    )
                    if not in_scope:
                        st.session_state.результаты_поиска = {
                            "тип": "off_topic",
                            "scope_score": скор_scope,
                            "примеры": примеры_in_scope_вопросов(),
                        }
                        st.stop()

                with st.spinner("Векторный поиск в Qdrant..."):
                    точки = найти_похожие(
                        вопрос_пользователя,
                        выбор_кейса,
                        количество_фрагментов,
                        домен=выбор_домена,
                        субдомен=выбор_субдомена,
                        год_от=выбор_года_от,
                        язык=выбор_языка,
                        recency_weight=вес_свежести,
                    )
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
                                "document": т.payload.get("document", ""),
                                "page": т.payload.get("page", ""),
                                "case": т.payload.get("case", ""),
                                "text": т.payload.get("text", ""),
                                "score": float(т.score),
                                "domain": т.payload.get("domain"),
                                "subdomain": т.payload.get("subdomain"),
                                "year": т.payload.get("year"),
                                "source": т.payload.get("source"),
                                "title": т.payload.get("title"),
                                "language": т.payload.get("language"),
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
    if результат and результат.get("тип") == "off_topic":
        st.warning(
            "Этот вопрос вне области моей базы знаний. "
            "Я отвечаю по химии, IT и их пересечению (cheminformatics, ML для химии, "
            "computational chemistry, materials informatics и т. п.)."
        )
        st.caption(f"scope-score: {результат['scope_score']:.3f} (порог {SCOPE_ПОРОГ_ПО_УМОЛЧАНИЮ:.2f})")
        st.markdown("**Примеры вопросов, на которые я отвечу:**")
        for пр in результат["примеры"]:
            st.markdown(f"- {пр}")
    elif результат and результат["тип"] == "демо":
        демо = результат["данные"]
        дизайн.показать_мета_демо(демо.get("кейс", ""))
        st.markdown(демо["ответ"])

        дизайн.показать_заголовок("Источники", отступ_сверху_rem=3)
        дизайн.показать_источники_демо(демо["источники"])

    elif результат and результат["тип"] == "rag":
        ответ = результат["ответ"]
        фрагменты = результат["фрагменты"]


        есть_маркеры = bool(re.search(r"\[\d+\]", ответ))

        дизайн.показать_мета_rag(len(фрагменты))
        st.markdown(вставить_цитаты_в_ответ(ответ, фрагменты), unsafe_allow_html=True)

        if есть_маркеры:
            дизайн.показать_заголовок("Источники", отступ_сверху_rem=3)
            дизайн.показать_источники_rag(фрагменты)

        дизайн.показать_заголовок("Найденные фрагменты", отступ_сверху_rem=3)
        if not есть_маркеры:
            st.caption(
                "Эти фрагменты найдены векторным поиском по близости вопроса, "
                "но модель не нашла в них ничего применимого к ответу. "
                "Поэтому раздел «Источники» не показан."
            )
        переводить = st.toggle(
            "Показать перевод на русский",
            value=False,
            key="переводить_фрагменты",
            help="Перевод через LLM, кэшируется."
        )

        for i, фр in enumerate(фрагменты, 1):
            заголовок = f"{i:02d}   {фр['document']}   ·   стр. {фр['page']}   ·   score {фр['score']:.3f}"
            with st.expander(заголовок):
                метки = []
                if фр.get("domain"):
                    дом = фр["domain"]
                    метки.append(название_домена(дом))
                    if фр.get("subdomain"):
                        метки.append(название_субдомена(дом, фр["subdomain"]))
                if фр.get("year"):
                    метки.append(str(фр["year"]))
                if фр.get("source"):
                    метки.append(фр["source"])
                if метки:
                    st.markdown("**Метки:** " + " · ".join(метки))
                if фр.get("case"):
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
    дизайн.показать_кейсы(кейсы)

with вкладка3:
    дизайн.показать_архитектуру()
