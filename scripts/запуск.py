"""Стабильный публичный запуск (РФ-friendly, без VPN, бесплатно).

ПРОБЛЕМА. Раньше использовался один localhost.run-туннель без watchdog —
через 1-2 часа SSH-соединение протухало (idle drop у провайдера или у lhr),
и сайт ложился до ручного рестарта.

ЧТО ДЕЛАЕМ ТЕПЕРЬ:

  1. Streamlit на 8501 (прижатый к 127.0.0.1).
  2. Туннель: пробуем по приоритету localhost.run → Serveo (оба через SSH-22,
     в РФ работают без VPN). Cloudflare Tunnel из РФ не идёт — TLS handshake
     режется на порту 7844 у большинства провайдеров, поэтому его не пытаемся.
  3. Watchdog раз в 15 сек:
       — `/_stcore/health` Streamlit (ловит зависания event loop'а, OOM);
       — `process.poll()` туннеля (если SSH упал — пересоздаём);
       — попытка GET к публичному URL (если URL отдаёт >=500 — туннель битый).
  4. При любом фейле: kill старых процессов → backoff → повторный старт.
     Backoff: 5 → 10 → 20 → 40 → 80 → 160 → 300с (cap), сбрасывается на 5
     после первой успешной минуты работы.
  5. SSH-туннель идёт с агрессивным keep-alive (ServerAliveInterval=20,
     ExitOnForwardFailure=yes), чтобы быстрее ловить разрыв и быстро
     возвращаться в watchdog для рестарта.
  6. URL может смениться при рестарте — печатаем новый и пересохраняем QR.
"""
import os
import re
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer

# ─────────────────────────────────────────────────────────────────────────
# Совместимость интерпретатора
# ─────────────────────────────────────────────────────────────────────────
# Зависимости (streamlit/protobuf/qdrant-client/...) проверены и установлены
# для Python 3.12. На 3.14 свежеустановленный Streamlit падает на старте с
# `ImportError: cannot import name 'builder' from 'google.protobuf.internal'`
# из-за устаревшего protobuf'а (нужен >=3.20.3, см. requirements.txt).
# Не молчим, а сразу даём понятную ошибку с инструкцией — иначе watchdog
# будет вечно крутить рестарт-цикл, а пользователь не поймёт почему сайт
# не открывается.
if sys.version_info[:2] != (3, 12):
    подсказка = (
        f"\n[ОШИБКА] Запущено на Python {sys.version_info.major}."
        f"{sys.version_info.minor}, а проект собран под 3.12.\n"
        "  Запусти через:  py -3.12 scripts/запуск.py\n"
        "  Или используй:  scripts/запуск.cmd  (двойной клик)\n"
    )
    print(подсказка, file=sys.stderr)
    sys.exit(1)

import qrcode

# ─────────────────────────────────────────────────────────────────────────
# Константы
# ─────────────────────────────────────────────────────────────────────────

КОРЕНЬ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ПОРТ = int(os.environ.get("NAV_PORT", "8501"))
ПУТЬ_QR = os.path.join(КОРЕНЬ, "qr.png")
ПУТЬ_ТУННЕЛЬ_ЛОГ = os.path.join(КОРЕНЬ, "_tunnel.log")
ПУТЬ_STREAMLIT_ЛОГ = os.path.join(КОРЕНЬ, "_streamlit.log")


def _подгрузить_env():
    """Читает .env из корня репо в os.environ, не перезаписывая уже заданные.

    Streamlit и harvester умеют это сами через python-dotenv, а launcher
    запускается до них — нам нужны NGROK_DOMAIN/LHR_USER здесь же.
    Реализован минимально, без зависимости от python-dotenv: один проход
    `KEY=VALUE`, кавычки снимаются, комментарии и пустые строки игнорятся.
    """
    путь = os.path.join(КОРЕНЬ, ".env")
    if not os.path.isfile(путь):
        return
    try:
        with open(путь, "r", encoding="utf-8") as f:
            for строка in f:
                строка = строка.strip()
                if not строка or строка.startswith("#"):
                    continue
                if "=" not in строка:
                    continue
                ключ, значение = строка.split("=", 1)
                ключ = ключ.strip()
                значение = значение.strip().strip('"').strip("'")
                # Не перезаписываем — env-переменные имеют приоритет над .env.
                if ключ and ключ not in os.environ:
                    os.environ[ключ] = значение
    except OSError:
        pass


_подгрузить_env()

# Режим запуска. По умолчанию — публичный (через SSH-туннель).
# Если передан флаг --лан/--lan/--local: запускаемся ТОЛЬКО на LAN
# (без туннеля). Это спасение когда у провайдера зарезан localhost.run
# или сам провайдер сейчас деградировал. Сайт открывается с любого
# устройства в той же Wi-Fi/Ethernet — этого достаточно, например, чтобы
# показать защиту с телефона проверяющего.
РЕЖИМ_LAN = any(arg in {"--лан", "--lan", "--local", "--только-локально"}
                for arg in sys.argv[1:])
# Streamlit слушает 127.0.0.1 в публичном режиме (туннель пробрасывает
# на него внутри loopback'а) и 0.0.0.0 в LAN-режиме (доступ из локалки).
STREAMLIT_BIND = "0.0.0.0" if РЕЖИМ_LAN else "127.0.0.1"

HEALTH_TIMEOUT = 8
HEALTH_INTERVAL = 15  # как часто watchdog проверяет состояние
TUNNEL_URL_ОЖИДАНИЕ = 60  # сколько ждём публичный URL после старта SSH
RESTART_BACKOFF_СТАРТ = 5
RESTART_BACKOFF_МАКС = 300
СТАБИЛЬНЫЙ_АПТАЙМ = 60  # после 60 сек без падений считаем что заработало
МАКС_ПОПЫТОК_ОДНОГО_ПРОВАЙДЕРА = 2  # если 2 раза подряд не дал URL, идём дальше


