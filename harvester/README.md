# Harvester — автосбор корпуса

Скачивает свежие PDF из открытых источников по теме «химия + IT»:

- **arXiv** — категории `cs.LG, cs.AI, cs.CL, stat.ML, physics.chem-ph, cond-mat.mtrl-sci, q-bio.BM, q-bio.QM`
- **chemRxiv** — все препринты
- **OpenAlex** — concepts: Cheminformatics, Machine learning, Chemistry, Materials science, Computer science (нужен email в User-Agent)

## Запуск

```bash
pip install -r harvester/requirements.txt
python -m harvester.run --budget 300 --year-min 2020 --email you@example.com
```

PDF попадают в `all_pdfs/`, метаданные — в `harvested_meta/`. Состояние (курсоры по
источникам, скачанные ID) — в `harvester/state.json`. Прогрессивно докачивается при каждом запуске.

После прогона:

```bash
python ingest_доп.py    # дочанкует только новые файлы
python embed_resume.py  # инкрементально докинет векторы
```

## GitHub Actions (бесконечный режим)

См. `.github/workflows/harvest.yml` (PR #2). Раз в 3 часа поднимается раннер,
запускает `harvester.run` с бюджетом, коммитит обновлённый `state.json` и
загружает векторы в Qdrant Cloud / VPS.

## Этика

Используются ТОЛЬКО открытые легальные API. Никаких Sci-Hub / LibGen / зеркал
платных журналов. OpenAlex / arXiv / chemRxiv требуют только User-Agent с
email и щадящий rate-limit (≤2 req/s) — никаких прокси и обходов не нужно.
