"""Таксономия знаний: химия + IT + их пересечение.

Каждый субдомен — короткое описание-прототип на двух языках.
Используется эмбеддинговым классификатором (классификатор.py)
для авторазметки чанков и маршрутизации запросов.
"""


ДОМЕНЫ = {
    "chemistry": {
        "название": "Химия",
        "описание": "Фундаментальная и прикладная химия: вещество, реакции, синтез.",
        "subdomains": {
            "organic": {
                "название": "Органическая химия",
                "прототип": (
                    "Органическая химия: синтез органических соединений, "
                    "функциональные группы, механизмы реакций, ретросинтез, "
                    "стереохимия, спектроскопия органических молекул, "
                    "named reactions, total synthesis, retrosynthesis, "
                    "organic compounds, functional groups, reaction mechanisms."
                ),
            },
            "inorganic": {
                "название": "Неорганическая химия",
                "прототип": (
                    "Неорганическая химия: координационные соединения, металлокомплексы, "
                    "кристаллохимия, оксиды, соли, кислоты и основания, химия элементов, "
                    "inorganic chemistry, coordination compounds, metal complexes, "
                    "crystal chemistry, oxides, salts, periodic table elements."
                ),
            },
            "physical": {
                "название": "Физическая химия",
                "прототип": (
                    "Физическая химия: термодинамика, кинетика реакций, квантовая химия, "
                    "молекулярная динамика, статистическая термодинамика, фазовые равновесия, "
                    "physical chemistry, thermodynamics, reaction kinetics, quantum chemistry, "
                    "molecular dynamics, phase equilibria, statistical mechanics."
                ),
            },
            "analytical": {
                "название": "Аналитическая химия",
                "прототип": (
                    "Аналитическая химия: качественный и количественный анализ, "
                    "хроматография, масс-спектрометрия, ЯМР, ИК-спектроскопия, "
                    "пробоподготовка, метрология, валидация методов, "
                    "analytical chemistry, chromatography, mass spectrometry, "
                    "NMR, IR spectroscopy, sample preparation, method validation."
                ),
            },
            "catalysis": {
                "название": "Катализ",
                "прототип": (
                    "Катализ: гомогенный и гетерогенный катализ, ферменты, "
                    "активность катализатора, селективность, TOF, поверхность катализатора, "
                    "noble metal catalysts, zeolites, MOF catalysts, "
                    "catalysis, homogeneous, heterogeneous, enzymes, turnover frequency, "
                    "catalyst activity, selectivity, surface chemistry."
                ),
            },
            "materials": {
                "название": "Материаловедение и материалы",
                "прототип": (
                    "Материаловедение: кристаллические структуры, перовскиты, MOF, COF, "
                    "наноматериалы, полимеры, металлы и сплавы, керамика, "
                    "механические свойства, теплопроводность, band gap, "
                    "materials science, crystal structures, perovskites, MOF, "
                    "nanomaterials, polymers, alloys, ceramics, band gap, mechanical properties."
                ),
            },
            "biochem_med": {
                "название": "Биохимия и медицинская химия",
                "прототип": (
                    "Биохимия и медицинская химия: белки, ферменты, нуклеиновые кислоты, "
                    "метаболизм, лекарственные молекулы, фармакология, ADMET, "
                    "лиганды, drug-target interaction, biochemistry, medicinal chemistry, "
                    "proteins, enzymes, drug molecules, pharmacology, ADMET properties."
                ),
            },
            "process_tech": {
                "название": "Химическая технология и производство",
                "прототип": (
                    "Химическая технология: реакторы, ректификация, теплообмен, "
                    "контроль производства, soft sensors, технологический процесс, "
                    "масштабирование, безопасность химпроизводства, "
                    "chemical engineering, reactors, distillation, heat exchangers, "
                    "process monitoring, soft sensors, scale-up, process safety."
                ),
            },
        },
    },
    "it_chem": {
        "название": "IT в химии (пересечение)",
        "описание": "Применение ИТ, машинного обучения и Big Data к химическим задачам.",
        "subdomains": {
            "cheminformatics": {
                "название": "Хемоинформатика",
                "прототип": (
                    "Хемоинформатика: молекулярные дескрипторы и отпечатки, SMILES, InChI, "
                    "RDKit, виртуальный скрининг, базы данных молекул, "
                    "химическая графовая теория, similarity search, "
                    "cheminformatics, molecular descriptors, fingerprints, SMILES, "
                    "RDKit, virtual screening, chemical databases, similarity search."
                ),
            },
            "ml_for_chem": {
                "название": "Машинное обучение для химии",
                "прототип": (
                    "Машинное обучение для химии: graph neural networks для молекул, "
                    "transformers для SMILES, predictive models, регрессия свойств, "
                    "QSAR, молекулярная генерация, deep learning chemistry, "
                    "MPNN, MEGNet, ChemBERTa, MolFormer, Schnet, "
                    "machine learning chemistry, GNN molecules, generative models for molecules."
                ),
            },
            "computational_chem": {
                "название": "Вычислительная химия",
                "прототип": (
                    "Вычислительная химия: DFT, ab initio, Hartree-Fock, MP2, CCSD, "
                    "молекулярная динамика, force fields, GROMACS, AMBER, "
                    "квантовая химия, расчёт энергии, оптимизация геометрии, "
                    "computational chemistry, DFT, density functional theory, "
                    "molecular dynamics, force field, ab initio, GROMACS."
                ),
            },
            "drug_discovery_ml": {
                "название": "ML в разработке лекарств",
                "прототип": (
                    "Разработка лекарств с ML: предсказание активности, докинг, "
                    "AlphaFold, drug-target affinity, генерация лекарственных молекул, "
                    "лиганд-белковое взаимодействие, ADMET prediction, "
                    "drug discovery machine learning, virtual screening, docking, "
                    "AlphaFold, drug-target interaction, generative drug design."
                ),
            },
            "materials_informatics": {
                "название": "Информатика материалов",
                "прототип": (
                    "Информатика материалов: предсказание свойств материалов нейросетями, "
                    "Materials Project, AFLOW, OQMD, NOMAD, high-throughput screening, "
                    "active learning материалов, генеративные модели кристаллов, "
                    "materials informatics, materials property prediction, "
                    "Materials Project, high-throughput, active learning, crystal generation."
                ),
            },
            "lab_automation": {
                "название": "Автоматизация лаборатории и self-driving labs",
                "прототип": (
                    "Автоматизация эксперимента: self-driving labs, роботизированный синтез, "
                    "Bayesian optimization условий реакции, активное обучение, "
                    "high-throughput screening, electronic lab notebooks, "
                    "lab automation, self-driving lab, autonomous experimentation, "
                    "Bayesian reaction optimization, robotic chemistry."
                ),
            },
            "text_mining_chem": {
                "название": "Извлечение химических данных из текстов",
                "прототип": (
                    "Извлечение данных из научных статей и патентов: NER химических сущностей, "
                    "ChemDataExtractor, DECIMER, парсинг структур, реакций, условий, "
                    "patent mining, chemical text mining, named entity recognition chemistry, "
                    "извлечение реакций, аннотация молекул в тексте."
                ),
            },
            "ord_data": {
                "название": "Базы реакций и FAIR-данные",
                "прототип": (
                    "Базы данных химических экспериментов: Open Reaction Database (ORD), "
                    "электронный лабораторный журнал (ELN), FAIR principles, "
                    "metadata, reproducibility, data management для химии, "
                    "open reaction database, electronic lab notebook, FAIR data, "
                    "experimental metadata, reproducibility chemistry."
                ),
            },
        },
    },
    "it": {
        "название": "IT и Computer Science",
        "описание": "Чистый IT/CS/ML вне химии: алгоритмы, ML, БД, инженерия ПО.",
        "subdomains": {
            "ml_general": {
                "название": "Машинное обучение (общее)",
                "прототип": (
                    "Машинное обучение: классификация, регрессия, кластеризация, "
                    "supervised и unsupervised обучение, feature engineering, "
                    "cross-validation, метрики качества, scikit-learn, XGBoost, "
                    "machine learning, classification, regression, clustering, "
                    "supervised learning, model evaluation, hyperparameter tuning."
                ),
            },
            "deep_learning": {
                "название": "Глубокое обучение",
                "прототип": (
                    "Глубокое обучение: нейронные сети, CNN, RNN, transformers, "
                    "attention mechanism, backpropagation, PyTorch, TensorFlow, "
                    "dropout, batch normalization, оптимизаторы Adam SGD, "
                    "deep learning, neural networks, transformers, attention, "
                    "convolutional networks, recurrent networks, gradient descent."
                ),
            },
            "nlp": {
                "название": "Обработка естественного языка",
                "прототип": (
                    "NLP: языковые модели, BERT, GPT, токенизация, embedding слов, "
                    "named entity recognition, классификация текстов, машинный перевод, "
                    "RAG, vector search, LangChain, LlamaIndex, "
                    "natural language processing, language models, BERT, GPT, "
                    "word embeddings, tokenization, RAG retrieval augmented generation."
                ),
            },
            "computer_vision": {
                "название": "Компьютерное зрение",
                "прототип": (
                    "Computer vision: image classification, object detection, "
                    "segmentation, ResNet, YOLO, ViT, image generation, GANs, diffusion, "
                    "компьютерное зрение, классификация изображений, детекция объектов, "
                    "сегментация, генерация изображений."
                ),
            },
            "data_engineering": {
                "название": "Data Engineering и Big Data",
                "прототип": (
                    "Data engineering: ETL pipelines, data warehouses, Spark, Hadoop, "
                    "Airflow, Kafka, потоковая обработка, batch processing, parquet, "
                    "data lake, инженерия данных, big data, распределённые вычисления, "
                    "ETL, data pipelines, Apache Spark, streaming, Kafka."
                ),
            },
            "databases": {
                "название": "Базы данных",
                "прототип": (
                    "Базы данных: SQL, PostgreSQL, MySQL, NoSQL, MongoDB, "
                    "vector databases, Qdrant, Weaviate, Milvus, индексы, "
                    "реляционные модели, транзакции, ACID, нормализация, "
                    "databases, SQL, NoSQL, vector database, indexing, transactions."
                ),
            },
            "software_engineering": {
                "название": "Инженерия программного обеспечения",
                "прототип": (
                    "Software engineering: системный дизайн, микросервисы, "
                    "DevOps, CI/CD, Docker, Kubernetes, REST API, GraphQL, "
                    "тестирование, паттерны проектирования, Git, code review, "
                    "software architecture, microservices, REST, GraphQL, Docker, "
                    "Kubernetes, CI/CD, design patterns, testing."
                ),
            },
        },
    },
}


def все_субдомены():
    """[(domain_key, subdomain_key, прототип_текст), ...]"""
    результат = []
    for домен_ключ, домен in ДОМЕНЫ.items():
        for суб_ключ, суб in домен["subdomains"].items():
            результат.append((домен_ключ, суб_ключ, суб["прототип"]))
    return результат


def название_домена(ключ):
    return ДОМЕНЫ.get(ключ, {}).get("название", ключ)


def название_субдомена(домен_ключ, суб_ключ):
    домен = ДОМЕНЫ.get(домен_ключ, {})
    суб = домен.get("subdomains", {}).get(суб_ключ, {})
    return суб.get("название", суб_ключ)


def плоский_список_доменов():
    return [(ключ, домен["название"]) for ключ, домен in ДОМЕНЫ.items()]