# Регулярки для поиска публичных URL в логе SSH
RE_LHR_URL = re.compile(r"https://[a-zA-Z0-9\-]+\.lhr\.life")
RE_SERVEO_URL = re.compile(r"https://[a-zA-Z0-9\-]+\.serveo\.net")
# ngrok печатает url= в JSON-логе и в человеческом виде (Forwarding ...)
RE_NGROK_URL = re.compile(r"https://[a-zA-Z0-9\-]+\.ngrok-free\.(?:dev|app)")


# ─────────────────────────────────────────────────────────────────────────
# Утилиты
# ─────────────────────────────────────────────────────────────────────────

def печать(сообщение, *, метка="info"):
    стмп = time.strftime("%H:%M:%S")
    префикс = {"info": "·", "warn": "!", "error": "✗", "ok": "✓"}.get(метка, "·")
    print(f"[{стмп}] {префикс} {сообщение}", flush=True)


def открыть_лог(путь):
    return open(путь, "w", encoding="utf-8", errors="ignore", buffering=1)


def порт_свободен(порт):
    try:
        с = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        с.settimeout(0.5)
        с.bind(("127.0.0.1", порт))
        с.close()
        return True
    except OSError:
        return False


def streamlit_живой(таймаут=HEALTH_TIMEOUT):
    """Проверяет /_stcore/health endpoint. True если Streamlit отвечает.

    Раньше проверялся просто localhost:port — но он отвечает 200 даже на
    зависший Streamlit (TCP accept'ит, но дальше не идёт). Endpoint health
    идёт через event loop, ловит зависания.
    """
    try:
        urllib.request.urlopen(
            f"http://127.0.0.1:{ПОРТ}/_stcore/health", timeout=таймаут,
        )
        return True
    except (urllib.error.URLError, ConnectionError, socket.timeout, OSError):
        return False


def url_живой(url, таймаут=8):
    """HEAD/GET к публичному URL — проверка что туннель реально проксирует.

    Streamlit на /_stcore/health отвечает 'ok' — оптимально для проверки
    через туннель. Если 5xx или таймаут — туннель кривой, рестартуем.
    """
    try:
        запрос = urllib.request.Request(
            url.rstrip("/") + "/_stcore/health",
            headers={
                "User-Agent": "navigator-watchdog/1",
                # localhost.run требует этот header чтобы пропустить запрос
                # без редиректа на промо-страницу:
                "Accept": "*/*",
                # ngrok без этого заголовка отдаёт interstitial-страницу
                # с предупреждением «You are about to visit...» — не страшно
                # с нашей стороны (всё равно будет 200), но шлём для чистоты.
                "ngrok-skip-browser-warning": "1",
            },
        )
        с_ответом = urllib.request.urlopen(запрос, timeout=таймаут)
        return с_ответом.status < 500
    except urllib.error.HTTPError as e:
        return e.code < 500
    except Exception:
        return False


def завершить_старые():
    """Аккуратно убивает прежние процессы перед стартом."""
    for имя in ("ssh.exe", "cloudflared.exe", "ngrok.exe"):
        try:
            subprocess.run(["taskkill", "/F", "/IM", имя],
                           capture_output=True, timeout=5)
        except Exception:
            pass

    # Что слушает наш порт — убить
    try:
        netstat = subprocess.run(
            ["netstat", "-ano", "-p", "tcp"],
            capture_output=True, text=True, encoding="cp866", errors="ignore",
            timeout=10,
        )
        pids = set()
        for строка in netstat.stdout.splitlines():
            if f":{ПОРТ}" in строка and "LISTENING" in строка.upper():
                части = строка.split()
                if части and части[-1].isdigit():
                    pids.add(части[-1])
        for pid in pids:
            subprocess.run(["taskkill", "/F", "/PID", pid],
                           capture_output=True, timeout=5)
    except Exception:
        pass

    # Прежние Streamlit-процессы по командной строке
    try:
        subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "Get-CimInstance Win32_Process | "
             "Where-Object { $_.Name -in 'python.exe','pythonw.exe' -and "
             "$_.CommandLine -like '*ui\\app.py*' } | "
             "ForEach-Object { Stop-Process -Id $_.ProcessId -Force "
             "-ErrorAction SilentlyContinue }"],
            capture_output=True, timeout=10,
        )
    except Exception:
        pass


# ─────────────────────────────────────────────────────────────────────────
# Streamlit
# ─────────────────────────────────────────────────────────────────────────

def запустить_streamlit():
    лог = открыть_лог(ПУТЬ_STREAMLIT_ЛОГ)
    окружение = os.environ.copy()
    окружение["PYTHONIOENCODING"] = "utf-8"
    окружение["PYTHONUNBUFFERED"] = "1"
    окружение.setdefault("STREAMLIT_BROWSER_GATHER_USAGE_STATS", "false")
    окружение.setdefault("STREAMLIT_SERVER_MAX_UPLOAD_SIZE", "100")

    процесс = subprocess.Popen(
        [sys.executable, "-m", "streamlit", "run",
         os.path.join(КОРЕНЬ, "ui", "app.py"),
         "--server.headless", "true",
         "--server.port", str(ПОРТ),
         "--server.address", STREAMLIT_BIND,
         "--server.enableXsrfProtection", "false",
         "--browser.gatherUsageStats", "false"],
        cwd=КОРЕНЬ,
        stdout=лог, stderr=subprocess.STDOUT,
        env=окружение,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
    )
    процесс._лог_файл = лог
    return процесс


def дождаться_streamlit(таймаут=120):
    """Ждём пока /_stcore/health начнёт отвечать. e5-base загружается ~30с,
    плюс Qdrant. На медленном диске иногда дольше — даём 120 сек."""
    старт = time.time()
    while time.time() - старт < таймаут:
        if streamlit_живой(таймаут=2):
            return True
        time.sleep(1)
    return False


