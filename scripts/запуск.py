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
import time
import urllib.error
import urllib.request

import qrcode

# ─────────────────────────────────────────────────────────────────────────
# Константы
# ─────────────────────────────────────────────────────────────────────────

КОРЕНЬ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ПОРТ = int(os.environ.get("NAV_PORT", "8501"))
ПУТЬ_QR = os.path.join(КОРЕНЬ, "qr.png")
ПУТЬ_ТУННЕЛЬ_ЛОГ = os.path.join(КОРЕНЬ, "_tunnel.log")
ПУТЬ_STREAMLIT_ЛОГ = os.path.join(КОРЕНЬ, "_streamlit.log")

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
    for имя in ("ssh.exe", "cloudflared.exe"):
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
         "--server.address", "127.0.0.1",
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
    """localhost.run, free tier. URL: https://*.lhr.life."""
    ssh = _ssh_бинарь()
    if not ssh:
        return None
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


# Список провайдеров туннеля по убыванию приоритета.
# (имя, функция-стартер, регэксп для URL)
ПРОВАЙДЕРЫ_ТУННЕЛЯ = [
    ("localhost.run", запустить_localhostrun, RE_LHR_URL),
    ("serveo.net",     запустить_serveo,      RE_SERVEO_URL),
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


# Локальная HTML-страница с актуальным QR. Открывается ОДИН раз в браузере,
# а потом автообновляется через meta-refresh — пользователь не должен
# перезапускать просмотрщик при смене URL после watchdog-рестарта.
ПУТЬ_QR_HTML = os.path.join(КОРЕНЬ, "qr.html")
ПУТЬ_QR_СТАТУС = os.path.join(КОРЕНЬ, "qr_status.txt")  # текущий URL в текстовом виде


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
  let TUNNEL_URL = {repr(серверный_url)};
  let LAST_PYTHON_BUST = {bust};
  let CONSECUTIVE_FAILS = 0;
  const SOFT_FAIL_THRESHOLD = 2;
  const STATUS_FILE = "qr_status.txt";
  const QR_FILE = "qr.png";

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

  async function pingTunnel(url) {{
    if (!url) return false;
    try {{
      const ctrl = new AbortController();
      const timer = setTimeout(() => ctrl.abort(), 6000);
      await fetch(url.replace(/\\/$/, '') + '/_stcore/health',
                  {{mode: 'no-cors', signal: ctrl.signal, cache: 'no-store'}});
      clearTimeout(timer);
      return true;
    }} catch (e) {{
      return false;
    }}
  }}

  async function pullPythonStatus() {{
    try {{
      const r = await fetch(STATUS_FILE + '?t=' + Date.now(),
                            {{cache: 'no-store'}});
      if (!r.ok) return null;
      const text = await r.text();
      const lines = text.split(/\\r?\\n/);
      return {{
        url:       (lines[0] || '').trim(),
        provider:  (lines[1] || '').trim(),
        status:    (lines[2] || '').trim(),
        bust:      parseInt(lines[3] || '0', 10),
      }};
    }} catch (e) {{
      return null;
    }}
  }}

  function applyPythonState(s) {{
    if (!s) return;
    if (s.url !== TUNNEL_URL) {{
      TUNNEL_URL = s.url;
      if (s.url) {{
        elUrl.innerHTML = '<a href="' + s.url + '" target="_blank" '
          + 'style="color:#60a5fa;text-decoration:none;word-break:break-all">'
          + s.url + '</a>';
      }} else {{
        elUrl.innerHTML = '<span style="color:#888">URL появится при '
          + 'подключении туннеля</span>';
      }}
    }}
    if (s.bust && s.bust !== LAST_PYTHON_BUST && elQr && elQr.tagName === 'IMG') {{
      elQr.src = QR_FILE + '?t=' + s.bust;
      LAST_PYTHON_BUST = s.bust;
    }}
    if (s.provider && elProvider) {{
      elProvider.innerHTML = 'через <b>' + s.provider + '</b>';
    }}
    if (s.status === 'down') {{
      setStatus('down', '○ восстанавливается…');
      CONSECUTIVE_FAILS = SOFT_FAIL_THRESHOLD;
    }} else if (s.status === 'starting') {{
      setStatus('starting', '◐ запуск…');
    }}
  }}

  async function tick() {{
    const py = await pullPythonStatus();
    applyPythonState(py);

    if (TUNNEL_URL) {{
      const живой = await pingTunnel(TUNNEL_URL);
      if (живой) {{
        CONSECUTIVE_FAILS = 0;
        setStatus('ok', '● онлайн');
      }} else {{
        CONSECUTIVE_FAILS++;
        if (CONSECUTIVE_FAILS >= SOFT_FAIL_THRESHOLD) {{
          setStatus('down', '○ нет соединения, восстанавливаем…');
        }} else {{
          setStatus('starting', '◐ проверяем соединение…');
        }}
      }}
    }} else {{
      setStatus('starting', '◐ запуск…');
    }}
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
    try:
        with open(ПУТЬ_QR_СТАТУС, "w", encoding="utf-8") as f:
            f.write(f"{url or ''}\n{провайдер or ''}\n{статус}\n{bust}\n")
    except OSError:
        pass


def открыть_файл(путь):
    if os.name == "nt":
        try:
            os.startfile(путь)
        except OSError:
            pass
    else:
        subprocess.run(["xdg-open", путь], check=False)


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
        открыть_файл(ПУТЬ_QR_HTML)
        состояние.qr_открыт_впервые = True

    return True


def watchdog(состояние: Состояние, остановлен_callback):
    """Бесконечный цикл проверок. Возвращает 'fail' если что-то умерло,
    'stop' если пользователь нажал Ctrl+C."""
    стабильность_старт = time.time()
    последняя_проверка = 0
    последняя_url_проверка = 0

    while True:
        if остановлен_callback():
            return "stop"
        time.sleep(1)
        сейчас = time.time()

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

            # Если стабильно работаем дольше СТАБИЛЬНЫЙ_АПТАЙМ — сбрасываем
            # backoff: следующий рестарт будет с малой паузы.
            if сейчас - стабильность_старт > СТАБИЛЬНЫЙ_АПТАЙМ:
                if состояние.backoff != RESTART_BACKOFF_СТАРТ:
                    состояние.backoff = RESTART_BACKOFF_СТАРТ

        # Раз в минуту — внешний healthcheck публичного URL.
        # Туннель может быть «формально жив» (процесс не упал), но
        # перестать проксировать — например, при ребуте на стороне lhr.
        if состояние.url and (сейчас - последняя_url_проверка >= 60):
            последняя_url_проверка = сейчас
            if not url_живой(состояние.url):
                печать(f"Внешний URL {состояние.url} не отвечает — рестарт",
                       метка="error")
                return "fail"


def главный():
    print("=" * 64)
    print("  НАВИГАТОР · публичный запуск (с watchdog)")
    print("=" * 64)

    состояние = Состояние()
    остановлен = [False]

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
        ок = стартовый_цикл(состояние)
        if ок:
            print()
            print("─" * 64)
            print(f"  Локально:    http://localhost:{ПОРТ}")
            print(f"  Публично:    {состояние.url}")
            print(f"  Провайдер:   {состояние.провайдер}")
            print(f"  QR-страница: {ПУТЬ_QR_HTML}")
            print(f"  QR-картинка: {ПУТЬ_QR}")
            print(f"  Streamlit:   {ПУТЬ_STREAMLIT_ЛОГ}")
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
