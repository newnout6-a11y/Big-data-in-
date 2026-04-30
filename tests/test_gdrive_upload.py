"""Тесты для harvester.gdrive_upload (без реальных запросов к Drive API)."""
from __future__ import annotations

import json
import os
import sys
import types
from unittest.mock import MagicMock, patch

import pytest

from harvester import gdrive_upload


# ---------- _получить_креды ----------

def test_креды_не_заданы_возвращает_none(monkeypatch, capsys):
    """Без env-переменных функция возвращает None и печатает hint."""
    for k in (
        "GDRIVE_CREDENTIALS_FILE", "GDRIVE_CREDENTIALS_JSON",
        "GDRIVE_OAUTH_TOKEN_FILE", "GDRIVE_OAUTH_TOKEN_JSON",
    ):
        monkeypatch.delenv(k, raising=False)
    assert gdrive_upload._получить_креды() is None
    out = capsys.readouterr().out
    assert "[gdrive] креды не заданы" in out


def test_креды_service_account_json(monkeypatch):
    """Если задан GDRIVE_CREDENTIALS_JSON — парсится JSON и зовётся
    service_account.Credentials.from_service_account_info."""
    monkeypatch.setenv("GDRIVE_CREDENTIALS_JSON", '{"type":"service_account"}')
    monkeypatch.delenv("GDRIVE_CREDENTIALS_FILE", raising=False)

    fake_module = types.ModuleType("google.oauth2.service_account")
    sentinel = object()
    fake_creds_class = MagicMock()
    fake_creds_class.from_service_account_info.return_value = sentinel
    fake_module.Credentials = fake_creds_class

    with patch.dict(sys.modules, {
        "google.oauth2.service_account": fake_module,
    }):
        результат = gdrive_upload._получить_креды()

    assert результат is sentinel
    fake_creds_class.from_service_account_info.assert_called_once()
    args, kwargs = fake_creds_class.from_service_account_info.call_args
    assert args[0] == {"type": "service_account"}
    assert kwargs["scopes"] == gdrive_upload.SCOPES


def test_креды_oauth_token_file(monkeypatch, tmp_path):
    """OAuth путь: читается JSON и зовётся
    Credentials.from_authorized_user_info."""
    for k in ("GDRIVE_CREDENTIALS_FILE", "GDRIVE_CREDENTIALS_JSON",
              "GDRIVE_OAUTH_TOKEN_JSON"):
        monkeypatch.delenv(k, raising=False)

    token = tmp_path / "token.json"
    token.write_text(json.dumps({
        "refresh_token": "rt",
        "client_id": "ci",
        "client_secret": "cs",
        "token_uri": "https://oauth2.googleapis.com/token",
    }), encoding="utf-8")
    monkeypatch.setenv("GDRIVE_OAUTH_TOKEN_FILE", str(token))

    fake_module = types.ModuleType("google.oauth2.credentials")
    sentinel = object()
    fake_creds_class = MagicMock()
    fake_creds_class.from_authorized_user_info.return_value = sentinel
    fake_module.Credentials = fake_creds_class

    with patch.dict(sys.modules, {
        "google.oauth2.credentials": fake_module,
    }):
        результат = gdrive_upload._получить_креды()

    assert результат is sentinel
    fake_creds_class.from_authorized_user_info.assert_called_once()
    args, kwargs = fake_creds_class.from_authorized_user_info.call_args
    assert args[0]["refresh_token"] == "rt"


# ---------- загрузить ----------

def test_загрузить_без_folder_id_возвращает_0(monkeypatch, capsys):
    """Без GDRIVE_FOLDER_ID функция выходит с 0."""
    monkeypatch.delenv("GDRIVE_FOLDER_ID", raising=False)
    assert gdrive_upload.загрузить() == 0
    assert "GDRIVE_FOLDER_ID не задан" in capsys.readouterr().out


def test_загрузить_без_кредов_возвращает_0(monkeypatch, capsys):
    """С folder_id, но без кредов — функция выходит с 0."""
    monkeypatch.setenv("GDRIVE_FOLDER_ID", "FOLDER")
    for k in (
        "GDRIVE_CREDENTIALS_FILE", "GDRIVE_CREDENTIALS_JSON",
        "GDRIVE_OAUTH_TOKEN_FILE", "GDRIVE_OAUTH_TOKEN_JSON",
    ):
        monkeypatch.delenv(k, raising=False)
    assert gdrive_upload.загрузить() == 0


# ---------- _собрать_локальные_файлы ----------