# ─────────────────────────────────────────────────────────────────────────
# Туннели — список бесплатных, работающих в РФ без VPN
# ─────────────────────────────────────────────────────────────────────────

def _ssh_бинарь():
    """Путь к ssh.exe. На Windows 10/11 ssh поставляется в комплекте."""
    путь = shutil.which("ssh")
    if путь:
        return путь
    # Стандартное место на Windows
    кандидаты = [
        r"C:\Windows\System32\OpenSSH\ssh.exe",
        r"C:\Program Files\OpenSSH\ssh.exe",
    ]
    for к in кандидаты:
        if os.path.isfile(к):
            return к
    return None


def _ssh_базовые_опции():
    """Общие опции для всех SSH-туннелей. ServerAliveInterval=20 шлёт keep-
    alive каждые 20 сек чтобы провайдер не дропнул idle TCP. ExitOnForward
    Failure=yes — если форвард не получился (например провайдер уже занят),
    немедленно выходим, watchdog поймает и пересоздаст."""
    return [
        "-o", "StrictHostKeyChecking=no",
        "-o", "UserKnownHostsFile=NUL" if os.name == "nt" else "/dev/null",
        "-o", "ServerAliveInterval=20",
        "-o", "ServerAliveCountMax=3",
        "-o", "ConnectTimeout=15",
        "-o", "PasswordAuthentication=no",
        "-o", "BatchMode=yes",
        "-o", "ExitOnForwardFailure=yes",
        "-T",
    ]


def запустить_localhostrun(лог):
    """localhost.run, http://*.lhr.life.

    Два режима:
      1. Если задана env-переменная LHR_USER — подключаемся через
         <LHR_USER>@localhost.run с SSH-ключом из ~/.ssh/id_ed25519.
         Это даёт стабильный URL (reserved domain), привязанный к
         аккаунту в admin.localhost.run, и более надёжное проксирование
         (платные/авторизованные туннели не режутся как анонимные).
      2. Без LHR_USER — подключаемся как `nokey@localhost.run`, домен
         случайный, поведение как раньше.
    """
    ssh = _ssh_бинарь()
    if not ssh:
        return None

    lhr_user = os.environ.get("LHR_USER", "").strip()
    if lhr_user:
        # Авторизованный туннель: ключ ed25519 из стандартного места.
        # localhost.run по этому ключу узнаёт аккаунт и применяет
        # привязанные reserved domain'ы.
        ключ = os.path.join(os.path.expanduser("~"), ".ssh", "id_ed25519")
        ключ_args = ["-i", ключ] if os.path.exists(ключ) else []
        args = [ssh, *_ssh_базовые_опции(), *ключ_args,
                "-R", f"80:localhost:{ПОРТ}",
                f"{lhr_user}@localhost.run"]
    else:
        args = [ssh, *_ssh_базовые_опции(),
                "-R", f"80:localhost:{ПОРТ}",
                "nokey@localhost.run"]

    return subprocess.Popen(
        args, stdout=лог, stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
    )


def запустить_serveo(лог):
    """Serveo, free tier. URL: https://*.serveo.net.

    Раньше Serveo иногда требовал ввод password — в BatchMode=yes такие
    попытки сразу падают и watchdog уходит на следующий провайдер."""
    ssh = _ssh_бинарь()
    if not ssh:
        return None
    args = [ssh, *_ssh_базовые_опции(),
            "-R", f"80:localhost:{ПОРТ}",
            "serveo.net"]
    return subprocess.Popen(
        args, stdout=лог, stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
    )


def _ngrok_бинарь():
    """Ищет ngrok.exe в стандартных местах Windows-установки.
    Возвращает None если не нашёл."""
    кандидаты = [
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "ngrok", "ngrok.exe"),
        os.path.join(os.environ.get("ProgramFiles", ""), "ngrok", "ngrok.exe"),
        shutil.which("ngrok") or "",
    ]
    for к in кандидаты:
        if к and os.path.isfile(к):
            return к
    return None


def запустить_ngrok(лог):
    """ngrok-туннель к стабильному домену.

    Требует:
      1. Установленный ngrok.exe (см. _ngrok_бинарь).
      2. Authtoken прописан через `ngrok config add-authtoken <token>`.
      3. NGROK_DOMAIN в окружении — поддомен из admin.ngrok.com
         (например, "moodiness-corral-armed.ngrok-free.dev").
    Без NGROK_DOMAIN или без бинарника возвращаем None — провайдер пропускается.
    """
    ngrok = _ngrok_бинарь()
    domain = os.environ.get("NGROK_DOMAIN", "").strip()
    if not ngrok or not domain:
        return None
    args = [
        ngrok, "http",
        f"--domain={domain}",
        f"127.0.0.1:{ПОРТ}",  # явно IPv4 — ngrok иначе резолвит localhost в [::1] и ловит ERR_NGROK_8012
        "--log=stdout",
        "--log-format=logfmt",
    ]
    return subprocess.Popen(
        args, stdout=лог, stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
    )


# Список провайдеров туннеля по убыванию приоритета.
# (имя, функция-стартер, регэксп для URL)
# ngrok идёт первым: если NGROK_DOMAIN задан, это самый стабильный путь
# (стабильный URL, не режется в РФ). Без NGROK_DOMAIN ngrok-провайдер
# сразу возвращает None и переходим к localhost.run/serveo.
ПРОВАЙДЕРЫ_ТУННЕЛЯ = [
    ("ngrok",         запустить_ngrok,        RE_NGROK_URL),
    ("localhost.run", запустить_localhostrun, RE_LHR_URL),
    ("serveo.net",    запустить_serveo,       RE_SERVEO_URL),
]


