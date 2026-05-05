import math
import os
import re
import json
import mimetypes
import html
from datetime import datetime, timezone
from pathlib import Path

os.environ.setdefault("TRANSFORMERS_NO_TF", "1")
os.environ.setdefault("USE_TF", "0")

import streamlit as st
from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue, Range
from groq import Groq
from dotenv import load_dotenv

import дизайн
import notebooks
import study_tools
import визуальная_обработка as виз
from cases import кейсы, получить_название_кейса
from taxonomy import ДОМЕНЫ, название_домена, название_субдомена
from классификатор import (
    подготовить_прототипы,
    проверить_scope,
    примеры_in_scope_вопросов,
    SCOPE_ПОРОГ_ПО_УМОЛЧАНИЮ,
)

load_dotenv()
APP_DIR = Path(__file__).resolve().parent

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
10. ЗАПРЕЩЕНО приводить формулы, уравнения и численные константы, которых НЕТ в CONTEXT — даже если ты эту формулу знаешь из общих знаний. Если формулы в CONTEXT нет, опиши процесс словами или скажи: «Формула для этого в найденных фрагментах не приведена». Каждая формула в ответе должна быть подкреплена маркером [N] из CONTEXT, где она реально присутствует.
11. КАРТИНКИ: у некоторых фрагментов в CONTEXT есть блок «Картинки:» со списком доступных изображений вида «[img:N.M] описание». Правила вставки строгие:
    а) ЖЁСТКИЙ ЛИМИТ: во всём ответе максимум 2 маркера `[img:N.M]`. Никогда не ставь картинку «на каждый абзац», «на каждый пункт списка» или «в каждую подтему» — это запрещено. Если подходит 3+, выбери 1–2 САМЫЕ точные под вопрос пользователя, остальные выкинь.
    б) ПРИОРИТЕТ СОВПАДЕНИЯ С ВОПРОСОМ: если пользователь спрашивает про конкретную схему/диаграмму/классификацию («схема X», «классификация Y», «как устроен Z», «виды X»), выбирай картинку, чей caption БУКВАЛЬНО содержит ключевые слова из вопроса, а не общую иллюстрацию по теме. Картинка-дерево/блок-схема/классификационная диаграмма ВСЕГДА приоритетнее CFD-визуализации, фотографии аппарата или графика по той же теме, если в вопросе есть слово «схема», «классификация», «виды», «структура».
    в) ФОРМАТ: `[img:N.M]` ставь на отдельной строке сразу после того абзаца, который эту картинку реально описывает. Не ставь картинку, если её caption описывает другой объект (например, абзац про «мешалки», а картинка про «задвижку» — не ставь).
    г) ЕСЛИ НИ ОДНА НЕ ПОДХОДИТ ТОЧНО — НЕ ВСТАВЛЯЙ ВОВСЕ. Пустой ответ без картинок лучше, чем 5 нерелевантных.
    Маркер `[img:N.M]` не заменяет обычный маркер цитаты `[N]` — ставь оба.
12. КАТЕГОРИЧЕСКИ ЗАПРЕЩЕНО дословно копировать в ответ: URL'ы и ссылки (http://, https://, doi.org, creativecommons.org), названия лицензий (CC BY, BY-NC-ND), авторские блоки (имена авторов, аффилиации университетов, адреса, e-mail, телефоны), названия журналов и издательств, ключевые слова в формате «K e y w o r d s», метки разделов вида «A B S T R A C T» / «I N T R O D U C T I O N» / «A R T I C L E I N F O», DOI, ORCID, номера страниц журнала. Это технические артефакты PDF, а не факты по теме. Если фрагмент содержит подобный мусор — ИГНОРИРУЙ его и излагай ТОЛЬКО содержательную часть фрагмента своими словами на русском."""


@st.cache_resource
def загрузить_модель():
    return SentenceTransformer("intfloat/multilingual-e5-base")


@st.cache_resource
def загрузить_qdrant():
    """Удалённый Qdrant если задан QDRANT_URL, иначе локальный qdrant_db/."""
    url = os.getenv("QDRANT_URL", "").strip()
    if url:
        return QdrantClient(
            url=url,
            api_key=os.getenv("QDRANT_API_KEY") or None,
            prefer_grpc=False,
            timeout=60,
        )
    папка = os.path.join(os.path.dirname(os.path.abspath(__file__)), "qdrant_db")
    return QdrantClient(path=папка)


@st.cache_resource
def выбрать_коллекцию():
    """Выбираем активную коллекцию: knowledge_hybrid (dense+sparse) >
    knowledge (только dense) > химия (старая, dense + старая схема payload).

    Возвращает (имя, новая_схема, гибрид):
      - новая_схема=True если payload содержит domain/subdomain/...
      - гибрид=True если можно делать sparse-prefetch + RRF
    """
    клиент = загрузить_qdrant()
    try:
        имена = {к.name for к in клиент.get_collections().collections}
    except Exception:
        имена = set()
    if "knowledge_hybrid" in имена:
        return "knowledge_hybrid", True, True
    if "knowledge" in имена:
        return "knowledge", True, False
    return "химия", False, False


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
        url = notebooks.citation_url(фр)
        if url and isinstance(фр, dict):
            фр["citation_url"] = url
        href = _экранировать_атрибут(url or "")
        открывающий = (
            f'<a class="cite" href="{href}" target="_blank" rel="noopener" '
            f'title="Открыть документ на странице {страница}">'
            if url else '<span class="cite">'
        )
        закрывающий = '</a>' if url else '</span>'
        return (
            f'{открывающий}'
            f'[{n}]'
            f'<span class="cite-tip">'
            f'<span class="cite-doc">{doc_attr}</span>'
            f'<span class="cite-text">{text_attr}</span>'
            f'</span>{закрывающий}'
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
    разница = max(0, datetime.now(timezone.utc).year - int(год))
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
    использовать_reranker=False,
):
    модель = загрузить_модель()
    клиент = загрузить_qdrant()
    коллекция, новая_схема, гибрид = выбрать_коллекцию()

    вектор = модель.encode("query: " + вопрос, normalize_embeddings=True).tolist()

    if новая_схема:
        фильтр = _построить_фильтр(
            выбранный_кейс=None,  # case в новой схеме менее приоритетен
            домен=домен, субдомен=субдомен,
            год_от=год_от, язык=язык, источник=источник,
        )
    else:
        фильтр = _построить_фильтр(выбранный_кейс=выбранный_кейс)

    лимит_кандидатов = количество * 5 if использовать_reranker else количество * 3

    if гибрид:
        from qdrant_client.models import (
            Fusion,
            FusionQuery,
            Prefetch,
            SparseVector,
        )
        from hybrid_search import построить_sparse_один

        sparse_idx, sparse_val = построить_sparse_один(вопрос)
        ответ = клиент.query_points(
            collection_name=коллекция,
            prefetch=[
                Prefetch(query=вектор, using="dense", limit=лимит_кандидатов, filter=фильтр),
                Prefetch(
                    query=SparseVector(indices=sparse_idx, values=sparse_val),
                    using="sparse", limit=лимит_кандидатов, filter=фильтр,
                ),
            ],
            query=FusionQuery(fusion=Fusion.RRF),
            limit=лимит_кандидатов,
            with_payload=True,
        )
    else:
        ответ = клиент.query_points(
            collection_name=коллекция,
            query=вектор,
            limit=лимит_кандидатов,
            query_filter=фильтр,
            with_payload=True,
        )

    for точка in ответ.points:
        точка.payload["text"] = почистить_pdf_артефакты(точка.payload.get("text", ""))

    # При гибриде у точек RRF-score (~0.01–0.1) — порог по-другому. При dense — cosine ≥0.72.
    if гибрид:
        кандидаты = list(ответ.points)
    else:
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

    if использовать_reranker and кандидаты:
        try:
            from reranker import переранжировать
            тексты = [т.payload.get("text", "") for т in кандидаты]
            упорядоченные = переранжировать(вопрос, тексты, top_k=количество)
            кандидаты = [кандидаты[i] for i, _ in упорядоченные]
        except Exception as e:
            # При ошибке (нет интернета/модели) — обычный порядок
            print(f"reranker недоступен: {e}")

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


def _собрать_картинки_фрагмента_для_промпта(payload: dict) -> list[tuple[int, str]]:
    """Возвращает список `(M, caption)` — картинки фрагмента с описаниями,
    пригодными для вставки в промпт. Без caption картинку не показываем
    модели, чтобы она не ставила [img:N.M] наугад."""
    картинки = payload.get("images") or []
    результат: list[tuple[int, str]] = []
    for индекс, карт in enumerate(картинки, 1):
        if not isinstance(карт, dict):
            continue
        caption = (карт.get("caption") or "").strip()
        if not caption:
            continue
        # Обрезаем слишком длинные caption'ы
        if len(caption) > 260:
            caption = caption[:257].rstrip() + "…"
        результат.append((индекс, caption))
    return результат


def получить_ответ_от_groq(вопрос, фрагменты):
    if not _ключи_groq():
        return "Ошибка: GROQ_API_KEY не задан в файле .env"

    контекст = ""
    for i, фр in enumerate(фрагменты, 1):
        payload = фр if isinstance(фр, dict) else фр.payload
        источник = "мои документы" if payload.get("source") == "user_upload" else "корпус"
        контекст += f"[{i}] Источник: {источник}. Документ: {payload['document']}, стр. {payload['page']}\n"
        контекст += payload["text"] + "\n"
        картинки_с_подписью = _собрать_картинки_фрагмента_для_промпта(payload)
        if картинки_с_подписью:
            контекст += "Картинки:\n"
            for M, caption in картинки_с_подписью:
                контекст += f"  [img:{i}.{M}] {caption}\n"
        контекст += "\n"

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
    текст = _вырезать_pdf_мусор_из_ответа(текст)
    текст = _ограничить_количество_картинок(текст)
    return текст


