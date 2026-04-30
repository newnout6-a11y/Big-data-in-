"""Классификатор домена документа (chem / it / other) для балансировки.

Цель: не допустить перекоса корпуса — например, чтобы IT-домен не
забил на 80% химию (или наоборот). Работает до ingest: на лету по
источнику + заголовку + abstract, без ML.

Стратегия:
  1. Источник задаёт априорный домен (chemrxiv/cyberleninka-chem → chem,
     stackexchange:stackoverflow → it, и т.п.).
  2. Если источник нейтральный (arxiv, openalex, europepmc, semanticscholar),
     проверяем ключевые слова в title + abstract.
  3. Fallback → "other".
"""
from __future__ import annotations

import re
from typing import Iterable


# Химические маркеры — английские + русские корни
_CHEM_КЛЮЧИ = [
    # English
    r"\bchemistry\b", r"\bchemical\b", r"\bmolecul", r"\breaction", r"\bcatal",
    r"\bsynthes", r"\bdrug\b", r"\bpharma", r"\bprotein", r"\benzyme",
    r"\bligand", r"\bmaterials?\b", r"\bcrystal", r"\bpolymer", r"\bDFT\b",
    r"\bdensity functional", r"\bquantum chem", r"\babinitio\b", r"\bab[- ]initio\b",
    r"\bretrosynth", r"\bcheminform", r"\bQSAR\b", r"\bdocking", r"\bSMILES\b",
    r"\bspectroscop", r"\bNMR\b", r"\bcrystallograph",
    # Русский
    r"хими", r"молекул", r"реакци", r"катализ", r"синтез", r"полимер",
    r"материаловед", r"кристалл", r"лекарственн", r"фермент", r"белок",
]

# IT / CS маркеры
_IT_КЛЮЧИ = [
    # English
    r"\balgorithm", r"\bmachine learning\b", r"\bdeep learning\b", r"\bneural network",
    r"\btransformer", r"\battention mechanism", r"\bGPT\b", r"\bNLP\b",
    r"\bnatural language", r"\breinforcement learning\b", r"\bcomputer vision\b",
    r"\bdatabase", r"\bdistributed", r"\bparallel comput", r"\bkubernetes\b",
    r"\bdocker\b", r"\bjavascript\b", r"\btypescript\b", r"\bpython\b",
    r"\bsoftware engineering\b", r"\boperating system\b", r"\bnetwork protocol",
    r"\boptimization algorithm\b", r"\bgraph neural\b", r"\bLLM\b",
    r"\btransfer learning\b", r"\bself[- ]supervised\b", r"\bdiffusion model\b",
    # Русский
    r"машинное обучение", r"нейросет", r"алгоритм", r"программирован",
    r"искусственный интеллект", r"компьютер", r"база данных",
]


_RE_CHEM = re.compile("|".join(_CHEM_КЛЮЧИ), re.IGNORECASE)
_RE_IT = re.compile("|".join(_IT_КЛЮЧИ), re.IGNORECASE)


# Априорный домен по источнику (+ сайту для stackexchange)
_ИСТОЧНИК_ДОМЕН: dict[str, str] = {
    "chemrxiv": "chem",
    # остальные — нейтральные, классифицируем по тексту
}


def _подсчитать_маркеры(текст: str) -> tuple[int, int]:
    """Возвращает (счёт_chem, счёт_it) в данном тексте."""
    if not текст:
        return 0, 0
    chem = len(_RE_CHEM.findall(текст))
    it = len(_RE_IT.findall(текст))
    return chem, it


def классифицировать(источник: str, название: str = "", abstract: str = "",
                     doc_id: str = "") -> str:
    """Возвращает 'chem' | 'it' | 'other'."""
    # 1. Сильный приоритет — источник
    if источник in _ИСТОЧНИК_ДОМЕН:
        return _ИСТОЧНИК_ДОМЕН[источник]

    # 2. stackexchange: сайт вшит в doc_id (se:<site>:<id>)
    if источник == "stackexchange" and doc_id:
        части = doc_id.split(":")
        if len(части) >= 2:
            сайт = части[1].lower()
            if сайт in {"chemistry"}:
                return "chem"
            if сайт in {"stackoverflow", "ai", "datascience", "cs", "softwareengineering"}:
                return "it"

    # 3. Текст title+abstract
    текст = f"{название}\n{abstract}".strip()
    chem, it = _подсчитать_маркеры(текст)
    if chem == 0 and it == 0:
        return "other"
    if chem > it * 1.5:
        return "chem"
    if it > chem * 1.5:
        return "it"
    # Слабое большинство → выбираем побольше, без домена = other
    if chem > it:
        return "chem"
    if it > chem:
        return "it"
    return "other"


def рассчитать_коэффициенты(counts: dict[str, int], *, минимум_всего: int = 50) -> dict[str, float]:
    """На основе накопленных счётов возвращает мультипликаторы бюджета на домен.

    Если какой-то домен отстаёт → даём ему >1.0, ведущий получает <1.0.
    При низком общем объёме (первые запуски) возвращает все 1.0, чтобы
    не переколбасить случайным шумом.
    """
    всего = sum(counts.values())
    if всего < минимум_всего or not counts:
        return {к: 1.0 for к in ("chem", "it", "other")}

    # Идеальное распределение — 45% chem, 45% it, 10% other
    идеал = {"chem": 0.45, "it": 0.45, "other": 0.10}
    коэф: dict[str, float] = {}
    for дом, цель in идеал.items():
        доля = counts.get(дом, 0) / всего if всего else 0
        if доля <= 0:
            коэф[дом] = 2.0  # полностью отсутствует → мощный буст
        else:
            # Отношение цели к факту, но мягко (√ чтобы не скакало)
            raw = цель / доля if доля > 0 else 2.0
            # Ограничим в [0.25, 2.5]
            коэф[дом] = max(0.25, min(2.5, raw ** 0.5))
    return коэф


# Источники по их ожидаемому домену (для масштабирования бюджетов)
ИСТОЧНИК_ОЖИДАЕМЫЙ_ДОМЕН: dict[str, str] = {
    "arxiv": "it",              # cs.LG, cs.AI, stat.ML, physics.chem-ph — преимущественно IT
    "chemrxiv": "chem",
    "openalex": "chem",         # концепты наполовину химия, но в нашей подборке — преим. chem
    "europepmc": "chem",        # медбио + химия
    "cyberleninka": "chem",     # в нашем scope-фильтре оставляем chem-темы
    "stackexchange": "it",      # большинство сайтов — IT
    "semanticscholar": "it",    # queries преим. ML/DL
    "core": "it",
}