def запустить_туннель_провайдер(имя, стартер, регэксп):
    """Запускает один провайдер и ждёт URL. Возвращает (Popen, url) или
    (None, None) если провайдер не отдал URL за TUNNEL_URL_ОЖИДАНИЕ."""
    лог = открыть_лог(ПУТЬ_ТУННЕЛЬ_ЛОГ)
    процесс = стартер(лог)
    if процесс is None:
        try:
            лог.close()
        except Exception:
            pass
        return None, None
    процесс._лог_файл = лог

    старт = time.time()
    while time.time() - старт < TUNNEL_URL_ОЖИДАНИЕ:
        # Если ssh упал раньше времени — выходим
        if процесс.poll() is not None:
            печать(f"{имя}: SSH-процесс упал (rc={процесс.returncode})",
                   метка="warn")
            return процесс, None

        try:
            with open(ПУТЬ_ТУННЕЛЬ_ЛОГ, "r", encoding="utf-8",
                      errors="ignore") as f:
                содержимое = f.read()
            m = регэксп.search(содержимое)
            if m:
                return процесс, m.group(0)
        except Exception:
            pass
        time.sleep(1)
    return процесс, None


def запустить_туннель():
    """Перебирает провайдеров. Возвращает (процесс, url, имя) первого, кто
    отдал URL. Если никто — (None, None, None)."""
    for имя, стартер, регэксп in ПРОВАЙДЕРЫ_ТУННЕЛЯ:
        печать(f"Пробую туннель: {имя} …")
        процесс, url = запустить_туннель_провайдер(имя, стартер, регэксп)
        if url:
            печать(f"Туннель {имя} поднялся: {url}", метка="ok")
            return процесс, url, имя
        # Не получилось — убиваем процесс и пробуем следующий
        if процесс is not None:
            try:
                процесс.terminate()
                try:
                    процесс.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    процесс.kill()
            except Exception:
                pass
            try:
                if hasattr(процесс, "_лог_файл"):
                    процесс._лог_файл.close()
            except Exception:
                pass
        печать(f"{имя} не отдал URL за {TUNNEL_URL_ОЖИДАНИЕ}с",
               метка="warn")
    return None, None, None


# ─────────────────────────────────────────────────────────────────────────
# QR
# ─────────────────────────────────────────────────────────────────────────

def сгенерировать_qr(url):
    qrcode.make(url).save(ПУТЬ_QR)
    return ПУТЬ_QR


def определить_lan_ip():
    """Возвращает IPv4 локальной сети, через который машина видна другим
    устройствам в той же подсети. Без сетевых обращений — просто открывает
    UDP-сокет к 8.8.8.8 (никаких пакетов наружу не уходит, getsockname()
    возвращает локальный адрес интерфейса по умолчанию).

    Если сети нет — возвращает 127.0.0.1 как fallback.
    """
    try:
        с = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        с.connect(("8.8.8.8", 80))
        ip = с.getsockname()[0]
        с.close()
        return ip
    except OSError:
        return "127.0.0.1"


# Локальная HTML-страница с актуальным QR. Открывается ОДИН раз в браузере,
# а потом автообновляется через meta-refresh — пользователь не должен
# перезапускать просмотрщик при смене URL после watchdog-рестарта.
ПУТЬ_QR_HTML = os.path.join(КОРЕНЬ, "qr.html")
ПУТЬ_QR_СТАТУС = os.path.join(КОРЕНЬ, "qr_status.txt")  # текущий URL в текстовом виде


def записать_heartbeat(состояние, url_статус: str = "ok"):
    """Heartbeat для qr.html. Пишется watchdog'ом каждые 5 сек.

    Содержит:
      строка 1 — публичный URL;
      строка 2 — провайдер;
      строка 3 — статус ('ok' / 'starting' / 'down');
      строка 4 — bust (timestamp генерации QR.png — для cache-bust);
      строка 5 — heartbeat_ts (unix epoch сейчас).

    JS на странице qr.html читает файл каждые 5 сек. Если heartbeat_ts
    старше 30 сек — рисует «watchdog не отвечает». Если url_статус='down' —
    рисует красный «нет соединения». Если 'ok' — зелёный «онлайн».

    Без браузерного fetch на туннель: file:// странички не могут фечнуть
    https-домен из-за CORS, поэтому проверка живости — через файл.
    """
    bust = int(time.time())
    статус_итог = "ok" if url_статус == "ok" and (состояние.url or "") else \
                  "down" if url_статус == "down" else "starting"
    # Атомарная запись через os.replace: пишем в .tmp, потом переименовываем.
    # Без этого JS на qr.html (или внешний наблюдатель) может прочитать файл
    # в момент когда open("w") уже обнулил его, но f.write ещё не дошёл до
    # 5-й строки. Получалось 4 строки → JS думал что heartbeat'а нет и
    # рисовал «launcher молчит», хотя watchdog был жив.
    payload = (
        f"{состояние.url or ''}\n"
        f"{состояние.провайдер or ''}\n"
        f"{статус_итог}\n"
        f"{bust}\n"
        f"{int(time.time())}\n"  # heartbeat
    )
    _атомарно_записать_статус(payload)


def _атомарно_записать_статус(payload: str):
    """Пишет qr_status.txt атомарно: tmp-файл + os.replace.

    На Windows os.replace это атомарная операция переименования
    в пределах того же тома. Гарантия: внешний читатель (JS, smoke-test)
    либо видит старое содержимое целиком, либо новое целиком — никогда
    «половинку».
    """
    tmp = ПУТЬ_QR_СТАТУС + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(payload)
        os.replace(tmp, ПУТЬ_QR_СТАТУС)
    except OSError:
        # Если что-то пошло не так — подчистим временный файл.
        try:
            if os.path.exists(tmp):
                os.remove(tmp)
        except OSError:
            pass


