@echo off
rem Публичный запуск через ngrok (стабильный URL).
rem
rem ПЕРЕД ПЕРВЫМ ЗАПУСКОМ:
rem   1. Установить ngrok: https://ngrok.com/download
rem   2. Получить authtoken на https://dashboard.ngrok.com/get-started/your-authtoken
rem   3. Прописать его:  ngrok config add-authtoken <token>
rem   4. Создать domain в admin.ngrok.com → Domains
rem   5. Прописать его в .env как NGROK_DOMAIN=<твой-поддомен>.ngrok-free.dev
rem
rem .env подхватывается launcher'ом автоматически.

cd /d "%~dp0\.."
py -3.12 scripts\запуск.py
pause