def обогатить_картинками_соседних_страниц(фрагменты, *, окно: int = 2) -> None:
    """Добавляет в каждый фрагмент `images_neighbors` — картинки с
    соседних страниц того же документа из других чанков той же тетради.

    Работает только для фрагментов, у которых известны `notebook_id` и
    `file_hash`. Для каждого фрагмента с пустым `images` ищет в коллекции
    тетради чанки на странице ±`окно` и подставляет их картинки.

    Идемпотентно: если у фрагмента уже есть `images_neighbors`, повторно не
    обновляет его. Если поиск завершается ошибкой — молча пропускает.
    """
    if not фрагменты:
        return
    группы: dict[tuple[str, str], list[dict]] = {}
    for фр in фрагменты:
        nid = фр.get("notebook_id")
        fh = фр.get("file_hash")
        if not nid or not fh:
            continue
        if фр.get("images") or фр.get("images_neighbors"):
            continue
        uid = фр.get("user_id") or пользователь_id
        группы.setdefault((uid, nid), []).append(фр)

    if not группы:
        return

    try:
        клиент = загрузить_qdrant()
    except Exception:
        return

    for (uid, nid), bucket in группы.items():
        try:
            store = notebooks.load_store(uid)
        except Exception:
            continue
        ноутбуки = store.get("users", {}).get(uid, {}).get("notebooks", [])
        тетрадь = next((nb for nb in ноутбуки if nb.get("id") == nid), None)
        if тетрадь is None:
            continue
        file_hashes = {фр.get("file_hash") for фр in bucket if фр.get("file_hash")}
        if not file_hashes:
            continue
        try:
            индекс = notebooks.собрать_картинки_по_страницам(
                клиент, тетрадь, file_hashes, user_id=uid,
            )
        except Exception:
            continue
        if not индекс:
            continue
        for фр in bucket:
            fh = фр.get("file_hash")
            try:
                page = int(фр.get("page"))
            except (TypeError, ValueError):
                continue
            if not fh or page <= 0:
                continue
            соседи: list[dict] = []
            видели: set[str] = set()
            for delta in range(1, окно + 1):
                for сторона in (-delta, delta):
                    for img in индекс.get((fh, page + сторона), []):
                        путь = img.get("path") or ""
                        if not путь or путь in видели:
                            continue
                        видели.add(путь)
                        соседи.append(img)
                if соседи:
                    break
            if соседи:
                фр["images_neighbors"] = соседи


def сериализовать_фрагменты(точки):
    фрагменты = []
    for т in точки:
        payload = т if isinstance(т, dict) else т.payload
        фрагменты.append({
            "document": payload.get("document", ""),
            "page": payload.get("page", ""),
            "case": payload.get("case", ""),
            "text": payload.get("text", ""),
            "score": float(getattr(т, "score", payload.get("score", 0.0)) or 0.0),
            "domain": payload.get("domain"),
            "subdomain": payload.get("subdomain"),
            "year": payload.get("year"),
            "source": payload.get("source"),
            "title": payload.get("title"),
            "language": payload.get("language"),
            "user_id": payload.get("user_id"),
            "notebook_id": payload.get("notebook_id"),
            "notebook_title": payload.get("notebook_title"),
            "file_path": payload.get("file_path"),
            "file_type": payload.get("file_type"),
            "file_hash": payload.get("file_hash"),
            "images": payload.get("images") or [],
        })
    return фрагменты


def показать_скачивание_источников(фрагменты, key_prefix):
    доступные = []
    seen = set()
    for фр in фрагменты:
        путь = notebooks.source_file_path(фр)
        if not путь:
            continue
        ключ = str(путь.resolve()).lower()
        if ключ in seen:
            continue
        seen.add(ключ)
        доступные.append((путь, фр))

    if not доступные:
        st.caption("Локальные файлы источников не найдены. Для harvest-документов проверьте наличие файла в папке all_pdfs/.")
        return

    st.markdown("**Скачать документы-источники:**")
    for i, (путь, фр) in enumerate(доступные, 1):
        try:
            данные = путь.read_bytes()
        except OSError as ошибка:
            st.caption(f"{путь.name}: не удалось прочитать файл ({ошибка})")
            continue
        mime = mimetypes.guess_type(путь.name)[0] or "application/octet-stream"
        st.download_button(
            label=f"Скачать {путь.name}",
            data=данные,
            file_name=путь.name,
            mime=mime,
            key=f"{key_prefix}_source_{i}_{abs(hash(str(путь)))}",
            use_container_width=True,
        )


_IMG_МАРКЕР = re.compile(r"\[img:(\d+)\.(\d+)\]")

_МАКС_КАРТИНОК_В_ОТВЕТЕ = 2


def _ограничить_количество_картинок(ответ: str, лимит: int = _МАКС_КАРТИНОК_В_ОТВЕТЕ) -> str:
    """Оставляет не более `лимит` маркеров `[img:N.M]` в ответе, остальные
    вырезает. Предохранитель на случай, если LLM проигнорировала правило
    11а и поставила больше картинок, чем нужно.
    """
    if лимит <= 0:
        return _IMG_МАРКЕР.sub("", ответ)
    счётчик = 0

    def _замена(m: re.Match) -> str:
        nonlocal счётчик
        счётчик += 1
        if счётчик <= лимит:
            return m.group(0)
        return ""

    return _IMG_МАРКЕР.sub(_замена, ответ)


_МИН_СТОРОНА_КАРТИНКИ = 280  # меньше — почти всегда логотип/иконка
_КЭШ_РАЗМЕРОВ: dict[str, tuple[int, int] | None] = {}


def _размер_картинки(путь: Path) -> tuple[int, int] | None:
    """Возвращает (width, height) или None, если прочитать не удалось.
    Кэширует результат по абсолютному пути."""
    ключ = str(путь.resolve()).lower()
    if ключ in _КЭШ_РАЗМЕРОВ:
        return _КЭШ_РАЗМЕРОВ[ключ]
    try:
        from PIL import Image
        with Image.open(путь) as im:
            размер = im.size  # (width, height)
    except Exception:
        размер = None
    _КЭШ_РАЗМЕРОВ[ключ] = размер
    return размер


def _картинка_содержательная(путь: Path) -> bool:
    """Отсекает логотипы/иконки по минимальному разрешению."""
    размер = _размер_картинки(путь)
    if размер is None:
        return True  # если не смогли прочитать — не режем
    w, h = размер
    if w < _МИН_СТОРОНА_КАРТИНКИ or h < _МИН_СТОРОНА_КАРТИНКИ:
        return False
    # очень вытянутые баннеры / разделители тоже обычно декоративные
    соотношение = max(w, h) / max(1, min(w, h))
    if соотношение > 6:
        return False
    return True


def _локальный_путь_картинки(путь_картинки):
    if not путь_картинки:
        return None
    путь = Path(str(путь_картинки))
    if not путь.is_absolute():
        путь = APP_DIR / путь
    try:
        путь = путь.resolve()
        путь.relative_to(APP_DIR)
    except (OSError, ValueError):
        return None
    if путь.is_file() and путь.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}:
        return путь
    return None


def _собрать_доступные_картинки(картинки, текущая_страница, *, фильтр_размера: bool = True):
    if not isinstance(картинки, list):
        return []
    доступные = []
    for картинка in картинки:
        if not isinstance(картинка, dict):
            continue
        путь = _локальный_путь_картинки(картинка.get("path"))
        if not путь:
            continue
        if фильтр_размера and not _картинка_содержательная(путь):
            continue
        доступные.append((путь, картинка.get("page") or текущая_страница))
    return доступные


def показать_картинки_фрагмента(фр, key_prefix):
    собственные = _собрать_доступные_картинки(фр.get("images"), фр.get("page"))
    if собственные:
        заголовок = "**Изображения со страницы:**"
        список = собственные
    else:
        соседние = _собрать_доступные_картинки(
            фр.get("images_neighbors"), фр.get("page")
        )
        if not соседние:
            return
        заголовок = "**Изображения с соседних страниц:**"
        список = соседние

    st.markdown(заголовок)
    колонки = st.columns(min(3, len(список)), gap="small")
    for индекс, (путь, страница) in enumerate(список):
        with колонки[индекс % len(колонки)]:
            st.image(
                str(путь),
                caption=f"стр. {страница} · {путь.name}",
                use_container_width=True,
            )


def _разрешить_img_маркер(n: int, m: int, фрагменты: list) -> tuple[Path, str, str] | None:
    """Превращает (N, M) в (локальный путь, подпись, caption) или None,
    если картинку нельзя показать."""
    if not (1 <= n <= len(фрагменты)):
        return None
    фр = фрагменты[n - 1]
    картинки = фр.get("images") or []
    if not (1 <= m <= len(картинки)):
        return None
    карт = картинки[m - 1]
    if not isinstance(карт, dict):
        return None
    путь = _локальный_путь_картинки(карт.get("path"))
    if путь is None:
        return None
    caption = (карт.get("caption") or "").strip()
    подпись = f"[{n}.{m}] стр. {карт.get('page') or фр.get('page', '')}"
    if caption:
        # укорачиваем caption для подписи под картинкой
        отображаемый = caption if len(caption) <= 140 else caption[:137].rstrip() + "…"
        подпись += f" · {отображаемый}"
    return путь, подпись, caption


def показать_ответ_с_картинками(ответ, фрагменты, key_prefix="rag_answer"):
    """Выводит ответ с картинками, которые ВЫБРАЛА модель через маркеры
    вида `[img:N.M]`. N — номер фрагмента, M — порядковый номер картинки
    внутри него. Если маркер указывает на несуществующую картинку —
    он просто удаляется из текста. Одна и та же картинка не дублируется.
    """
    if not ответ:
        return

    показанные: set[str] = set()

    def _показать_картинку(n: int, m: int) -> None:
        разрешено = _разрешить_img_маркер(n, m, фрагменты)
        if разрешено is None:
            return
        путь, подпись, _ = разрешено
        ключ = str(путь.resolve()).lower()
        if ключ in показанные:
            return
        показанные.add(ключ)
        # Центрируем картинку и ограничиваем ширину — ~55% контейнера,
        # чтобы она не распирала весь ответ.
        _, центр, _ = st.columns([1, 3, 1], gap="small")
        with центр:
            st.image(str(путь), caption=подпись, use_container_width=True)

    # Разбиваем ответ на сегменты по маркерам [img:N.M]:
    # текст до маркера → показать картинку → текст до следующего маркера → …
    позиция = 0
    буфер_текста = ""
    for m in _IMG_МАРКЕР.finditer(ответ):
        до_маркера = ответ[позиция:m.start()]
        буфер_текста += до_маркера
        позиция = m.end()

        # Выводим накопленный текст, если он не пустой
        текст_для_вывода = буфер_текста.strip()
        if текст_для_вывода:
            st.markdown(
                вставить_цитаты_в_ответ(буфер_текста, фрагменты),
                unsafe_allow_html=True,
            )
        буфер_текста = ""

        _показать_картинку(int(m.group(1)), int(m.group(2)))

    # Хвост ответа после последнего маркера
    хвост = ответ[позиция:]
    if хвост.strip():
        st.markdown(
            вставить_цитаты_в_ответ(хвост, фрагменты),
            unsafe_allow_html=True,
        )


def показать_экспорт_ответа(заголовок, текст, фрагменты, key_prefix):
    к1, к2 = st.columns(2, gap="small")
    with к1:
        st.download_button(
            "Скачать ответ .md",
            data=study_tools.markdown_export(заголовок, текст, фрагменты),
            file_name="navigator_answer.md",
            mime="text/markdown",
            key=f"{key_prefix}_md",
            use_container_width=True,
        )
    with к2:
        st.download_button(
            "Скачать ответ .docx",
            data=study_tools.docx_export(заголовок, текст, фрагменты),
            file_name="navigator_answer.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            key=f"{key_prefix}_docx",
            use_container_width=True,
        )


