"""Тесты для heartbeat в qr_status.txt.

Проверяет что и записать_heartbeat, и обновить_qr_страницу пишут
ровно 5 строк (url / провайдер / статус / bust / heartbeat_ts).

Контекст: смысл 5-й строки — JS на qr.html по file:// не может
делать кросс-доменные fetch к туннелю (CORS), поэтому единственный
честный способ узнать «watchdog жив?» — это смотреть, что
heartbeat_ts свежий. Если в файле 4 строки — это старый формат и
страница не сможет показать «launcher молчит N сек».
"""
import importlib.util
import os
import sys
import time
import types
from pathlib import Path

# Загружаем модуль scripts/запуск.py напрямую — у него кириллическое имя,
# обычный import не работает.
ROOT = Path(__file__).resolve().parent.parent
СКРИПТ = ROOT / "scripts" / "запуск.py"


def _загрузить_модуль(tmp_path):
    """Загружает запуск.py с подменённым КОРЕНЬ на tmp_path,
    чтобы не топтать настоящие qr.html / qr_status.txt в репо."""
    spec = importlib.util.spec_from_file_location("_zapusk_test", СКРИПТ)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["_zapusk_test"] = mod
    spec.loader.exec_module(mod)
    # Перенаправляем пути на tmp.
    mod.КОРЕНЬ = str(tmp_path)
    mod.ПУТЬ_QR = str(tmp_path / "qr.png")
    mod.ПУТЬ_QR_HTML = str(tmp_path / "qr.html")
    mod.ПУТЬ_QR_СТАТУС = str(tmp_path / "qr_status.txt")
    return mod


def test_записать_heartbeat_5_строк(tmp_path):
    mod = _загрузить_модуль(tmp_path)
    состояние = mod.Состояние()
    состояние.url = "https://example.com"
    состояние.провайдер = "localhost.run"

    mod.записать_heartbeat(состояние, "ok")

    содержимое = (tmp_path / "qr_status.txt").read_text(encoding="utf-8")
    строки = содержимое.rstrip("\n").split("\n")
    assert len(строки) == 5, f"ожидали 5 строк, получили {len(строки)}: {строки!r}"
    assert строки[0] == "https://example.com"
    assert строки[1] == "localhost.run"
    assert строки[2] == "ok"
    # bust и heartbeat_ts — числа.
    int(строки[3])
    ts = int(строки[4])
    # Heartbeat должен быть свежим — в пределах 5 сек.
    assert abs(ts - int(time.time())) < 5


def test_записать_heartbeat_статус_starting_когда_url_пустой(tmp_path):
    mod = _загрузить_модуль(tmp_path)
    состояние = mod.Состояние()
    # url не установлен — это «ещё запускаемся».
    mod.записать_heartbeat(состояние, "ok")
    строки = (tmp_path / "qr_status.txt").read_text(encoding="utf-8") \
        .rstrip("\n").split("\n")
    assert строки[2] == "starting", "при пустом url статус должен быть starting"
    assert len(строки) == 5


def test_записать_heartbeat_статус_down(tmp_path):
    mod = _загрузить_модуль(tmp_path)
    состояние = mod.Состояние()
    состояние.url = "https://example.com"
    состояние.провайдер = "serveo.net"

    mod.записать_heartbeat(состояние, "down")
    строки = (tmp_path / "qr_status.txt").read_text(encoding="utf-8") \
        .rstrip("\n").split("\n")
    assert строки[2] == "down"
    assert len(строки) == 5