def обновить_qr_страницу(url, провайдер, статус="ok"):
    """Перегенерирует qr.png и пишет qr.html с актуальным URL и QR.

    HTML внутри держит JavaScript-цикл: каждые 5 сек делает no-cors fetch
    к публичному URL (HEAD/GET) — нам важно только что network-уровень
    отдал ответ. Если 2 проверки подряд провалились, статус сразу
    переключается на красный «○ нет соединения, восстанавливаем…».

    Это ловит ситуацию когда туннель упал, а python-watchdog ещё не успел
    среагировать (HEALTH_INTERVAL=15 сек). Раньше плашка «● онлайн»
    оставалась показывать ложный статус несколько секунд.

    Параллельно страница каждые 5 сек читает qr_status.txt — если python
    обновил state (новый URL после рестарта или статус 'down'), страница
    подтягивает изменения без перезагрузки.

    QR.png пересохраняется при смене URL с cache-bust query `?t=<timestamp>`.
    """
    if url:
        сгенерировать_qr(url)
    bust = int(time.time())
    qr_блок = (
        f'<img id="qr-img" src="qr.png?t={bust}" alt="QR" '
        'style="width:340px;height:340px;background:#fff;padding:18px;'
        'border-radius:14px;box-shadow:0 8px 32px rgba(0,0,0,.25)" />'
        if url else
        '<div id="qr-img" style="width:340px;height:340px;border:2px dashed #555;'
        'border-radius:14px;display:flex;align-items:center;justify-content:center;'
        'color:#888;font-family:system-ui,sans-serif">QR пока не готов</div>'
    )
    url_html = (
        f'<a href="{url}" target="_blank" style="color:#60a5fa;'
        f'text-decoration:none;word-break:break-all">{url}</a>'
        if url else
        '<span style="color:#888">URL появится при подключении туннеля</span>'
    )
    провайдер_html = (
        f'через <b>{провайдер}</b>' if провайдер else 'провайдер: …'
    )

    стартовый_статус = статус
    серверный_url = url or ""

    html_страница = f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8">
