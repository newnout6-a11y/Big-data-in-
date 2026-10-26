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

import pytest
from unittest.mock import Mock

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


def test_python312_предпочитает_проектное_окружение(tmp_path, monkeypatch):
    mod = _загрузить_модуль(tmp_path)
    проверить = Mock(return_value=types.SimpleNamespace(
        returncode=0, stdout=str(tmp_path / "python.exe") + "\n"))
    monkeypatch.setattr(mod.subprocess, "run", проверить)
    monkeypatch.setattr(mod.shutil, "which", Mock(side_effect=AssertionError("uv не нужен")))

    assert mod._найти_python312() == str(tmp_path / "python.exe")
    assert проверить.call_count == 1
    assert ".venv" in проверить.call_args.args[0][0]


def test_python312_находит_uv_если_py_не_видит_его(tmp_path, monkeypatch):
    mod = _загрузить_модуль(tmp_path)
    uv_python = str(tmp_path / "uv python.exe")
    команды = []

    def выполнить(команда, **kwargs):
        команды.append(команда)
        if команда[0] == "uv.exe":
            return types.SimpleNamespace(returncode=0, stdout=uv_python + "\n")
        if команда[0] == uv_python:
            return types.SimpleNamespace(returncode=0, stdout=uv_python + "\n")
        return types.SimpleNamespace(returncode=1, stdout="")

    monkeypatch.setattr(mod.subprocess, "run", выполнить)
    monkeypatch.setattr(mod.shutil, "which", lambda _: "uv.exe")

    assert mod._найти_python312() == uv_python
    uv_поиск = next(к for к in команды if к[0] == "uv.exe")
    assert "--offline" in uv_поиск and "--no-python-downloads" in uv_поиск


def test_главный_сохраняет_аргументы_и_код_выхода_при_смене_python(tmp_path, monkeypatch):
    mod = _загрузить_модуль(tmp_path)
    python312 = str(tmp_path / "python312.exe")
    monkeypatch.setattr(mod, "_найти_python312", lambda: python312)
    monkeypatch.setattr(mod.sys, "argv", [str(СКРИПТ), "--lan", "дополнительный аргумент"])
    вызвать = Mock(return_value=23)
    monkeypatch.setattr(mod.subprocess, "call", вызвать)
    запуск_qr = Mock()
    monkeypatch.setattr(mod, "запустить_qr_сервер", запуск_qr)

    with pytest.raises(SystemExit) as ошибка:
        mod.главный()

    assert ошибка.value.code == 23
    assert вызвать.call_args.args[0] == [python312, str(СКРИПТ), "--lan", "дополнительный аргумент"]
    запуск_qr.assert_not_called()


def test_нет_python312_не_запускает_дочерние_процессы(tmp_path, monkeypatch, capsys):
    mod = _загрузить_модуль(tmp_path)
    monkeypatch.setattr(mod, "_найти_python312", lambda: None)
    запустить = Mock()
    monkeypatch.setattr(mod.subprocess, "Popen", запустить)

    with pytest.raises(SystemExit) as ошибка:
        mod.главный()

    assert ошибка.value.code == 1
    assert "Python 3.12" in capsys.readouterr().err
    запустить.assert_not_called()


@pytest.mark.parametrize("цикл", ["стартовый_цикл", "стартовый_цикл_lan"])
def test_занятый_порт_не_убивает_чужие_процессы(tmp_path, monkeypatch, цикл):
    mod = _загрузить_модуль(tmp_path)
    monkeypatch.setattr(mod, "порт_свободен", lambda _: False)
    системная_команда = Mock(side_effect=AssertionError("Нельзя завершать чужие процессы"))
    создать_процесс = Mock(side_effect=AssertionError("Порт занят"))
    monkeypatch.setattr(mod.subprocess, "run", системная_команда)
    monkeypatch.setattr(mod.subprocess, "Popen", создать_процесс)
    состояние = mod.Состояние()
    свой_процесс = Mock()
    состояние.streamlit = свой_процесс

    assert getattr(mod, цикл)(состояние) is False

    свой_процесс.wait.assert_called_once()
    assert состояние.streamlit is None
    системная_команда.assert_not_called()
    создать_процесс.assert_not_called()


@pytest.mark.parametrize("проверка", ["streamlit_живой", "url_живой"])
@pytest.mark.parametrize("статус,тело,ожидается", [
    (200, b"ok", True),
    (200, b"<html>tunnel login required</html>", False),
    (404, b"not found", False),
    (401, b"authorization required", False),
    (503, b"unavailable", False),
])
def test_health_требует_реальный_ответ_streamlit(
        tmp_path, monkeypatch, проверка, статус, тело, ожидается):
    from unittest.mock import MagicMock

    mod = _загрузить_модуль(tmp_path)
    ответ = MagicMock()
    ответ.__enter__.return_value = ответ
    ответ.status = статус
    ответ.read.return_value = тело[:16]
    monkeypatch.setattr(mod.urllib.request, "urlopen", lambda *a, **kw: ответ)

    аргументы = ["https://example.com"] if проверка == "url_живой" else []
    assert getattr(mod, проверка)(*аргументы) is ожидается
    ответ.__exit__.assert_called_once()


@pytest.mark.parametrize("код", [401, 404, 503])
def test_ошибка_http_не_считается_живым_туннелем(tmp_path, monkeypatch, код):
    mod = _загрузить_модуль(tmp_path)
    ошибка = mod.urllib.error.HTTPError("https://example.com", код, "error", None, None)
    monkeypatch.setattr(mod.urllib.request, "urlopen", Mock(side_effect=ошибка))

    assert mod.url_живой("https://example.com") is False


@pytest.mark.skipif(os.name != "nt", reason="Windows cmd launcher")
@pytest.mark.parametrize("имя,флаги", [
    ("запуск.cmd", []),
    ("запуск_lan.cmd", ["--lan"]),
    ("запуск_pub.cmd", []),
])
def test_cmd_передаёт_флаги_и_код_выхода(tmp_path, имя, флаги):
    import shutil
    import subprocess

    папка = tmp_path / "scripts"
    папка.mkdir()
    for скрипт in ("запуск.cmd", "запуск_lan.cmd", "запуск_pub.cmd"):
        shutil.copyfile(ROOT / "scripts" / скрипт, папка / скрипт)
    бин = tmp_path / "bin"
    бин.mkdir()
    (бин / "py.cmd").write_text(
        '@echo off\n> "%LAUNCH_ARGS%" echo %*\nexit /b 23\n', encoding="ascii")
    аргументы = tmp_path / "args.txt"
    окружение = {**os.environ, "PATH": str(бин) + os.pathsep + os.environ["PATH"],
                 "LAUNCH_ARGS": str(аргументы)}

    результат = subprocess.run(
        ["cmd", "/d", "/c", f'call scripts\\{имя} --test-value'],
        cwd=tmp_path, env=окружение, stdin=subprocess.DEVNULL,
        capture_output=True, timeout=15,
    )

    assert результат.returncode == 23
    assert аргументы.read_text(encoding="utf-8").strip().split() == [
        "scripts\\запуск.py", *флаги, "--test-value"]