def _построить_svg_граф(узлы, рёбра, adj, id2label, degree):
    """Иерархический mind-map в чистом SVG без динамических JS-модулей.

    Корень — самый связанный концепт (макс degree), под ним BFS-уровни:
    соседи корня → их соседи → … Tree-edges (родитель → ребёнок) рисуются
    плавными кривыми. Боковые связи (cross-edges, между родственниками не
    через родителя) — тонкими пунктирными серыми линиями, чтобы было видно
    дополнительные связи без визуального шума.

    `st.graphviz_chart` ломается за tunnel'ами вроде lhr.life/ngrok, потому
    что streamlit-компонент графа подгружает свой JS как ES-module, а
    прокси режут такие запросы. SVG рендерится сразу в HTML и работает
    везде.
    """
    if not узлы or not adj:
        return "<div style='color:#525252'>нет узлов для графа</div>"

    все_id = list(adj.keys())
    рёбра_графа: set[tuple[str, str]] = set()
    for ребро in рёбра:
        s = str(ребро.get("source", ""))
        t = str(ребро.get("target", ""))
        if s in adj and t in adj and s != t:
            рёбра_графа.add(tuple(sorted((s, t))))
    if not рёбра_графа:
        for s, соседи in adj.items():
            for t in соседи:
                if t in adj and s != t:
                    рёбра_графа.add(tuple(sorted((s, t))))

    корень = max(все_id, key=lambda nid: (degree.get(nid, 0), -все_id.index(nid)))
    родители: dict[str, str | None] = {корень: None}
    дети: dict[str, list[str]] = {nid: [] for nid in все_id}
    посещённые: set[str] = {корень}
    очередь = [корень]
    while очередь:
        nid = очередь.pop(0)
        соседи = sorted(adj.get(nid, []), key=lambda n: (-degree.get(n, 0), id2label.get(n, n)))
        for сосед in соседи:
            if сосед in посещённые:
                continue
            посещённые.add(сосед)
            родители[сосед] = nid
            дети[nid].append(сосед)
            очередь.append(сосед)

    for nid in все_id:
        if nid not in посещённые:
            родители[nid] = корень
            дети[корень].append(nid)

    tree_edges = [
        (parent, nid)
        for nid, parent in родители.items()
        if parent is not None
    ]
    tree_edge_keys = {tuple(sorted(edge)) for edge in tree_edges}

    def _листья(nid):
        if not дети.get(nid):
            return 1
        return sum(_листья(child) for child in дети[nid])

    листьев = max(1, _листья(корень))
    node_w = 202
    node_h = 56
    gap_x = 236
    gap_y = 142
    ширина = max(1060, листьев * gap_x + 180)

    глубина: dict[str, int] = {корень: 0}
    for nid in все_id:
        cur = nid
        d = 0
        seen = set()
        while родители.get(cur) is not None and cur not in seen:
            seen.add(cur)
            cur = родители[cur]
            d += 1
        глубина[nid] = d
    высота = max(540, (max(глубина.values()) + 1) * gap_y + 110)

    положения: dict[str, tuple[float, float]] = {}
    следующий_x = 90 + node_w / 2

    def _layout(nid):
        nonlocal следующий_x
        children = дети.get(nid, [])
        if not children:
            x = следующий_x
            следующий_x += gap_x
        else:
            xs = [_layout(child) for child in children]
            x = sum(xs) / len(xs)
        y = 70 + глубина.get(nid, 0) * gap_y
        положения[nid] = (x, y)
        return x

    _layout(корень)

    min_x = min(x for x, _ in положения.values())
    max_x = max(x for x, _ in положения.values())
    сдвиг = (ширина - (max_x - min_x)) / 2 - min_x
    for nid, (x, y) in list(положения.items()):
        положения[nid] = (x + сдвиг, y)

    if max(len(дети.get(nid, [])) for nid in все_id) <= 1 and len(все_id) > 2:
        for nid, (x, y) in list(положения.items()):
            d = глубина.get(nid, 0)
            if d:
                offset = 115 if d % 2 else -115
                положения[nid] = (min(ширина - node_w / 2 - 40, max(node_w / 2 + 40, x + offset)), y)

    def _строки(текст, лимит=20, максимум=2):
        текст = str(текст or "")
        words = текст.split()
        if not words:
            words = [текст]
        lines = []
        current = ""
        for word in words:
            if len(word) > лимит:
                parts = [word[i:i + лимит] for i in range(0, len(word), лимит)]
            else:
                parts = [word]
            for part in parts:
                проба = (current + " " + part).strip()
                if len(проба) <= лимит:
                    current = проба
                else:
                    if current:
                        lines.append(current)
                    current = part
        if current:
            lines.append(current)
        if len(lines) > максимум:
            lines = lines[:максимум]
            lines[-1] = lines[-1][:лимит - 1] + "…"
        return lines or [текст[:лимит]]

    куски = [
        '<div style="width:100%;overflow-x:auto;overflow-y:hidden;border-radius:8px;'
        'border:1px solid #262626;background:#0d0d0d">',
        f'<svg viewBox="0 0 {ширина} {высота}" xmlns="http://www.w3.org/2000/svg" '
        'style="width:100%;min-width:920px;height:auto;display:block;max-height:78vh">'
    ]

    for s, t in sorted(рёбра_графа - tree_edge_keys):
        x1, y1 = положения[s]
        x2, y2 = положения[t]
        куски.append(
            f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
            'stroke="#2563eb" stroke-width="1.8" opacity="0.7" />'
        )

    for s, t in tree_edges:
        x1, y1 = положения[s]
        x2, y2 = положения[t]
        mid_y = (y1 + y2) / 2
        куски.append(
            f'<path d="M {x1:.1f} {y1 + node_h / 2:.1f} '
            f'C {x1:.1f} {mid_y:.1f}, {x2:.1f} {mid_y:.1f}, {x2:.1f} {y2 - node_h / 2:.1f}" '
            'stroke="#3b82f6" stroke-width="2.7" fill="none" opacity="0.92" />'
        )

    for nid, (x, y) in положения.items():
        deg = degree.get(nid, 0)
        is_root = nid == корень
        fill = "#1e40af" if is_root else ("#1e3a8a" if deg > 1 else "#172554")
        stroke = "#60a5fa" if is_root else "#3b82f6"
        left = x - node_w / 2
        top = y - node_h / 2
        куски.append(
            f'<rect x="{left:.1f}" y="{top:.1f}" width="{node_w}" height="{node_h}" rx="16" '
            f'fill="{fill}" stroke="{stroke}" stroke-width="1.9" />'
        )
        lines = _строки(id2label.get(nid, nid))
        start_y = y - (len(lines) - 1) * 7 + 4
        for idx, line in enumerate(lines):
            куски.append(
                f'<text x="{x:.1f}" y="{start_y + idx * 14:.1f}" fill="#f5f7fb" '
                'font-family="Helvetica,Arial,sans-serif" font-size="13" font-weight="650" '
                f'text-anchor="middle">{html.escape(line, quote=True)}</text>'
            )

    куски.append('</svg></div>')
    return ''.join(куски)


def _страницы_из_файлов(файлы):
    всего = 0
    for файл in файлы:
        страниц = файл.get("pages") or файл.get("slides") or файл.get("chunks") or 0
        try:
            всего += int(страниц)
        except (TypeError, ValueError):
            pass
    return всего


def _тетрадь_заполнена(тетрадь):
    файлы = тетрадь.get("files") or []
    return any((файл.get("chunks") or файл.get("pages") or файл.get("slides") or файл.get("name")) for файл in файлы)


def _id_тетради_по_умолчанию(тетради_список, текущая_id=None):
    if not тетради_список:
        return None
    по_id = {тетрадь["id"]: тетрадь for тетрадь in тетради_список}
    заполненные = [тетрадь for тетрадь in тетради_список if _тетрадь_заполнена(тетрадь)]
    if текущая_id in по_id and (not заполненные or _тетрадь_заполнена(по_id[текущая_id])):
        return текущая_id
    if заполненные:
        return заполненные[0]["id"]
    if текущая_id in по_id:
        return текущая_id
    return тетради_список[0]["id"]


def _статистика_после_поиска(результат, тетради_пользователя):
    фрагменты = результат.get("фрагменты", [])
    режим = результат.get("режим") or "поиск"

    # В режиме "только корпус из интернета" пользовательские тетради не учитываются
    # вообще — иначе статистика подсыпает сумму чанков из всех тетрадей и
    # сбивает пользователя с толку. В остальных режимах считаем только по
    # выбранной тетради (если она определена), а не по всем сразу.
    режим_lower = режим.lower()
    только_корпус = ("корпус" in режим_lower and "мои" not in режим_lower)

    активная_тетрадь_имя = результат.get("тетрадь")
    есть_активная_тетрадь = (
        not только_корпус
        and активная_тетрадь_имя
        and активная_тетрадь_имя != "не выбрана"
    )

    if только_корпус:
        тетради_для_подсчёта: list = []
    elif есть_активная_тетрадь:
        тетради_для_подсчёта = [
            т for т in тетради_пользователя
            if т.get("title") == активная_тетрадь_имя
        ] or list(тетради_пользователя)
    else:
        тетради_для_подсчёта = list(тетради_пользователя)

    файлы = []
    типы: set[str] = set()
    всего_фрагментов = 0
    for тетрадь in тетради_для_подсчёта:
        файлы.extend(тетрадь.get("files", []))
    for файл in файлы:
        if файл.get("type"):
            типы.add(str(файл["type"]).upper())
        try:
            всего_фрагментов += int(файл.get("chunks") or 0)
        except (TypeError, ValueError):
            pass

    связанные = []
    for фр in фрагменты[:3]:
        связанные.append({
            "score": f"{float(фр.get('score') or 0.0):.2f}",
            "title": фр.get("document") or "документ",
            "why": "похожий контекст / найденный фрагмент",
        })

    темы = []
    for ключ in ("domain", "subdomain", "case", "source"):
        for фр in фрагменты:
            значение = фр.get(ключ)
            if значение and значение not in темы:
                темы.append(str(значение))
            if len(темы) >= 8:
                break
        if len(темы) >= 8:
            break
    if not темы:
        темы = ["Big Data", "Qdrant", "RAG", "фрагменты", "ответ"]

    режим = результат.get("режим") or "поиск"
    использованы_мои = any(фр.get("source") == "user_upload" or фр.get("notebook_id") for фр in фрагменты)
    использован_корпус = any(not (фр.get("source") == "user_upload" or фр.get("notebook_id")) for фр in фрагменты)
    if "Мои + корпус" in режим:
        источники = [("мои материалы", 35 if использованы_мои else 8), ("интернет-корпус", 92 if использован_корпус else 8)]
    elif "моим" in режим.lower():
        источники = [("мои материалы", 92 if использованы_мои or фрагменты else 8), ("интернет-корпус", 8)]
    else:
        источники = [("мои материалы", 8), ("интернет-корпус", 92 if использован_корпус or фрагменты else 8)]

    диагностика = []
    for подпись, фр in zip(("семантически близко к вопросу", "поддерживает тот же термин/метод"), фрагменты[:2]):
        диагностика.append({
            "score": f"{float(фр.get('score') or 0.0):.2f}",
            "title": фр.get("document") or "фрагмент",
            "why": подпись,
        })
    диагностика.append({
        "score": f"{min(0.99, 0.55 + len(фрагменты) * 0.05):.2f}",
        "title": режим,
        "why": "добавляет контекст для ответа",
    })

    мои_векторы = всего_фрагментов
    if только_корпус:
        qdrant_статус = "QDRANT · корпус интернета"
        qdrant_пайплайн = "поиск по корпусу"
    elif есть_активная_тетрадь:
        qdrant_статус = f"QDRANT · {мои_векторы} векторов в тетради"
        qdrant_пайплайн = f"{мои_векторы} в тетради + корпус"
    else:
        qdrant_статус = f"QDRANT · {мои_векторы} моих векторов"
        qdrant_пайплайн = f"{мои_векторы} моих + корпус"

    return {
        "режим": режим,
        "тетрадь": результат.get("тетрадь") or "не выбрана",
        "qdrant_статус": qdrant_статус,
        "мои_файлы": len(файлы),
        "страницы_слайды": _страницы_из_файлов(файлы),
        "мои_фрагменты": всего_фрагментов,
        "мои_векторы": мои_векторы,
        "типы_файлов": len(типы),
        "темы": темы,
        "связанные": связанные,
        "источники": источники,
        "диагностика": диагностика,
        "пайплайн": [
            (1, "файл", ", ".join(sorted(типы)) or "PDF, PPTX"),
            (2, "текст", "извлечение страниц и слайдов"),
            (3, "фрагменты", f"{len(фрагменты)} найдено для ответа"),
            (4, "embedding", "multilingual-e5 · 768 dim"),
            (5, "Qdrant", qdrant_пайплайн),
            (6, "результат", "ответ / источники / статистика"),
        ],
    }