def test_обновить_qr_страницу_пишет_5_строк_starting(tmp_path):
    """Главная регрессия: первый вызов в главный() — обновить_qr_страницу("", "", "starting").
    Раньше он мог писать 4 строки (без heartbeat_ts), и JS на qr.html не мог
    отличить «свежий запуск» от «процесс упал и больше не пишет»."""
    mod = _загрузить_модуль(tmp_path)
    mod.обновить_qr_страницу("", "", статус="starting")

    путь = tmp_path / "qr_status.txt"
    assert путь.exists()
    строки = путь.read_text(encoding="utf-8").rstrip("\n").split("\n")
    assert len(строки) == 5, f"ожидали 5 строк, получили {len(строки)}: {строки!r}"
    assert строки[0] == ""
    assert строки[1] == ""
    assert строки[2] == "starting"
    int(строки[3])
    ts = int(строки[4])
    assert abs(ts - int(time.time())) < 5


def test_обновить_qr_страницу_пишет_5_строк_с_url(tmp_path):
    mod = _загрузить_модуль(tmp_path)
    mod.обновить_qr_страницу("https://abc.lhr.life", "localhost.run", статус="ok")

    строки = (tmp_path / "qr_status.txt").read_text(encoding="utf-8") \
        .rstrip("\n").split("\n")
    assert len(строки) == 5
    assert строки[0] == "https://abc.lhr.life"
    assert строки[1] == "localhost.run"
    assert строки[2] == "ok"
    ts = int(строки[4])
    assert abs(ts - int(time.time())) < 5


def test_heartbeat_перезаписывает_файл_свежим_ts(tmp_path):
    """После того как обновить_qr_страницу записал статус, watchdog
    каждые 5 сек пишет heartbeat — timestamp должен расти."""
    mod = _загрузить_модуль(tmp_path)
    состояние = mod.Состояние()
    состояние.url = "https://example.com"
    состояние.провайдер = "localhost.run"

    mod.обновить_qr_страницу("https://example.com", "localhost.run", статус="ok")
    ts1 = int((tmp_path / "qr_status.txt").read_text(encoding="utf-8")
              .rstrip("\n").split("\n")[4])

    time.sleep(1.1)  # чтобы int(time.time()) гарантированно увеличился
    mod.записать_heartbeat(состояние, "ok")
    ts2 = int((tmp_path / "qr_status.txt").read_text(encoding="utf-8")
              .rstrip("\n").split("\n")[4])

    assert ts2 > ts1, f"heartbeat не обновился: {ts1} → {ts2}"



def test_атомарность_записи_qr_status(tmp_path):
    """Регрессия: раньше open("w") + f.write шли последовательно, и внешний
    читатель (JS на qr.html) мог поймать файл в момент когда содержимое
    обнулено или записана только часть. Получалось 4 строки вместо 5.

    Сейчас запись идёт через os.replace из tmp-файла — атомарно.
    Тест: 200 итераций записи в фоновом потоке + параллельные чтения
    из главного. Все чтения должны видеть либо ровно 5 строк, либо
    исходное состояние (отсутствующий файл — игнорируем, мало вероятен)."""
    import threading

    mod = _загрузить_модуль(tmp_path)
    состояние = mod.Состояние()
    состояние.url = "https://example.com"
    состояние.провайдер = "localhost.run"

    # Прогрев: первая запись.
    mod.записать_heartbeat(состояние, "ok")

    стоп = threading.Event()
    нашли_кривое = []

    def писатель():
        i = 0
        while not стоп.is_set() and i < 500:
            mod.записать_heartbeat(состояние, "ok")
            i += 1

    def читатель():
        while not стоп.is_set():
            try:
                содержимое = (tmp_path / "qr_status.txt").read_text(encoding="utf-8")
            except (OSError, FileNotFoundError):
                continue
            строки = содержимое.rstrip("\n").split("\n")
            if len(строки) != 5:
                нашли_кривое.append((len(строки), строки))
                стоп.set()
                return

    t1 = threading.Thread(target=писатель)
    t2 = threading.Thread(target=читатель)
    t1.start()
    t2.start()
    t1.join(timeout=5)
    стоп.set()
    t2.join(timeout=2)

    assert not нашли_кривое, (
        f"читатель поймал файл в неконсистентном состоянии: "
        f"{нашли_кривое[:3]}"
    )