<title>Навигатор · публичный доступ</title>
<style>
  body {{
    margin: 0; padding: 0;
    min-height: 100vh;
    background: #0a0a0a;
    color: #fafafa;
    font-family: system-ui, -apple-system, sans-serif;
    display: flex; align-items: center; justify-content: center;
  }}
  .card {{
    text-align: center;
    padding: 48px 56px;
    background: #111;
    border-radius: 16px;
    border: 1px solid #2a2a2a;
    max-width: 460px;
  }}
  .status {{
    font-size: 0.85rem;
    letter-spacing: 0.2em;
    text-transform: uppercase;
    margin-bottom: 12px;
    font-weight: 600;
    transition: color 0.3s ease;
  }}
  .status.ok      {{ color: #22c55e; }}
  .status.starting{{ color: #eab308; }}
  .status.down    {{ color: #ef4444; }}
  h1 {{
    font-size: 1.5rem;
    margin: 0 0 4px 0;
    letter-spacing: -0.02em;
  }}
  .sub {{
    color: #a3a3a3;
    margin-bottom: 28px;
    font-size: 0.92rem;
  }}
  .url {{
    margin-top: 28px;
    font-size: 0.95rem;
    font-family: ui-monospace, "SF Mono", Consolas, monospace;
    line-height: 1.55;
  }}
  .hint {{
    margin-top: 18px;
    color: #525252;
    font-size: 0.78rem;
  }}
  /* Когда живой статус "down" — затемняем QR, чтобы пользователь видел что
     сейчас сканировать бесполезно. */
  body.is-down #qr-img {{ opacity: 0.35; filter: grayscale(0.5); }}
</style>
</head>
<body class="is-{стартовый_статус}">
  <div class="card">
    <div id="status" class="status {стартовый_статус}">…</div>
    <h1>Навигатор цифровой химии</h1>
    <div class="sub" id="provider">{провайдер_html}</div>
    {qr_блок}
    <div class="url" id="url-block">{url_html}</div>
    <div class="hint" id="hint">
      Статус обновляется автоматически каждые 5 сек.
    </div>
  </div>

<script>
(function() {{
  // Все данные приходят от python-watchdog'а через qr_status.txt.
  // Прямой fetch к туннелю не делаем — браузер с file:// его блокирует
  // из-за CORS, никаких реальных проверок не получится. Вместо этого
  // python-watchdog раз в 5 сек сам пишет в файл свежий heartbeat и
  // url_статус (ok/down). Если heartbeat_ts > 30 сек — JS показывает
  // «watchdog не отвечает» (значит сам python-процесс рухнул).

  let TUNNEL_URL = {repr(серверный_url)};
  let LAST_PYTHON_BUST = {bust};
  // Если страница открыта по file:// (двойной клик из проводника),
  // браузер блокирует fetch к локальным файлам из-за CORS. Перенаправляем
  // все запросы на локальный сервер, который launcher поднимает на :{ПОРТ_QR_СЕРВЕРА}.
  // Если страница уже открыта через http://localhost — оставляем
  // относительные пути (нагрузка на сервер чуть меньше, кэширование чище).
  const BASE = (window.location.protocol === 'file:')
    ? 'http://localhost:{ПОРТ_QR_СЕРВЕРА}/'
    : '';
  const STATUS_FILE = BASE + "qr_status.txt";
  const QR_FILE = BASE + "qr.png";
  const HEARTBEAT_СТАЛО_СТАРО_СЕК = 30;

  const elStatus   = document.getElementById('status');
  const elProvider = document.getElementById('provider');
  const elUrl      = document.getElementById('url-block');
  const elQr       = document.getElementById('qr-img');
  const elBody     = document.body;

  function setStatus(name, text) {{
    elStatus.className = 'status ' + name;
    elStatus.textContent = text;
    elBody.className = 'is-' + name;
  }}

  async function pullPythonStatus() {{
    // STATUS_FILE уже либо относительный (если страница открыта по
    // http://localhost), либо абсолютный к локальному серверу (если file://).
    try {{
      const r = await fetch(STATUS_FILE + '?t=' + Date.now(),
                            {{cache: 'no-store'}});
      if (!r.ok) return null;
      const text = await r.text();
      const lines = text.split(/\\r?\\n/);
      return {{
        url:           (lines[0] || '').trim(),
        provider:      (lines[1] || '').trim(),
        status:        (lines[2] || '').trim(),
        bust:          parseInt(lines[3] || '0', 10),
        heartbeat_ts:  parseInt(lines[4] || '0', 10),
      }};
    }} catch (e) {{
      return null;
    }}
  }}

  async function tick() {{
    const py = await pullPythonStatus();
    if (!py) {{
      setStatus('down', '○ нет связи с launcher');
      return;
    }}

    // 1. Обновляем URL (если сменился) и QR (если bust сменился)
    if (py.url !== TUNNEL_URL) {{
      TUNNEL_URL = py.url;
      if (py.url) {{
        elUrl.innerHTML = '<a href="' + py.url + '" target="_blank" '
          + 'style="color:#60a5fa;text-decoration:none;word-break:break-all">'
          + py.url + '</a>';
      }} else {{
        elUrl.innerHTML = '<span style="color:#888">URL появится при '
          + 'подключении туннеля</span>';
      }}
    }}
    if (py.bust && py.bust !== LAST_PYTHON_BUST && elQr && elQr.tagName === 'IMG') {{
      elQr.src = QR_FILE + '?t=' + py.bust;
      LAST_PYTHON_BUST = py.bust;
    }}
    if (py.provider && elProvider) {{
      elProvider.innerHTML = 'через <b>' + py.provider + '</b>';
    }}

    // 2. Heartbeat: если python давно не обновлял файл — что-то не так
    const сейчас = Math.floor(Date.now() / 1000);
    if (py.heartbeat_ts && (сейчас - py.heartbeat_ts) > HEARTBEAT_СТАЛО_СТАРО_СЕК) {{
      const прошло = сейчас - py.heartbeat_ts;
      setStatus('down', '○ launcher молчит ' + прошло + ' сек');
      return;
    }}

    // 3. Решающий статус — то что сказал watchdog
    if (py.status === 'ok' && py.url) {{
      setStatus('ok', '● онлайн');
    }} else if (py.status === 'down') {{
      setStatus('down', '○ туннель упал, восстанавливаем…');
    }} else {{
      setStatus('starting', '◐ запуск…');
    }}
  }}

  // Если страница открыта по file://, начальный QR.png в HTML тоже
  // живёт по относительному file://-пути — он у нас сейчас грузится
  // через src в обычном <img>, при file:// браузер картинку показывает
  // (это HTML, а не fetch — не блокируется), но при первом обновлении
  // через JS мы перепишем src на локальный сервер для надёжности.
  if (BASE && elQr && elQr.tagName === 'IMG') {{
    elQr.src = QR_FILE + '?t=' + LAST_PYTHON_BUST;
  }}

  tick();
  setInterval(tick, 5000);
}})();
</script>
</body>
</html>
"""
    try:
        with open(ПУТЬ_QR_HTML, "w", encoding="utf-8") as f:
            f.write(html_страница)
    except OSError:
        pass
    # 5 строк: url, провайдер, статус, bust (для qr.png), heartbeat_ts.
    # Атомарно через _атомарно_записать_статус — иначе внешний читатель
    # ловил файл в момент open("w") и видел нулевую длину или 4 строки.
    now_ts = int(time.time())
    _атомарно_записать_статус(
        f"{url or ''}\n"
        f"{провайдер or ''}\n"
        f"{статус}\n"
        f"{bust}\n"
        f"{now_ts}\n"
    )


def открыть_файл(путь):
    """Открывает локальный файл или URL в дефолтном приложении.

    Для http-URL используем webbrowser — os.startfile с https-аргументом
    срабатывает не на всех Windows-инсталляциях."""
    if путь.startswith(("http://", "https://")):
        try:
            import webbrowser
            webbrowser.open(путь)
        except Exception:
            pass
        return
    if os.name == "nt":
        try:
            os.startfile(путь)
        except OSError:
            pass
    else:
        subprocess.run(["xdg-open", путь], check=False)


# ─────────────────────────────────────────────────────────────────────────
# Локальный HTTP-сервер для qr.html
# ─────────────────────────────────────────────────────────────────────────
# JS на странице qr.html делает fetch('qr_status.txt') каждые 5 сек.
# Если страницу открыли по file://, Chromium и Firefox блокируют этот
# fetch из-за CORS-политики на локальных файлах — JS видит ошибку и
# рисует «нет связи с launcher», хотя watchdog честно пишет файл.
# Решение: поднимаем мини-HTTP на 127.0.0.1:8502, отдающий qr.html и
# qr_status.txt с одного origin — fetch разрешён, индикатор работает.

ПОРТ_QR_СЕРВЕРА = int(os.environ.get("NAV_QR_PORT", "8502"))


class _QRHandler(BaseHTTPRequestHandler):
    """Раздаёт qr.html, qr.png и qr_status.txt с no-cache.

    Игнорирует всё остальное. Без листинга директории — мы не файл-сервер.
    """
    _ALLOWED = {
        "/": ("qr.html", "text/html; charset=utf-8"),
        "/qr.html": ("qr.html", "text/html; charset=utf-8"),
        "/qr.png": ("qr.png", "image/png"),
        "/qr_status.txt": ("qr_status.txt", "text/plain; charset=utf-8"),
    }

    def do_GET(self):  # noqa: N802 — имя метода фиксировано базовым классом
        # Срезаем query string (?t=12345 — cache-bust от JS) перед поиском
        # в whitelist'е. Без этого fetch с no-store ловит 404.
        путь = self.path.split("?", 1)[0]
        путь_имя = self._ALLOWED.get(путь)
        if путь_имя is None:
            self.send_error(404, "Not found")
            return
        имя, mime = путь_имя
        полный = os.path.join(КОРЕНЬ, имя)
        try:
            with open(полный, "rb") as f:
                содержимое = f.read()
        except OSError:
            self.send_error(404, "Not ready")
            return
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(содержимое)))
        # Без этого браузер будет кэшировать qr_status.txt и JS не увидит
        # обновлений heartbeat'а — тогда индикатор «онлайн» застрянет.
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.end_headers()
        self.wfile.write(содержимое)

    def log_message(self, формат, *args):  # noqa: N802
        # Глушим стандартный access-log — он засоряет консоль launcher'а.
        return


_qr_сервер = None


def запустить_qr_сервер():
    """Поднимает локальный HTTP на 127.0.0.1:ПОРТ_QR_СЕРВЕРА в фоне.

    Делается один раз за жизнь launcher'а. Идемпотентно — повторный
    вызов ничего не делает. Закрытие сервера не нужно: daemon-поток
    умрёт вместе с процессом.
    """
    global _qr_сервер
    if _qr_сервер is not None:
        return
    try:
        _qr_сервер = HTTPServer(("127.0.0.1", ПОРТ_QR_СЕРВЕРА), _QRHandler)
    except OSError:
        # Порт занят — отдаём None, qr.html откроем по file:// (с дисклеймером
        # «связь с launcher» работать не будет, но QR покажется).
        _qr_сервер = None
        return
    поток = threading.Thread(
        target=_qr_сервер.serve_forever,
        name="qr-http",
        daemon=True,
    )
    поток.start()


def url_qr_страницы():
    """Возвращает URL для открытия в браузере. Если локальный сервер
    поднялся — http://localhost, если нет — file:// как fallback."""
    if _qr_сервер is not None:
        return f"http://localhost:{ПОРТ_QR_СЕРВЕРА}/qr.html"
    return ПУТЬ_QR_HTML


# ─────────────────────────────────────────────────────────────────────────
# Watchdog: главный цикл с auto-restart
# ─────────────────────────────────────────────────────────────────────────

class Состояние:
    def __init__(self):
        self.streamlit = None
        self.туннель = None
        self.url = None
        self.провайдер = None
        self.backoff = RESTART_BACKOFF_СТАРТ
        self.qr_открыт_впервые = False

    def закрыть(self):
        for проц in (self.туннель, self.streamlit):
            if проц is None:
                continue
            try:
                if os.name == "nt":
                    try:
                        проц.send_signal(signal.CTRL_BREAK_EVENT)
                    except Exception:
                        проц.terminate()
                else:
                    проц.terminate()
                try:
                    проц.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    проц.kill()
            except Exception:
                try:
                    проц.kill()
                except Exception:
                    pass
            try:
                if hasattr(проц, "_лог_файл"):
                    проц._лог_файл.close()
            except Exception:
                pass
        self.streamlit = None
        self.туннель = None


def стартовый_цикл(состояние: Состояние) -> bool:
    завершить_старые()
    time.sleep(2)

    if not порт_свободен(ПОРТ):
        time.sleep(3)

    печать(f"Запускаю Streamlit (порт {ПОРТ}, ждём health …)")
    состояние.streamlit = запустить_streamlit()
    if not дождаться_streamlit():
        печать("Streamlit не ответил health за 120с", метка="error")
        return False
    печать(f"Streamlit живой: http://localhost:{ПОРТ}", метка="ok")

    proc, url, имя = запустить_туннель()
    if not url:
        печать("Ни один туннель не сработал", метка="error")
        return False
    состояние.туннель = proc
    состояние.url = url
    состояние.провайдер = имя

    обновить_qr_страницу(url, имя, статус="ok")
    if not состояние.qr_открыт_впервые:
        # Открываем именно qr.html (не qr.png) — у HTML есть meta-refresh
        # каждые 5 сек, поэтому пользователь не должен переоткрывать после
        # watchdog-рестарта со сменой URL. Старый qr.png тоже обновляется
        # на диске, но просмотрщики Windows за ним не следят.
        открыть_файл(url_qr_страницы())
        состояние.qr_открыт_впервые = True

    return True


def стартовый_цикл_lan(состояние: Состояние) -> bool:
    """Стартовый цикл без публичного туннеля — Streamlit на 0.0.0.0,
    URL — http://<lan-ip>:<port>. Подходит когда туннель в РФ режется
    провайдером и публичную ссылку не получить.

    QR-страница и watchdog работают как обычно, только проверка
    «внешнего URL» идёт по LAN-адресу (он точно отвечает пока сетевая
    карта жива), а не по https://*.lhr.life."""
    завершить_старые()
    time.sleep(2)

    if not порт_свободен(ПОРТ):
        time.sleep(3)

    печать(f"Запускаю Streamlit на 0.0.0.0:{ПОРТ} (LAN-режим, без туннеля)")
    состояние.streamlit = запустить_streamlit()
    if not дождаться_streamlit():
        печать("Streamlit не ответил health за 120с", метка="error")
        return False

    lan_ip = определить_lan_ip()
    url = f"http://{lan_ip}:{ПОРТ}"
    состояние.url = url
    состояние.провайдер = "lan"
    состояние.туннель = None  # туннеля нет — watchdog это поймёт
    печать(f"Streamlit живой: http://localhost:{ПОРТ}  (LAN: {url})",
           метка="ok")

    обновить_qr_страницу(url, "lan", статус="ok")
    if not состояние.qr_открыт_впервые:
        открыть_файл(url_qr_страницы())
        состояние.qr_открыт_впервые = True

    return True


def watchdog(состояние: Состояние, остановлен_callback):
    """Бесконечный цикл проверок. Возвращает 'fail' если что-то умерло,
    'stop' если пользователь нажал Ctrl+C.

    Дополнительно каждые 5 сек обновляет qr_status.txt — это heartbeat
    для открытой qr.html-страницы. Если страница видит что timestamp в
    файле > 30 сек назад, она показывает «watchdog не отвечает» (значит
    процесс python упал и watchdog некому делать).
    """
    стабильность_старт = time.time()
    последняя_проверка = 0
    последняя_url_проверка = 0
    последний_heartbeat = 0
    последний_url_статус = "ok"  # "ok" | "down"

    while True:
        if остановлен_callback():
            return "stop"
        time.sleep(1)
        сейчас = time.time()

        # Heartbeat для qr.html — пишется каждые 5 сек чтобы JS видел что
        # watchdog жив. Браузер по file:// не может фечнуть https-туннель,
        # поэтому единственный честный сигнал «онлайн» — это свежий
        # heartbeat в файле + last_url_check_ok=True.
        if сейчас - последний_heartbeat >= 5:
            последний_heartbeat = сейчас
            записать_heartbeat(состояние, последний_url_статус)

        # Раз в HEALTH_INTERVAL — локальный health
        if сейчас - последняя_проверка >= HEALTH_INTERVAL:
            последняя_проверка = сейчас

            проц_st = состояние.streamlit
            if проц_st is not None and проц_st.poll() is not None:
                печать(f"Streamlit умер (rc={проц_st.returncode})",
                       метка="error")
                return "fail"
            if not streamlit_живой():
                печать("Streamlit health fail (event loop завис?)",
                       метка="error")
                return "fail"

            проц_тн = состояние.туннель
            if проц_тн is not None and проц_тн.poll() is not None:
                печать(f"Туннель {состояние.провайдер} умер "
                       f"(rc={проц_тн.returncode})", метка="error")
                return "fail"

            if сейчас - стабильность_старт > СТАБИЛЬНЫЙ_АПТАЙМ:
                if состояние.backoff != RESTART_BACKOFF_СТАРТ:
                    состояние.backoff = RESTART_BACKOFF_СТАРТ

        # Раз в 30 сек — внешний healthcheck публичного URL (раньше было 60,
        # сократил чтобы быстрее ловить «формально жив, но не проксирует»).
        if состояние.url and (сейчас - последняя_url_проверка >= 30):
            последняя_url_проверка = сейчас
            если_жив = url_живой(состояние.url)
            последний_url_статус = "ok" if если_жив else "down"
            if not если_жив:
                печать(f"Внешний URL {состояние.url} не отвечает — рестарт",
                       метка="error")
                return "fail"


def главный():
    print("=" * 64)
    print("  НАВИГАТОР · публичный запуск (с watchdog)")
    print("=" * 64)

    состояние = Состояние()
    остановлен = [False]

    # Поднимаем локальный HTTP-сервер для qr.html. Без него страница
    # открывается по file:// и JS-fetch к qr_status.txt блокируется
    # CORS'ом в Chromium/Firefox — на странице горит «нет связи с
    # launcher» хотя watchdog честно пишет heartbeat в файл.
    запустить_qr_сервер()

    # Заранее создаём HTML-заглушку, чтобы пользователь мог открыть страницу
    # и видеть статус «запуск…» пока поднимается Streamlit.
    обновить_qr_страницу("", "", статус="starting")

    def обработчик_сигнала(signum, frame):
        if not остановлен[0]:
            остановлен[0] = True
            печать(f"Получен сигнал {signum}, останавливаюсь…")

    signal.signal(signal.SIGINT, обработчик_сигнала)
    try:
        signal.signal(signal.SIGTERM, обработчик_сигнала)
    except (AttributeError, ValueError):
        pass  # Windows нюансы

    while not остановлен[0]:
        ок = стартовый_цикл_lan(состояние) if РЕЖИМ_LAN else стартовый_цикл(состояние)
        if ок:
            print()
            print("─" * 64)
            print(f"  Локально:    http://localhost:{ПОРТ}")
            if РЕЖИМ_LAN:
                print(f"  По LAN:      {состояние.url}")
                print(f"  Провайдер:   локальная сеть (без туннеля)")
            else:
                print(f"  Публично:    {состояние.url}")
                print(f"  Провайдер:   {состояние.провайдер}")
            print(f"  QR-страница: {ПУТЬ_QR_HTML}")
            print(f"  QR-картинка: {ПУТЬ_QR}")
            print(f"  Streamlit:   {ПУТЬ_STREAMLIT_ЛОГ}")
            if not РЕЖИМ_LAN:
                print(f"  Туннель:     {ПУТЬ_ТУННЕЛЬ_ЛОГ}")
            print("─" * 64)
            print(f"  Watchdog активен (health каждые {HEALTH_INTERVAL}с,")
            print(f"  внешний URL каждые 60с). Ctrl+C — стоп.\n")
            try:
                итог = watchdog(состояние, lambda: остановлен[0])
            except KeyboardInterrupt:
                остановлен[0] = True
                итог = "stop"
            if итог == "stop":
                break
            # Иначе fail — закрываемся и идём в backoff
        состояние.закрыть()
        # Обновляем HTML-страницу: статус «восстанавливается». Пользователь,
        # держащий вкладку открытой, увидит изменение через 5 сек (meta-refresh).
        обновить_qr_страницу(состояние.url, состояние.провайдер, статус="down")
        пауза = состояние.backoff
        состояние.backoff = min(состояние.backoff * 2, RESTART_BACKOFF_МАКС)
        печать(f"Пауза {пауза}с перед рестартом…")
        for _ in range(пауза):
            if остановлен[0]:
                break
            time.sleep(1)

    состояние.закрыть()
    print("\nВсё остановлено.")


if __name__ == "__main__":
    главный()