def _html(значение):
    return html.escape(str(значение or ""), quote=True)


def _источник_url_без_подсветки(фр):
    путь = notebooks.source_file_path(фр)
    if not путь:
        return ""
    try:
        страница = int(фр.get("page") or 0)
    except (TypeError, ValueError):
        страница = 0
    suffix = f"#page={страница}" if путь.suffix.lower() == ".pdf" and страница else ""
    return путь.resolve().as_uri() + suffix


def _источник_карточки_plain(карточка, фрагменты):
    if карточка.get("source_display"):
        return str(карточка["source_display"])
    if not фрагменты:
        return str(карточка.get("source") or "")
    сырьё = " ".join(
        str(карточка.get(ключ) or "")
        for ключ in ("source", "back", "answer")
    )
    номера = использованные_номера_цитат(сырьё, len(фрагменты))
    if not номера:
        return str(карточка.get("source") or "")
    части = []
    for номер in номера:
        фр = фрагменты[номер - 1]
        документ = дизайн.красивое_имя_файла(фр.get("document", ""))
        страница = фр.get("page", "")
        части.append(f"[{номер}] {документ}, стр. {страница}")
    return "; ".join(части)


def _источник_карточки_html(карточка, фрагменты):
    if not фрагменты:
        return _html(карточка.get("source") or "источник не указан")
    сырьё = " ".join(
        str(карточка.get(ключ) or "")
        for ключ in ("source", "back", "answer")
    )
    номера = использованные_номера_цитат(сырьё, len(фрагменты))
    if not номера:
        return _html(карточка.get("source_display") or карточка.get("source") or "источник не указан")
    ссылки = []
    for номер in номера:
        фр = фрагменты[номер - 1]
        документ = дизайн.красивое_имя_файла(фр.get("document", ""))
        страница = фр.get("page", "")
        текст = f"[{номер}] стр. {страница} · {документ}"
        url = _источник_url_без_подсветки(фр)
        if url:
            ссылки.append(f'<a href="{_html(url)}" target="_blank" rel="noopener">{_html(текст)}</a>')
        else:
            ссылки.append(_html(текст))
    return " · ".join(ссылки)


def обогатить_карточки_источниками(карточки, фрагменты):
    результат = []
    for карточка in карточки or []:
        копия = dict(карточка)
        копия["source_display"] = _источник_карточки_plain(копия, фрагменты)
        результат.append(копия)
    return результат


def показать_учебные_карточки(карточки, фрагменты):
    if not карточки:
        st.warning("Карточки не сгенерировались. Попробуйте сузить тему или выбрать документ.")
        return
    html_cards = ['<div class="flashcards-grid">']
    for индекс, карточка in enumerate(карточки, 1):
        вопрос = _html(карточка.get("front") or карточка.get("question", ""))
        ответ = _html(карточка.get("back") or карточка.get("answer", "")).replace("\n", "<br>")
        источник = _источник_карточки_html(карточка, фрагменты)
        html_cards.append(
            f'<details class="study-flashcard" style="animation-delay:{min(индекс * 0.035, 0.45):.2f}s">'
            '<summary>'
            f'<span class="flashcard-index">карточка {индекс:02d} · открыть ответ</span>'
            f'<span class="flashcard-front">{вопрос}</span>'
            '</summary>'
            f'<div class="flashcard-back">{ответ}'
            f'<div class="flashcard-source">Источник: {источник}</div>'
            '</div>'
            '</details>'
        )
    html_cards.append("</div>")
    st.markdown("".join(html_cards), unsafe_allow_html=True)


def показать_действие_если_есть(ключ):
    действие = st.session_state.pop(ключ, None)
    if действие:
        дизайн.показать_анимацию_действия(
            действие["заголовок"],
            действие["шаги"],
        )


def использованные_номера_цитат(текст, всего):
    номера = []
    for match in re.finditer(r"\[(\d+)\]", текст or ""):
        номер = int(match.group(1))
        if 1 <= номер <= всего and номер not in номера:
            номера.append(номер)
    return номера


def сделать_выдержку(текст, лимит=700):
    чистый = почистить_pdf_текст(текст or "")
    if len(чистый) <= лимит:
        return чистый
    предложения = re.split(r"(?<=[.!?])\s+", чистый)
    выбранные = []
    длина = 0
    for предложение in предложения:
        предложение = предложение.strip()
        if not предложение:
            continue
        if len(предложение) < 25 and выбранные:
            continue
        if длина + len(предложение) > лимит and выбранные:
            break
        выбранные.append(предложение)
        длина += len(предложение) + 1
    выдержка = " ".join(выбранные).strip() or чистый[:лимит].strip()
    if len(выдержка) < len(чистый):
        выдержка = выдержка.rstrip(" .") + "…"
    return выдержка


def показать_фрагмент_основания(номер, фр, key_prefix):
    документ = фр.get("document", "")
    страница = фр.get("page", "")
    score = фр.get("score", 0.0)
    заголовок = f"[{номер}] {документ} · стр. {страница} · score {score:.3f}"
    with st.expander(заголовок, expanded=(номер == 1)):
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
            st.caption(" · ".join(метки))
        if фр.get("case"):
            st.caption(f"Кейс: {получить_название_кейса(фр['case'])}")

        путь = notebooks.source_file_path(фр)
        if путь:
            try:
                st.download_button(
                    f"Скачать документ: {путь.name}",
                    data=путь.read_bytes(),
                    file_name=путь.name,
                    mime=mimetypes.guess_type(путь.name)[0] or "application/octet-stream",
                    key=f"{key_prefix}_download_{номер}_{abs(hash(str(путь)))}",
                    use_container_width=True,
                )
            except OSError as ошибка:
                st.caption(f"Не удалось прочитать файл: {ошибка}")

        st.markdown("**Выдержка:**")
        полный_текст = почистить_pdf_текст(фр.get("text", ""))
        st.markdown(сделать_выдержку(фр.get("text", "")))
        показать_картинки_фрагмента(фр, f"{key_prefix}_{номер}")
        if st.toggle("Перевести на русский", key=f"{key_prefix}_translate_{номер}"):
            with st.spinner("Перевожу фрагмент..."):
                перевод = перевести_на_русский(полный_текст)
            st.markdown("**Перевод:**")
            st.markdown(перевод)
        st.text_area(
            "Полный текст фрагмента",
            value=полный_текст,
            height=180,
            disabled=True,
            key=f"{key_prefix}_full_{номер}",
        )


def учебные_фрагменты(тетрадь, документ, тема, лимит=16):
    клиент = загрузить_qdrant()
    модель = загрузить_модель()
    тема = (тема or "").strip()
    if тема:
        точки = notebooks.search_notebook(
            клиент,
            модель,
            тетрадь,
            f"{документ or ''} {тема}",
            limit=лимит,
            user_id=пользователь_id,
            min_score=0.0,
        )
        фрагменты = сериализовать_фрагменты(точки)
        if документ and документ != "Все документы":
            фрагменты = [фр for фр in фрагменты if фр.get("document") == документ]
        if фрагменты:
            return фрагменты[:лимит]

    return notebooks.notebook_fragments(
        клиент,
        тетрадь,
        user_id=пользователь_id,
        document=документ,
        limit=лимит,
    )


def учебный_текстовый_ответ(задача, фрагменты, max_tokens=1800):
    if not _ключи_groq():
        return "Ошибка: GROQ_API_KEY не задан в файле .env"
    контекст = study_tools.fragments_context(фрагменты)
    ответ = вызвать_groq({
        "model": "llama-3.3-70b-versatile",
        "messages": [
            {"role": "system", "content": (
                "Ты учебный ассистент. Отвечай только по CONTEXT, на русском языке. "
                "Каждый тезис, определение, вопрос или вывод подкрепляй маркером [N] из CONTEXT. "
                "Если данных нет, прямо скажи что в выбранных документах этого нет. "
                "Не добавляй отдельный список источников в конце."
            )},
            {"role": "user", "content": f"CONTEXT:\n{контекст}\n\nTASK:\n{задача}"}
        ],
        "temperature": 0.1,
        "max_tokens": max_tokens,
    })
    текст = отрезать_источники(ответ.choices[0].message.content)
    return убрать_неверные_маркеры(текст, фрагменты)


def учебный_json_ответ(задача, фрагменты, max_tokens=1800):
    if not _ключи_groq():
        raise RuntimeError("GROQ_API_KEY не задан в файле .env")
    контекст = study_tools.fragments_context(фрагменты)
    ответ = вызвать_groq({
        "model": "llama-3.3-70b-versatile",
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": (
                "Ты учебный ассистент. Используй только CONTEXT. "
                "Верни строго валидный JSON без markdown. "
                "Все ответы, тезисы и объяснения должны быть на русском и с citation-маркерами [N]."
            )},
            {"role": "user", "content": f"CONTEXT:\n{контекст}\n\nTASK:\n{задача}"}
        ],
        "temperature": 0.1,
        "max_tokens": max_tokens,
    })
    return study_tools.parse_json_loose(ответ.choices[0].message.content)


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


