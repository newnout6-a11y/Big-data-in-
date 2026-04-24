import os
import re
import sys
import time
import subprocess
import qrcode

корень = os.path.dirname(os.path.abspath(__file__))
порт = 8501
путь_лога = os.path.join(корень, "_tunnel.log")
путь_qr = os.path.join(корень, "qr.png")


def завершить_старые():
    # Старые туннели
    for имя in ("cloudflared.exe", "ssh.exe"):
        try:
            subprocess.run(["taskkill", "/F", "/IM", имя], capture_output=True)
        except Exception:
            pass

    # Всё что слушает порт 8501 (старый Streamlit)
    try:
        netstat = subprocess.run(
            ["netstat", "-ano", "-p", "tcp"],
            capture_output=True, text=True, encoding="cp866", errors="ignore"
        )
        pids_к_убою = set()
        for строка in netstat.stdout.splitlines():
            if f":{порт}" in строка and "LISTENING" in строка.upper():
                части = строка.split()
                if части and части[-1].isdigit():
                    pids_к_убою.add(части[-1])
        for pid in pids_к_убою:
            subprocess.run(["taskkill", "/F", "/PID", pid], capture_output=True)
    except Exception:
        pass

    # Любые python-процессы, запускающие наш app.py (на случай если висят без порта)
    try:
        subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "Get-CimInstance Win32_Process | "
             "Where-Object { $_.Name -in 'python.exe','pythonw.exe' -and "
             "$_.CommandLine -like '*app.py*' } | "
             "ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"],
            capture_output=True, timeout=10
        )
    except Exception:
        pass


def подготовить_лог():
    """Освобождаем _tunnel.log. Если занят — ретрай, иначе уникальное имя."""
    global путь_лога
    for _ in range(6):
        try:
            if os.path.exists(путь_лога):
                os.remove(путь_лога)
            return
        except OSError:
            time.sleep(1)
    путь_лога = os.path.join(корень, f"_tunnel_{int(time.time())}.log")


def запустить_streamlit():
    питон = sys.executable
    процесс = subprocess.Popen(
        [питон, "-m", "streamlit", "run", os.path.join(корень, "app.py"),
         "--server.headless", "true", "--server.port", str(порт)],
        cwd=корень,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
    )
    return процесс


def дождаться_streamlit(таймаут=60):
    import urllib.request
    старт = time.time()
    while time.time() - старт < таймаут:
        try:
            urllib.request.urlopen(f"http://localhost:{порт}", timeout=1)
            return True
        except Exception:
            time.sleep(1)
    return False


def запустить_туннель():
    подготовить_лог()
    файл = open(путь_лога, "w", encoding="utf-8", errors="ignore")
    аргументы = [
        "ssh",
        "-o", "StrictHostKeyChecking=no",
        "-o", "UserKnownHostsFile=NUL",
        "-o", "ServerAliveInterval=30",
        "-o", "PasswordAuthentication=no",
        "-o", "BatchMode=yes",
        "-T",
        "-R", f"80:localhost:{порт}",
        "nokey@localhost.run"
    ]
    процесс = subprocess.Popen(
        аргументы,
        stdout=файл,
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
    )
    return процесс, файл


def получить_url(таймаут=40):
    старт = time.time()
    шаблон = re.compile(r"https://[a-zA-Z0-9\-]+\.lhr\.life")
    while time.time() - старт < таймаут:
        if os.path.exists(путь_лога):
            try:
                with open(путь_лога, "r", encoding="utf-8", errors="ignore") as f:
                    содержимое = f.read()
                совпадение = шаблон.search(содержимое)
                if совпадение:
                    return совпадение.group(0)
            except Exception:
                pass
        time.sleep(1)
    return None


def сгенерировать_qr(url):
    картинка = qrcode.make(url)
    картинка.save(путь_qr)
    return путь_qr


def открыть_файл(путь):
    if os.name == "nt":
        os.startfile(путь)
    else:
        subprocess.run(["xdg-open", путь])


print("=" * 60)
print("  НАВИГАТОР ЦИФРОВОЙ ХИМИИ · запуск")
print("=" * 60)

print("\n[1/4] останавливаем старые процессы...")
завершить_старые()
time.sleep(2)

print("[2/4] запускаем Streamlit на порту", порт, "...")
streamlit_процесс = запустить_streamlit()
if not дождаться_streamlit():
    print("\nОШИБКА: Streamlit не запустился за 60 секунд")
    sys.exit(1)
print("      Streamlit готов:  http://localhost:" + str(порт))

print("[3/4] создаём туннель через localhost.run (SSH)...")
туннель_процесс, лог_файл = запустить_туннель()
публичный_url = получить_url()
if not публичный_url:
    print("\nОШИБКА: не удалось получить публичный URL за 40 секунд")
    print("Проверь лог:", путь_лога)
    туннель_процесс.terminate()
    streamlit_процесс.terminate()
    sys.exit(1)

print("[4/4] генерируем QR-код...")
сгенерировать_qr(публичный_url)
открыть_файл(путь_qr)

print("\n" + "=" * 60)
print("  ГОТОВО")
print("=" * 60)
print(f"\n  Локально:         http://localhost:{порт}")
print(f"  Публичная ссылка: {публичный_url}")
print(f"  QR-код:           {путь_qr}")
print("\n  Наведи камеру телефона на QR или открой ссылку")
print("  Работает из РФ без VPN")
print("  Нажми Ctrl+C чтобы остановить")
print()

try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("\n\nОстанавливаем...")
    туннель_процесс.terminate()
    streamlit_процесс.terminate()
    try:
        лог_файл.close()
    except Exception:
        pass
    print("Всё остановлено.")
