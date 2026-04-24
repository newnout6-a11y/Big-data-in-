кейсы = {
    "поиск_молекул": {
        "название": "Поиск лекарственных молекул",
        "ключевые_слова": [
            "drug discovery", "molecule", "molecular", "drug design", "ligand",
            "binding", "docking", "pharmacophore", "SMILES", "fingerprint",
            "лекарство", "молекула", "молекулярный", "фармакофор"
        ]
    },
    "токсичность": {
        "название": "Прогноз токсичности вещества",
        "ключевые_слова": [
            "toxicity", "toxic", "LD50", "ADMET", "QSAR", "lethal", "hazard",
            "ecotoxicity", "acute toxicity", "inhibition",
            "токсичность", "токсичный", "летальность", "ингибирование"
        ]
    },
    "оптимизация_реакции": {
        "название": "Оптимизация условий химической реакции",
        "ключевые_слова": [
            "reaction optimization", "reaction conditions", "temperature", "solvent",
            "bayesian optimization", "self-driving", "high-throughput",
            "оптимизация реакции", "условия реакции", "температура", "растворитель"
        ]
    },
    "выход_реакции": {
        "название": "Прогноз выхода реакции",
        "ключевые_слова": [
            "reaction yield", "yield prediction", "yield %", "product yield",
            "выход реакции", "прогноз выхода", "выход продукта"
        ]
    },
    "катализ": {
        "название": "Подбор катализатора",
        "ключевые_слова": [
            "catalyst", "catalysis", "catalytic", "CO2", "methanation",
            "heterogeneous", "turnover frequency", "активность катализатора",
            "катализатор", "катализ", "каталитический"
        ]
    },
    "новые_материалы": {
        "название": "Поиск новых материалов",
        "ключевые_слова": [
            "crystal structure", "materials discovery", "perovskite", "MOF",
            "band gap", "formation energy", "lattice", "alloy",
            "новый материал", "кристаллическая структура", "перовскит"
        ]
    },
    "свойства_материалов": {
        "название": "Прогноз свойств материала",
        "ключевые_слова": [
            "materials property", "property prediction", "mechanical properties",
            "thermal conductivity", "hardness", "elastic modulus", "GNN",
            "свойства материала", "прогноз свойств", "теплопроводность"
        ]
    },
    "анализ_спектров": {
        "название": "Анализ спектров веществ",
        "ключевые_слова": [
            "NMR", "infrared", "IR spectroscopy", "mass spectrometry", "MALDI",
            "spectral", "spectrum", "elucidation", "chemical shift",
            "ЯМР", "спектроскопия", "ИК-спектр", "масс-спектрометрия", "спектр"
        ]
    },
    "контроль_производства": {
        "название": "Контроль качества химического производства",
        "ключевые_слова": [
            "process monitoring", "soft sensor", "process control", "distillation",
            "refinery", "industrial process", "quality control", "sensor",
            "контроль производства", "технологический процесс", "датчик", "ректификация"
        ]
    },
    "предиктивное_обслуживание": {
        "название": "Прогноз поломок оборудования",
        "ключевые_слова": [
            "predictive maintenance", "fault detection", "anomaly detection",
            "equipment failure", "condition monitoring", "vibration",
            "предиктивное обслуживание", "обнаружение аномалий", "поломка оборудования"
        ]
    },
    "энергоэффективность": {
        "название": "Оптимизация расхода энергии",
        "ключевые_слова": [
            "energy optimization", "energy efficiency", "heat exchanger",
            "exergy", "thermodynamic", "CO2 capture", "biohydrogen",
            "энергоэффективность", "оптимизация энергии", "теплообменник"
        ]
    },
    "зелёная_химия": {
        "название": "Выбор экологичного маршрута синтеза",
        "ключевые_слова": [
            "green chemistry", "green synthesis", "sustainable", "solvent selection",
            "atom economy", "E-factor", "eco-friendly", "waste",
            "зелёная химия", "устойчивое развитие", "экологичный синтез"
        ]
    },
    "извлечение_данных": {
        "название": "Извлечение химических данных из статей и патентов",
        "ключевые_слова": [
            "text mining", "NLP", "named entity recognition", "patent mining",
            "chemical extraction", "DECIMER", "ChemScanner", "NER",
            "извлечение данных", "обработка текста", "патентный анализ"
        ]
    },
    "лабораторные_данные": {
        "название": "Создание базы лабораторных экспериментов",
        "ключевые_слова": [
            "electronic lab notebook", "ELN", "FAIR", "open reaction database",
            "ORD", "data management", "reproducibility", "metadata",
            "электронный журнал", "база данных экспериментов", "воспроизводимость"
        ]
    },
    "компетенции": {
        "название": "Связь с направлением Цифровая химическая технология",
        "ключевые_слова": [
            "cheminformatics", "digital chemistry", "education", "machine learning chemistry",
            "AI chemistry", "chemistry education", "workflow",
            "хемоинформатика", "цифровая химия", "образование", "машинное обучение в химии"
        ]
    }
}


def определить_кейс(текст):
    текст_нижний = текст.lower()
    лучший_кейс = "компетенции"
    лучший_счёт = 0
    for ключ, данные in кейсы.items():
        счёт = sum(1 for слово in данные["ключевые_слова"] if слово.lower() in текст_нижний)
        if счёт > лучший_счёт:
            лучший_счёт = счёт
            лучший_кейс = ключ
    return лучший_кейс


def получить_название_кейса(ключ):
    if ключ in кейсы:
        return кейсы[ключ]["название"]
    return "Неизвестный кейс"