_PDF_МУСОР_ПАТТЕРНЫ = (
    # URL'ы
    re.compile(r"https?://\S+|www\.\S+|doi\.org/\S+", re.IGNORECASE),
    # Лицензии Creative Commons
    re.compile(r"\(CC\s*BY[\w\-]*[^)]*\)|CC\s*BY[\w\-]*\s*\d\.\d", re.IGNORECASE),
    # Метки разделов с пробелами между буквами: "A B S T R A C T", "K e y w o r d s"
    re.compile(r"(?:\b[A-Za-z]\s+){3,}[A-Za-z]\b"),
    # Аффилиационные блоки университетов: "School/Department of …, City NNNNN, Country"
    re.compile(
        r"(?:School|Department|Institute|Faculty|College|Laboratory|University)\s+"
        r"(?:of|for)\s+[A-Z][^.\n]{5,120}(?:,\s*[A-Z][^.\n,]{2,40}){1,4}\s*\d{4,6}\b",
        re.IGNORECASE,
    ),
    # ORCID
    re.compile(r"\bORCID:?\s*\d{4}-\d{4}-\d{4}-\d{3}[0-9X]\b", re.IGNORECASE),
)


def _вырезать_pdf_мусор_из_ответа(текст: str) -> str:
    """Страховка от того, что LLM дословно копирует URL'ы / лицензии /
    аффилиации / разметку разделов из текста фрагмента в ответ. Применяется
    после `убрать_неверные_маркеры`, как последний шаг очистки.
    """
    if not текст:
        return текст
    результат = текст
    for паттерн in _PDF_МУСОР_ПАТТЕРНЫ:
        результат = паттерн.sub("", результат)
    # Чистим скобки, в которых после удаления URL осталось пусто/мусор.
    результат = re.sub(r"\(\s*[).,\s]*\)", "", результат)
    результат = re.sub(r"\(\s*\)", "", результат)
    # Свертываем повторные пробелы и переносы.
    результат = re.sub(r"[ \t]{2,}", " ", результат)
    результат = re.sub(r"\n{3,}", "\n\n", результат)
    # Удаляем пустые маркеры цитат, оказавшиеся в конце предложения после очистки.
    результат = re.sub(r"\s+([.,;:])", r"\1", результат)
    return результат.strip()


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
                    "Ты извлекаешь математические формулы из научного текста "
                    "и переписываешь их в корректном LaTeX.\n\n"
                    "ЧТО ИЗВЛЕКАТЬ:\n"
                    "— уравнения, функции, суммы/произведения/интегралы, "
                    "нормы, вероятности, argmin/argmax, операторы.\n\n"
                    "ЧТО ИГНОРИРОВАТЬ:\n"
                    "— одиночные числа, единицы измерения, ссылки на "
                    "литературу типа [12], даты, диапазоны страниц.\n\n"
                    "ПРАВИЛА LaTeX:\n"
                    "— все Unicode-символы заменяй на их LaTeX-эквиваленты "
                    "(см. таблицу ниже). НЕ оставляй греческие буквы, ∑, ∫, "
                    "≤, ∞ как символы — только командами.\n"
                    "— подстрочный индекс: одна буква x_1; несколько символов "
                    "в фигурных скобках: i_{ref}, x_{opt}.\n"
                    "— надстрочный: x^2, e^{-t/\\tau}.\n"
                    "— argmin/argmax: \\arg\\min, \\arg\\max.\n"
                    "— модуль |x|; норма \\|x\\|.\n\n"
                    "ТАБЛИЦА КОНВЕРТАЦИИ:\n"
                    "  ∑ Σ (оператор суммы) → \\sum\n"
                    "  Σ (матрица/множество, в обозначении) → \\Sigma\n"
                    "  ∏ → \\prod   ∫ → \\int   ∮ → \\oint\n"
                    "  ∈ → \\in   ∉ → \\notin   ⊂ → \\subset   ⊆ → \\subseteq\n"
                    "  ≤ → \\leq   ≥ → \\geq   ≠ → \\neq   ≈ → \\approx   ≡ → \\equiv\n"
                    "  ∞ → \\infty   → → \\to   ↦ → \\mapsto   ⇒ → \\Rightarrow\n"
                    "  α β γ δ ε → \\alpha \\beta \\gamma \\delta \\varepsilon\n"
                    "  θ λ μ ν ξ → \\theta \\lambda \\mu \\nu \\xi\n"
                    "  π σ τ φ ψ ω → \\pi \\sigma \\tau \\varphi \\psi \\omega\n"
                    "  ∂ → \\partial   ∇ → \\nabla   √ → \\sqrt{}\n"
                    "  · ∗ → \\cdot   × → \\times   ÷ → \\div   ± → \\pm\n"
                    "  − (Unicode-минус) → -   ′ → '   ° → ^\\circ\n\n"
                    "ПРИМЕРЫ:\n"
                    "  'f(x) = Σ m∈IQA w(m)·|m(ix)−m(iref)|' → "
                    "'f(x) = \\sum_{m \\in IQA} w(m) \\cdot |m(i_x) - m(i_{ref})|'\n"
                    "  'xopt ∈ argmin x∈X f(x)' → "
                    "'x_{opt} \\in \\arg\\min_{x \\in X} f(x)'\n"
                    "  'P(A∩B) = P(A)·P(B)' → 'P(A \\cap B) = P(A) \\cdot P(B)'\n"
                    "  'E = mc^2' → 'E = mc^2'  (уже корректный LaTeX)\n\n"
                    "ФОРМАТ ОТВЕТА — строго JSON:\n"
                    "  {\"formulas\": [{\"latex\": \"...\", \"описание\": \"...\"}]}\n"
                    "Внутри строки 'latex' каждый обратный слэш экранируй "
                    "удвоением, как в любом JSON: '\\sum' пиши как \"\\\\sum\".\n"
                    "'описание' — на русском, 1–2 предложения: что за формула "
                    "и что означают переменные.\n"
                    "Если формул нет — {\"formulas\": []}. Не выдумывай."
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



названия_кейсов = {"все": "Все кейсы"}
for ключ, данные in кейсы.items():
    названия_кейсов[ключ] = данные["название"]


дизайн.показать_шапку()
дизайн.показать_маркизу()
дизайн.показать_статистику()
дизайн.показать_подсказку_скролла()
дизайн.показать_фичи()
дизайн.показать_терминал()
дизайн.показать_вертикальный_отступ(1.4)
дизайн.показать_пайплайн()

пользователь_id = notebooks.get_user_id()
тетради = notebooks.list_notebooks(пользователь_id)
if тетради:
    st.session_state["активная_тетрадь_id"] = _id_тетради_по_умолчанию(
        тетради,
        st.session_state.get("активная_тетрадь_id"),
    )

вкладка1, вкладка2, вкладка3, вкладка4, вкладка5 = st.tabs(["Поиск", "Мои документы", "Учёба", "Кейсы", "Архитектура"])