def test_собрать_файлы_пропускает_несуществующие_папки(tmp_path, monkeypatch):
    """Если all_pdfs/ / harvested_meta/ не существуют — пустой список."""
    monkeypatch.setattr(gdrive_upload, "_БАЗА", str(tmp_path))
    assert gdrive_upload._собрать_локальные_файлы() == []


def test_собрать_файлы_находит_pdf_и_meta(tmp_path, monkeypatch):
    """PDF в all_pdfs/ и JSON в harvested_meta/ → попадают в список."""
    monkeypatch.setattr(gdrive_upload, "_БАЗА", str(tmp_path))
    pdf_dir = tmp_path / "all_pdfs"
    pdf_dir.mkdir()
    (pdf_dir / "test.pdf").write_bytes(b"%PDF-fake")
    meta_dir = tmp_path / "harvested_meta"
    meta_dir.mkdir()
    (meta_dir / "test.json").write_text("{}", encoding="utf-8")

    файлы = gdrive_upload._собрать_локальные_файлы()
    имена_и_папки = {(имя, папка) for _, имя, папка in файлы}
    assert ("test.pdf", "all_pdfs") in имена_и_папки
    assert ("test.json", "harvested_meta") in имена_и_папки


# ---------- _угадать_mime ----------

@pytest.mark.parametrize("имя,ожидаемый_mime", [
    ("foo.pdf", "application/pdf"),
    ("FOO.PDF", "application/pdf"),
    ("a.json", "application/json"),
    ("doc.docx", "application/vnd.openxmlformats-officedocument."
                 "wordprocessingml.document"),
    ("note.txt", "text/plain"),
    ("unknown.bin", "application/octet-stream"),
])
def test_угадать_mime(имя, ожидаемый_mime):
    assert gdrive_upload._угадать_mime(имя) == ожидаемый_mime


# ---------- _получить_или_создать_подпапку ----------

def test_получить_или_создать_подпапку_возвращает_существующую():
    """Если подпапка уже есть — возвращает её id, не создаёт."""
    сервис = MagicMock()
    listing = MagicMock()
    listing.execute.return_value = {"files": [{"id": "EXISTING", "name": "all_pdfs"}]}
    сервис.files().list.return_value = listing

    создать = MagicMock()
    сервис.files().create = создать

    folder_id = gdrive_upload._получить_или_создать_подпапку(
        сервис, "all_pdfs", "ROOT"
    )
    assert folder_id == "EXISTING"
    создать.assert_not_called()


def test_получить_или_создать_подпапку_создаёт_новую():
    """Если подпапки нет — создаёт и возвращает новый id."""
    сервис = MagicMock()
    listing = MagicMock()
    listing.execute.return_value = {"files": []}
    сервис.files().list.return_value = listing

    create_call = MagicMock()
    create_call.execute.return_value = {"id": "NEW_FOLDER"}
    сервис.files().create.return_value = create_call

    folder_id = gdrive_upload._получить_или_создать_подпапку(
        сервис, "state", "ROOT"
    )
    assert folder_id == "NEW_FOLDER"
    сервис.files().create.assert_called()


# ---------- _список_файлов_в_папке ----------

def test_список_файлов_в_папке_объединяет_страницы():
    """Несколько страниц nextPageToken → один общий словарь."""
    сервис = MagicMock()
    page1 = MagicMock()
    page1.execute.return_value = {
        "files": [{"id": "f1", "name": "a.pdf"}, {"id": "f2", "name": "b.pdf"}],
        "nextPageToken": "tok",
    }
    page2 = MagicMock()
    page2.execute.return_value = {
        "files": [{"id": "f3", "name": "c.pdf"}],
    }
    сервис.files().list.side_effect = [page1, page2]

    результат = gdrive_upload._список_файлов_в_папке(сервис, "FOLDER")
    assert результат == {"a.pdf": "f1", "b.pdf": "f2", "c.pdf": "f3"}


# ---------- main ----------

def test_main_dry_run_без_folder_id(monkeypatch):
    """main(--dry-run) без GDRIVE_FOLDER_ID должен вернуть 0 и не падать."""
    monkeypatch.delenv("GDRIVE_FOLDER_ID", raising=False)
    assert gdrive_upload.main(["--dry-run"]) == 0


def test_main_state_only_без_folder_id(monkeypatch):
    """main(--state-only) без env должен вернуть 0 и не падать."""
    monkeypatch.delenv("GDRIVE_FOLDER_ID", raising=False)
    assert gdrive_upload.main(["--state-only"]) == 0