with вкладка1:
    дизайн.показать_заголовок("Задайте вопрос базе знаний")

    вопрос_пользователя = st.text_area(
        "вопрос",
        value=st.session_state.get("вопрос_пользователя", ""),
        height=130,
        placeholder="Какие методы машинного обучения используются для предсказания растворимости молекул?",
        label_visibility="collapsed"
    )

    _, новая_схема, _ = выбрать_коллекцию()

    режимы_запроса = {
        "my": "Только по моим документам",
        "corpus": "Только по корпусу из интернета",
        "mixed": "Мои + корпус",
    }
    р1, р2 = st.columns([1.6, 1.1], gap="small")
    with р1:
        режим_запроса = st.radio(
            "Режим запроса",
            options=list(режимы_запроса.keys()),
            format_func=lambda к: режимы_запроса[к],
            horizontal=True,
            key="режим_запроса",
        )
    искать_в_моих = режим_запроса in ("my", "mixed")
    искать_в_корпусе = режим_запроса in ("corpus", "mixed")
    with р2:
        варианты_тетрадей = [т["id"] for т in тетради]
        выбранная_по_умолчанию = _id_тетради_по_умолчанию(тетради, st.session_state.get("активная_тетрадь_id"))
        индекс_тетради = варианты_тетрадей.index(выбранная_по_умолчанию) if выбранная_по_умолчанию in варианты_тетрадей else 0
        выбранная_тетрадь_id = st.selectbox(
            "Тетрадь",
            options=варианты_тетрадей,
            index=индекс_тетради,
            format_func=lambda notebook_id: notebooks.notebook_label(
                next(т for т in тетради if т["id"] == notebook_id)
            ),
            disabled=not искать_в_моих,
            key="поиск_тетрадь",
        ) if варианты_тетрадей else None
        if выбранная_тетрадь_id:
            st.session_state["активная_тетрадь_id"] = выбранная_тетрадь_id
        if not варианты_тетрадей and искать_в_моих:
            st.caption("Нет тетрадей — создайте во вкладке «Мои документы».")
    выбранная_тетрадь = notebooks.get_notebook(выбранная_тетрадь_id, пользователь_id) if выбранная_тетрадь_id else None

    к1, к2, к3 = st.columns([2, 1.3, 1.2], gap="small")
    with к1:
        выбор_кейса = st.selectbox(
            "Фильтр по кейсу",
            options=list(названия_кейсов.keys()),
            format_func=lambda к: названия_кейсов[к],
            disabled=not искать_в_корпусе,
        )
    with к2:
        количество_фрагментов = st.slider("Фрагментов", 3, 10, 5)
    with к3:
        дизайн.показать_вертикальный_отступ()
        кнопка = st.button("Найти ответ", type="primary", use_container_width=True)

    выбор_домена = "все"
    выбор_субдомена = "все"
    выбор_года_от = None
    выбор_языка = "все"
    вес_свежести = 0.0
    использовать_reranker = False
    if новая_схема and искать_в_корпусе:
        with st.expander("Расширенные фильтры (домен, год, язык, свежесть, reranker)", expanded=False):
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
                    min_value=1990, max_value=datetime.now(timezone.utc).year,
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
                использовать_reranker = st.checkbox(
                    "Reranker (точнее, +1–2 сек)",
                    value=False,
                    help="Перепроверяет top-K cross-encoder'ом BAAI/bge-reranker-v2-m3 (~600 МБ, скачивается один раз).",
                )

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
        try:
            модель_e5 = загрузить_модель()
            мои_точки = []
            корпус_точки = []
            заметка = None

            if искать_в_моих:
                if not выбранная_тетрадь:
                    st.session_state.результаты_поиска = {
                        "тип": "notebook_empty",
                        "тетрадь": "не выбрана",
                    }
                    st.rerun()
                with st.spinner(f"Поиск в тетради «{выбранная_тетрадь['title']}»..."):
                    мои_точки = notebooks.search_notebook(
                        загрузить_qdrant(),
                        модель_e5,
                        выбранная_тетрадь,
                        вопрос_пользователя,
                        limit=количество_фрагментов,
                        user_id=пользователь_id,
                    )

                if режим_запроса == "my" and not мои_точки:
                    st.session_state.результаты_поиска = {
                        "тип": "notebook_empty",
                        "тетрадь": выбранная_тетрадь["title"],
                    }
                    st.rerun()

            if искать_в_корпусе:
                лимит_корпуса = количество_фрагментов
                if режим_запроса == "mixed":
                    if not мои_точки:
                        заметка = (
                            f"В тетради «{выбранная_тетрадь['title']}» ответа не найдено; "
                            "использован корпус как бэкап."
                        ) if выбранная_тетрадь else None

                if лимит_корпуса > 0:
                    if новая_схема:
                        метки_p, прото_p, негативы_p = прототипы_доменов()
                        in_scope, авто_дом, авто_суб, скор_scope = проверить_scope(
                            вопрос_пользователя, модель_e5,
                            метки_p, прото_p, негативы_p,
                        )
                        if not in_scope:
                            if режим_запроса == "corpus" or not мои_точки:
                                st.session_state.результаты_поиска = {
                                    "тип": "off_topic",
                                    "scope_score": скор_scope,
                                    "примеры": примеры_in_scope_вопросов(),
                                }
                                st.stop()
                            лимит_корпуса = 0

                if лимит_корпуса > 0:
                    with st.spinner("Векторный поиск в harvest-корпусе Qdrant..."):
                        корпус_точки = найти_похожие(
                            вопрос_пользователя,
                            выбор_кейса,
                            лимит_корпуса,
                            домен=выбор_домена,
                            субдомен=выбор_субдомена,
                            год_от=выбор_года_от,
                            язык=выбор_языка,
                            recency_weight=вес_свежести,
                            использовать_reranker=использовать_reranker,
                        )

            if режим_запроса == "my":
                точки = мои_точки
            elif режим_запроса == "mixed":
                точки = sorted(
                    мои_точки + корпус_точки,
                    key=lambda т: float(getattr(т, "score", (т if isinstance(т, dict) else {}).get("score", 0.0)) or 0.0),
                    reverse=True,
                )[:количество_фрагментов]
            else:
                точки = корпус_точки

            if not точки:
                if искать_в_моих:
                    st.session_state.результаты_поиска = {
                        "тип": "notebook_empty",
                        "тетрадь": выбранная_тетрадь["title"] if выбранная_тетрадь else "не выбрана",
                    }
                else:
                    st.session_state.результаты_поиска = None
                    st.warning("Ничего не найдено. Попробуйте изменить вопрос или кейс.")
            else:
                with st.spinner("Генерация ответа · llama-3.3-70b..."):
                    ответ = получить_ответ_от_groq(вопрос_пользователя, точки)
                st.session_state.результаты_поиска = {
                    "тип": "rag",
                    "режим": режимы_запроса[режим_запроса],
                    "тетрадь": выбранная_тетрадь["title"] if выбранная_тетрадь and искать_в_моих else None,
                    "заметка": заметка,
                    "ответ": ответ,
                    "фрагменты": сериализовать_фрагменты(точки),
                }
                st.session_state["прокрутить_к_ответу"] = True
        except Exception as ошибка:
            st.session_state.результаты_поиска = None
            st.error(f"Ошибка подключения: {ошибка}")
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
    elif результат and результат.get("тип") == "notebook_empty":
        тетрадь_имя = результат.get('тетрадь', 'не выбрана')
        if тетрадь_имя == "не выбрана":
            st.warning("У вас нет тетрадей. Создайте тетрадь и загрузите документы во вкладке «Мои документы».")
        else:
            st.warning(f"В тетради «{тетрадь_имя}» ничего не найдено. Попробуйте режим «Мои + корпус» или загрузите документы.")
    elif результат and результат["тип"] == "rag":
        ответ = результат["ответ"]
        фрагменты = результат["фрагменты"]
        обогатить_картинками_соседних_страниц(фрагменты)

        есть_маркеры = bool(re.search(r"\[\d+\]", ответ))

        st.markdown('<div id="rag-answer-target"></div>', unsafe_allow_html=True)
        if st.session_state.pop("прокрутить_к_ответу", False):
            дизайн.прокрутить_к_якорю("rag-answer-target")
        дизайн.показать_мета_rag(len(фрагменты))
        if результат.get("режим"):
            st.caption("Режим: " + результат["режим"] + (f" · тетрадь: {результат['тетрадь']}" if результат.get("тетрадь") else ""))
        if результат.get("заметка"):
            дизайн.показать_тихую_заметку(результат["заметка"])
        показать_ответ_с_картинками(ответ, фрагменты)

        if есть_маркеры:
            дизайн.показать_заголовок("Источники", отступ_сверху_rem=3)
            дизайн.показать_источники_rag(фрагменты)
            показать_скачивание_источников(фрагменты, "rag")

        показать_экспорт_ответа("Ответ Навигатора", ответ, фрагменты, "rag_answer")

        дизайн.показать_заголовок("Фрагменты-основания", отступ_сверху_rem=3)
        номера_цитат = использованные_номера_цитат(ответ, len(фрагменты))
        if номера_цитат:
            st.caption("Сначала показаны только те фрагменты, на которые модель реально сослалась в ответе.")
            for номер in номера_цитат:
                показать_фрагмент_основания(номер, фрагменты[номер - 1], "used_fragment")
            остальные = [i for i in range(1, len(фрагменты) + 1) if i not in номера_цитат]
            if остальные:
                st.markdown("**Дополнительные найденные фрагменты:**")
                for номер in остальные:
                    показать_фрагмент_основания(номер, фрагменты[номер - 1], "extra_fragment")
        else:
            st.caption(
                "Модель не сослалась на эти найденные фрагменты в ответе. "
                "Показываю их как диагностический материал поиска."
            )
            for i, фр in enumerate(фрагменты, 1):
                показать_фрагмент_основания(i, фр, "diagnostic_fragment")

        дизайн.показать_статистику_поиска(_статистика_после_поиска(результат, тетради))

with вкладка2:
    дизайн.показать_заголовок("Мои документы")
    действие_документы = st.session_state.pop("действие_документы", None)
    if действие_документы:
        дизайн.показать_анимацию_действия(
            действие_документы["заголовок"],
            действие_документы["шаги"],
        )

    тетради = notebooks.list_notebooks(пользователь_id)
    варианты_тетрадей = [т["id"] for т in тетради]
    д1, д2 = st.columns([1.2, 1], gap="large")

    with д1:
        выбранная_по_умолчанию = _id_тетради_по_умолчанию(тетради, st.session_state.get("активная_тетрадь_id"))
        индекс_активной = варианты_тетрадей.index(выбранная_по_умолчанию) if выбранная_по_умолчанию in варианты_тетрадей else 0
        тетрадь_для_загрузки_id = st.selectbox(
            "Выберите тетрадь",
            options=варианты_тетрадей,
            index=индекс_активной,
            format_func=lambda notebook_id: notebooks.notebook_label(
                next(т for т in тетради if т["id"] == notebook_id)
            ),
            key="документы_тетрадь",
        ) if варианты_тетрадей else None
        if тетрадь_для_загрузки_id:
            st.session_state["активная_тетрадь_id"] = тетрадь_для_загрузки_id
        if not варианты_тетрадей:
            дизайн.показать_тихую_заметку("У вас пока нет тетрадей. Введите название справа и нажмите «Создать тетрадь».")

    with д2:
        новая_тетрадь = st.text_input(
            "Новая тетрадь",
            placeholder="Например: Кинетика экзамен",
            key="новая_тетрадь",
        )
        if st.button("Создать тетрадь", use_container_width=True):
            try:
                созданная = notebooks.create_notebook(новая_тетрадь, пользователь_id)
                st.session_state["активная_тетрадь_id"] = созданная["id"]
                st.session_state["действие_документы"] = {
                    "заголовок": "Готово",
                    "шаги": ["структура готова", "выбрана активной", "можно загружать файлы"],
                }
                st.rerun()
            except Exception as ошибка:
                st.error(str(ошибка))

    выбранная_для_документов = notebooks.get_notebook(
        st.session_state.get("активная_тетрадь_id"),
        пользователь_id,
    )

    if выбранная_для_документов:
        try:
            _doc_count = len(notebooks.notebook_documents(выбранная_для_документов))
            _doc_str = f" · {_doc_count} {'документ' if _doc_count == 1 else 'документа' if 2 <= _doc_count <= 4 else 'документов'}"
        except Exception:
            _doc_str = ""
        st.caption(f"Тетрадь: {выбранная_для_документов['title']}{_doc_str}")
        загруженные = st.file_uploader(
            "Перетащите файлы сюда",
            type=["pdf", "docx", "txt", "md", "pptx"],
            accept_multiple_files=True,
            help="Каждая тетрадь пишется в отдельную коллекцию Qdrant и не смешивается с harvest-корпусом.",
        )
        визуал_режим = st.checkbox(
            "Распознавать сканы и схемы (медленнее, но видит картинки)",
            value=False,
            help="Включает Tier 1 (RapidOCR) для PDF: текст со сканов попадает в индекс. "
                 "Локально, бесплатно, ~1–3 сек на страницу.",
            key="визуал_режим_тетрадь",
        )
        ocr_схем = st.checkbox(
            "Распознавать текст на схемах и диаграммах (OCR картинок, easyocr)",
            value=False,
            help="Извлекает текст с растровых схем-изображений в PDF (например, "
                 "стрелки и подписи на блок-схемах в слайдах лекций). Бесплатно, "
                 "локально, ~0.5–2 сек на картинку. Первый запуск скачает модели "
                 "easyocr (~70 MB).",
            key="ocr_схем_тетрадь",
        )
        groq_vision = False
        if визуал_режим:
            groq_доступен = виз.groq_vision_available()
            groq_vision = st.checkbox(
                "Дополнительно описывать графики/схемы через Groq Vision (платно, ~$0.0004 за страницу)",
                value=False,
                disabled=not groq_доступен,
                help="Если OCR не справился — посылает рендер страницы в Groq Vision "
                     "и сохраняет машинное описание. Только для страниц без текста.",
                key="groq_vision_тетрадь",
            )
            if not groq_доступен:
                st.caption("Чтобы включить Groq Vision, задай GROQ_API_KEY в .env.")
            свод = виз.budget_summary()
            if свод["total_pages"] > 0:
                st.caption(
                    f"Всего вызвано Groq Vision: {свод['total_pages']} стр., "
                    f"оценка стоимости ~${свод['estimated_cost_usd']:.4f}"
                )
        if st.button("Загрузить в выбранную тетрадь", type="primary", use_container_width=True):
            if not загруженные:
                st.warning("Выберите один или несколько файлов.")
            else:
                uploads = [(ф.name, ф.getvalue()) for ф in загруженные]
                статус = st.empty()
                def _on_progress(текст: str) -> None:
                    статус.caption(текст)
                try:
                    spinner_text = (
                        "Извлекаю текст + OCR, режу на чанки и пишу в Qdrant..."
                        if визуал_режим
                        else "Извлекаю текст, режу на чанки и пишу в Qdrant..."
                    )
                    with st.spinner(spinner_text):
                        итог = notebooks.ingest_uploaded_files(
                            загрузить_qdrant(),
                            загрузить_модель(),
                            выбранная_для_документов["id"],
                            uploads,
                            user_id=пользователь_id,
                            visual_mode=bool(визуал_режим),
                            use_groq_vision=bool(groq_vision),
                            use_ocr=bool(ocr_схем),
                            on_progress=_on_progress,
                        )
                    статус.empty()
                    msg = (
                        f"Добавлено файлов: {итог['added_files']}; "
                        f"пропущено дублей: {итог['skipped_files']}; "
                        f"чанков: {итог['chunks']}."
                    )
                    if итог.get("ocr_pages"):
                        msg += f" Tier 1 OCR: {итог['ocr_pages']} стр."
                    if итог.get("groq_vision_pages"):
                        msg += f" Tier 2 Groq Vision: {итог['groq_vision_pages']} стр."
                    st.success(msg)
                    for ошибка in итог["errors"]:
                        st.warning(ошибка)
                    шаги = ["текст извлечён"]
                    if итог.get("ocr_pages"):
                        шаги.append(f"OCR: {итог['ocr_pages']} стр.")
                    if итог.get("groq_vision_pages"):
                        шаги.append(f"Groq Vision: {итог['groq_vision_pages']} стр.")
                    шаги.extend(["чанки созданы", "Qdrant обновлён"])
                    st.session_state["действие_документы"] = {
                        "заголовок": "Готово",
                        "шаги": шаги,
                    }
                    st.rerun()
                except Exception as ошибка:
                    st.error(f"Ошибка загрузки: {ошибка}")

        свежая_тетрадь = notebooks.get_notebook(выбранная_для_документов["id"], пользователь_id)
        число_точек = notebooks.collection_count(загрузить_qdrant(), свежая_тетрадь)
        st.markdown(f"**В коллекции:** {число_точек} фрагмент(ов)")
        файлы = свежая_тетрадь.get("files", [])
        if not файлы:
            дизайн.показать_тихую_заметку("В этой тетради пока нет документов.")
        else:
            for файл in файлы:
                with st.expander(f"{файл['name']} · {файл.get('chunks', 0)} чанков"):
                    st.markdown(f"**Тип:** {файл.get('type', '')}")
                    st.markdown(f"**SHA-256:** `{файл.get('file_hash', '')[:16]}…`")
                    st.markdown(f"**Путь:** `{файл.get('path', '')}`")
                    st.caption(f"Загружен: {файл.get('uploaded_at', '')}")

with вкладка3:
    дизайн.показать_заголовок("Учебные фичи")

    тетради_учёба = notebooks.list_notebooks(пользователь_id)
    if not тетради_учёба:
        дизайн.показать_тихую_заметку("Сначала создайте тетрадь и загрузите документы во вкладке «Мои документы».")
    else:
        варианты_учёба = [т["id"] for т in тетради_учёба]
        выбранная_по_умолчанию = _id_тетради_по_умолчанию(тетради_учёба, st.session_state.get("активная_тетрадь_id"))
        индекс_учёба = варианты_учёба.index(выбранная_по_умолчанию) if выбранная_по_умолчанию in варианты_учёба else 0
        учебная_тетрадь_id = st.selectbox(
            "Тетрадь для учебных инструментов",
            options=варианты_учёба,
            index=индекс_учёба,
            format_func=lambda notebook_id: notebooks.notebook_label(
                next(т for т in тетради_учёба if т["id"] == notebook_id)
            ),
            key="учёба_тетрадь",
        )
        учебная_тетрадь = notebooks.get_notebook(учебная_тетрадь_id, пользователь_id)
        документы_учёба = ["Все документы"] + notebooks.notebook_documents(учебная_тетрадь)
        учебный_документ = st.selectbox(
            "Документ / лекция",
            options=документы_учёба,
            key="учёба_документ",
        )

        if len(документы_учёба) == 1:
            дизайн.показать_тихую_заметку("В выбранной тетради пока нет загруженных документов. Загрузите файлы внизу.")

        таб_конспект, таб_карточки, таб_квиз, таб_граф = st.tabs([
            "Конспект", "Флешкарточки", "Квиз", "Граф связей"
        ])

        with таб_конспект:
            тема_конспекта = st.text_input(
                "Глава или фокус",
                placeholder="Например: глава 3, катализ, лекция 5",
                key="тема_конспекта",
            )
            кн1, кн2 = st.columns(2, gap="small")
            with кн1:
                кнопка_вся_лекция = st.button("Тезисно всю лекцию", type="primary", use_container_width=True)
            with кн2:
                кнопка_глава = st.button("Конспект главы / темы", use_container_width=True)

            if кнопка_вся_лекция or кнопка_глава:
                фокус = "" if кнопка_вся_лекция else тема_конспекта
                фрагменты_учёба = учебные_фрагменты(учебная_тетрадь, учебный_документ, фокус, лимит=18)
                if not фрагменты_учёба:
                    st.warning("В выбранной тетради нет фрагментов для конспекта.")
                else:
                    задача = (
                        "Составь тезисный конспект всей выбранной лекции/документа. "
                        "Структура: 1) ключевая идея, 2) тезисы, 3) термины, 4) формулы/методы если есть, 5) что стоит выучить."
                        if кнопка_вся_лекция else
                        f"Составь конспект по фокусу «{тема_конспекта}». Структура: ключевые тезисы, определения, методы, формулы если есть, вопросы для самопроверки."
                    )
                    with st.spinner("Генерирую конспект с citation..."):
                        конспект = учебный_текстовый_ответ(задача, фрагменты_учёба)
                    st.session_state["конспект_результат"] = {
                        "ответ": конспект,
                        "фрагменты": фрагменты_учёба,
                        "заголовок": f"Конспект: {учебный_документ}",
                    }
                    st.session_state["действие_учёба"] = {
                        "заголовок": "Найдено",
                        "шаги": ["фрагменты выбраны", "тезисы собраны", "источники привязаны"],
                    }

            if st.session_state.get("конспект_результат"):
                показать_действие_если_есть("действие_учёба")
                результат_конспект = st.session_state["конспект_результат"]
                обогатить_картинками_соседних_страниц(результат_конспект["фрагменты"])
                показать_ответ_с_картинками(
                    результат_конспект["ответ"],
                    результат_конспект["фрагменты"],
                    key_prefix="notes",
                )
                дизайн.показать_заголовок("Источники конспекта", отступ_сверху_rem=2)
                дизайн.показать_источники_rag(результат_конспект["фрагменты"])
                показать_скачивание_источников(результат_конспект["фрагменты"], "notes")
                показать_экспорт_ответа(
                    результат_конспект["заголовок"],
                    результат_конспект["ответ"],
                    результат_конспект["фрагменты"],
                    "notes_export",
                )

        with таб_карточки:
            тема_карточек = st.text_input(
                "Тема для карточек",
                placeholder="Например: уравнение Аррениуса, QSAR, катализ",
                key="тема_карточек",
            )
            число_карточек = st.slider("Количество карточек", 5, 30, 12, key="число_карточек")
            if st.button("Сгенерировать учебные карточки", type="primary", use_container_width=True):
                фрагменты_карточки = учебные_фрагменты(учебная_тетрадь, учебный_документ, тема_карточек, лимит=16)
                if not фрагменты_карточки:
                    st.warning("Нет фрагментов для карточек.")
                else:
                    задача = (
                        f"Сгенерируй {число_карточек} учебных флешкарточек по теме «{тема_карточек or учебный_документ}». "
                        "Формат JSON: {\"cards\":[{\"front\":\"вопрос\", \"back\":\"краткий ответ\", \"source\":\"[N]\"}]}. "
                        "Вопросы должны проверять понимание, а не только определения."
                    )
                    with st.spinner("Генерирую карточки..."):
                        данные = учебный_json_ответ(задача, фрагменты_карточки)
                    карточки = обогатить_карточки_источниками(
                        данные.get("cards") or данные.get("items") or [],
                        фрагменты_карточки,
                    )
                    имя_набора = тема_карточек or учебный_документ or учебная_тетрадь["title"]
                    export_prefix = f"{учебная_тетрадь['title']}_{имя_набора}"
                    package_id = f"{пользователь_id}:{учебная_тетрадь['id']}:{имя_набора}"
                    экспорты_карточек = {}
                    if карточки:
                        экспорты_карточек = study_tools.save_flashcard_exports(
                            карточки,
                            f"Навигатор - {имя_набора}",
                            Path("exports") / "cards" / пользователь_id / учебная_тетрадь["id"],
                            prefix=export_prefix,
                            package_id=package_id,
                        )
                    st.session_state["карточки_результат"] = {
                        "cards": карточки,
                        "фрагменты": фрагменты_карточки,
                        "deck": f"Навигатор - {имя_набора}",
                        "package_id": package_id,
                        "export_prefix": export_prefix,
                        "exports": экспорты_карточек,
                    }
                    st.session_state["действие_учёба"] = {
                        "заголовок": "Найдено",
                        "шаги": ["фрагменты найдены", "вопросы собраны", "страницы привязаны"],
                    }

            if st.session_state.get("карточки_результат"):
                показать_действие_если_есть("действие_учёба")
                карточки_результат = st.session_state["карточки_результат"]
                фрагменты_карточек = карточки_результат.get("фрагменты", [])
                карточки = обогатить_карточки_источниками(
                    карточки_результат.get("cards", []),
                    фрагменты_карточек,
                )
                карточки_результат["cards"] = карточки
                показать_учебные_карточки(карточки, фрагменты_карточек)
                if карточки and not карточки_результат.get("exports"):
                    карточки_результат["exports"] = study_tools.save_flashcard_exports(
                        карточки,
                        карточки_результат["deck"],
                        Path("exports") / "cards" / пользователь_id / учебная_тетрадь["id"],
                        prefix=карточки_результат.get("export_prefix") or карточки_результат["deck"],
                        package_id=карточки_результат.get("package_id", ""),
                    )
                    st.session_state["карточки_результат"] = карточки_результат

                экспорты_карточек = карточки_результат.get("exports") or {}
                dl1, dl2 = st.columns(2, gap="small")
                with dl1:
                    st.download_button(
                        "Скачать карточки Word (.docx)",
                        data=экспорты_карточек.get("docx_bytes") or study_tools.cards_docx_export(
                            карточки_результат.get("deck", "Учебные карточки"),
                            карточки,
                        ),
                        file_name=Path(экспорты_карточек.get("docx_path") or "navigator_flashcards.docx").name,
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        key="flashcards_docx",
                        use_container_width=True,
                    )
                with dl2:
                    st.download_button(
                        "Скачать таблицу (.csv)",
                        data=экспорты_карточек.get("csv_bytes") or study_tools.cards_to_csv(карточки),
                        file_name=Path(экспорты_карточек.get("csv_path") or "navigator_flashcards.csv").name,
                        mime="text/csv",
                        key="flashcards_csv",
                        use_container_width=True,
                    )
                apkg = экспорты_карточек.get("apkg_bytes")
                with st.expander("Дополнительно: экспорт для Anki", expanded=False):
                    st.download_button(
                        "Скачать TSV",
                        data=экспорты_карточек.get("tsv_bytes") or study_tools.cards_to_tsv(карточки),
                        file_name=Path(экспорты_карточек.get("tsv_path") or "navigator_flashcards.tsv").name,
                        mime="text/tab-separated-values",
                        key="flashcards_tsv",
                        use_container_width=True,
                    )
                    if apkg:
                        st.download_button(
                            "Скачать .apkg",
                            data=apkg,
                            file_name=Path(экспорты_карточек.get("apkg_path") or "navigator_flashcards.apkg").name,
                            mime="application/octet-stream",
                            key="flashcards_apkg",
                            use_container_width=True,
                        )
                    else:
                        st.caption("Пакет .apkg появится, если установлен genanki. Основные файлы выше уже подходят обычному пользователю.")

        with таб_квиз:
            тема_квиза = st.text_input(
                "Тема",
                placeholder="Например: лекция 5, глава 3, молекулярные отпечатки",
                key="тема_квиза",
            )
            число_вопросов = st.slider("Вопросов", 3, 15, 10, key="число_вопросов")
            if st.button("Создать квиз", type="primary", use_container_width=True):
                фрагменты_квиз = учебные_фрагменты(учебная_тетрадь, учебный_документ, тема_квиза, лимит=18)
                if not фрагменты_квиз:
                    st.warning("Нет фрагментов для квиза.")
                else:
                    задача = (
                        f"Составь квиз из {число_вопросов} вопросов по теме «{тема_квиза or учебный_документ}». "
                        "Формат JSON: {\"questions\":[{\"id\":1,\"question\":\"...\", \"ideal_answer\":\"...\", \"source\":\"[N]\"}]}. "
                        "Смешай определения, применение, причинно-следственные вопросы и короткие задачи."
                    )
                    with st.spinner("Готовлю вопросы..."):
                        данные = учебный_json_ответ(задача, фрагменты_квиз)
                    st.session_state["квиз_результат"] = {
                        "questions": данные.get("questions") or данные.get("items") or [],
                        "фрагменты": фрагменты_квиз,
                    }
                    st.session_state["действие_учёба"] = {
                        "заголовок": "Найдено",
                        "шаги": ["темы найдены", "вопросы созданы", "можно отвечать"],
                    }

            if st.session_state.get("квиз_результат"):
                показать_действие_если_есть("действие_учёба")
                квиз = st.session_state["квиз_результат"]
                вопросы = квиз["questions"]
                for _qk, _qv in st.session_state.get("квиз_ответы_сохранённые", {}).items():
                    if f"ответ_квиз_{_qk}" not in st.session_state:
                        st.session_state[f"ответ_квиз_{_qk}"] = _qv
                with st.form("форма_квиза"):
                    ответы = {}
                    for вопрос in вопросы:
                        qid = str(вопрос.get("id") or len(ответы) + 1)
                        st.markdown(f"**{qid}. {вопрос.get('question', '')}** {вопрос.get('source', '')}")
                        ответы[qid] = st.text_area("Ваш ответ", key=f"ответ_квиз_{qid}", height=90)
                    проверить = st.form_submit_button("Проверить ответы")
                if проверить:
                    ответы_заполненные = {qid: ans for qid, ans in ответы.items() if ans.strip()}
                    st.session_state["квиз_ответы_сохранённые"] = {
                        **st.session_state.get("квиз_ответы_сохранённые", {}),
                        **ответы_заполненные,
                    }
                    if not ответы_заполненные:
                        st.warning("Введите хотя бы один ответ перед проверкой.")
                    else:
                        payload = {
                            "questions": вопросы,
                            "student_answers": ответы_заполненные,
                        }
                        задача = (
                            "Оцени ответы студента по 0-2 балла. "
                            "Оценивай ТОЛЬКО вопросы, у которых есть непустой ответ в student_answers — остальные пропускай. "
                            "max_total считай только по отвеченным вопросам (количество ответов × 2). "
                            "Верни JSON: {\"total\":число,\"max_total\":число,\"results\":[{\"id\":...,\"score\":0,\"feedback\":\"...\",\"correct_answer\":\"...\"}]}.\n"
                            + json.dumps(payload, ensure_ascii=False)
                        )
                        with st.spinner("Проверяю ответы..."):
                            оценка = учебный_json_ответ(задача, квиз["фрагменты"], max_tokens=2200)
                        st.session_state["оценка_квиза"] = оценка
                        st.session_state["действие_учёба"] = {
                            "заголовок": "Готово",
                            "шаги": ["ответы прочитаны", "баллы рассчитаны", "разбор готов"],
                        }

                if st.session_state.get("оценка_квиза"):
                    показать_действие_если_есть("действие_учёба")
                    оценка = st.session_state["оценка_квиза"]
                    st.markdown(f"**Итог:** {оценка.get('total', 0)} / {оценка.get('max_total', len(вопросы) * 2)}")
                    for item in оценка.get("results", []):
                        with st.expander(f"Вопрос {item.get('id')} · {item.get('score')} балл(ов)"):
                            st.markdown(item.get("feedback", ""))
                            st.markdown("**Правильный ответ:** " + str(item.get("correct_answer", "")))

        with таб_граф:
            тема_графа = st.text_input(
                "Тема",
                placeholder="Например: катализ, растворимость, GNN",
                key="тема_графа",
            )
            if st.button("Построить граф связей", type="primary", use_container_width=True):
                фрагменты_граф = учебные_фрагменты(учебная_тетрадь, учебный_документ, тема_графа, лимит=18)
                if not фрагменты_граф:
                    st.warning("Нет фрагментов для графа.")
                else:
                    задача = (
                        "Извлеки 8-14 ключевых сущностей/терминов и связи между ними. "
                        "Формат JSON: {\"nodes\":[{\"id\":\"term\",\"label\":\"термин\",\"theses\":[\"тезис [N]\"]}],"
                        "\"edges\":[{\"source\":\"term1\",\"target\":\"term2\",\"label\":\"тип связи\"}]}. "
                        "Тезисы должны ссылаться на [N]."
                    )
                    with st.spinner("Извлекаю сущности и связи..."):
                        граф = учебный_json_ответ(задача, фрагменты_граф)
                    st.session_state["граф_результат"] = {
                        "graph": граф,
                        "фрагменты": фрагменты_граф,
                    }
                    st.session_state["действие_учёба"] = {
                        "заголовок": "Найдено",
                        "шаги": ["сущности извлечены", "связи найдены", "узлы отрисованы"],
                    }

            if st.session_state.get("граф_результат"):
                показать_действие_если_есть("действие_учёба")
                граф_результат = st.session_state["граф_результат"]
                граф = граф_результат["graph"]
                _гузлы = граф.get("nodes", [])
                _грёбра = граф.get("edges", [])
                _adj: dict = {str(n.get("id") or n.get("label")): [] for n in _гузлы}
                for _e in _грёбра:
                    _s, _t = str(_e.get("source", "")), str(_e.get("target", ""))
                    if _s in _adj: _adj[_s].append(_t)
                    if _t in _adj: _adj[_t].append(_s)
                _id2label = {str(n.get("id") or n.get("label")): str(n.get("label") or n.get("id")) for n in _гузлы}
                _degree = {nid: len(nb) for nid, nb in _adj.items()}

                st.caption(f"Концепты · {len(_гузлы)} узлов · {len(_грёбра)} связей")
                _кол1, _кол2 = st.columns(2, gap="small")
                for _i, _n in enumerate(_гузлы):
                    _nid = str(_n.get("id") or _n.get("label"))
                    _nlabel = str(_n.get("label") or _n.get("id"))
                    _theses = _n.get("theses", [])
                    _connected = [_id2label.get(_c, _c) for _c in _adj.get(_nid, [])]
                    _deg = _degree.get(_nid, 0)
                    _card_class = "mind-card is-hub" if _deg > 2 else "mind-card"
                    _conn_html = "".join(
                        f"<span class='mind-chip'>{_l}</span>"
                        for _l in _connected
                    )
                    _li_html = "".join(
                        f"<li style='margin-bottom:5px;line-height:1.55;color:#a3a3a3'>{_t}</li>"
                        for _t in _theses
                    ) if _theses else "<li style='color:#525252;font-style:italic'>тезисы не извлечены</li>"
                    _degree_badge = (
                        '<span style="background:#2563eb;color:#fff;border-radius:50%;width:18px;'
                        'height:18px;display:inline-flex;align-items:center;justify-content:center;'
                        'font-size:0.65rem;font-weight:700;margin-left:7px;vertical-align:middle">'
                        + str(_deg) + '</span>'
                    ) if _deg > 0 else ""
                    _connections_block = (
                        '<div style="margin-bottom:0.55rem;line-height:1.8">'
                        + _conn_html + '</div>'
                    ) if _conn_html else ""
                    _card = (
                        f"<div class='{_card_class}'>"
                        f"<div style='font-weight:600;font-size:0.95rem;color:#f0f0f0;margin-bottom:0.55rem'>"
                        f"{_nlabel}"
                        f"{_degree_badge}"
                        f"</div>"
                        f"{_connections_block}"
                        f"<ul style='margin:0;padding-left:1.1rem;font-size:0.85rem'>{_li_html}</ul>"
                        f"</div>"
                    )
                    with (_кол1 if _i % 2 == 0 else _кол2):
                        st.markdown(_card, unsafe_allow_html=True)
                st.caption("Граф связей")
                # Чистый SVG без динамических JS-модулей: работает за tunnel'ами
                # (lhr.life, ngrok), где st.graphviz_chart ломается из-за того,
                # что прокси не отдаёт chunked ES-modules компонента графа.
                st.markdown(_построить_svg_граф(_гузлы, _грёбра, _adj, _id2label, _degree),
                            unsafe_allow_html=True)
                показать_скачивание_источников(граф_результат["фрагменты"], "mindmap")

with вкладка4:
    дизайн.показать_кейсы(кейсы)

with вкладка5:
    дизайн.показать_архитектуру()
