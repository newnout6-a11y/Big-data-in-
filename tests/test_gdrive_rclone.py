"""Тесты для harvester.gdrive_rclone (rclone-обёртка). Без реального rclone."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from harvester import gdrive_rclone


# ---------- _путь_к_rclone / доступен ----------

def test_путь_к_rclone_из_env(monkeypatch, tmp_path):
    rclone_путь = tmp_path / "fake_rclone"
    rclone_путь.write_text("")
    monkeypatch.setenv("RCLONE_BIN", str(rclone_путь))
    assert gdrive_rclone._путь_к_rclone() == str(rclone_путь)


def test_путь_к_rclone_env_не_существует(monkeypatch, tmp_path):
    monkeypatch.setenv("RCLONE_BIN", str(tmp_path / "nope"))
    assert gdrive_rclone._путь_к_rclone() is None


def test_путь_к_rclone_из_PATH(monkeypatch):
    monkeypatch.delenv("RCLONE_BIN", raising=False)
    with patch("harvester.gdrive_rclone.shutil.which", return_value="/usr/bin/rclone"):
        assert gdrive_rclone._путь_к_rclone() == "/usr/bin/rclone"


def test_доступен_false_без_rclone(monkeypatch):
    monkeypatch.delenv("RCLONE_BIN", raising=False)
    with patch("harvester.gdrive_rclone.shutil.which", return_value=None):
        assert gdrive_rclone.доступен() is False


def test_доступен_true_когда_rclone_есть(monkeypatch):
    monkeypatch.delenv("RCLONE_BIN", raising=False)
    with patch("harvester.gdrive_rclone.shutil.which", return_value="/usr/bin/rclone"):
        assert gdrive_rclone.доступен() is True


# ---------- _аргументы_конфига ----------

def test_аргументы_конфига_пусто_без_env(monkeypatch):
    monkeypatch.delenv("RCLONE_CONFIG", raising=False)
    assert gdrive_rclone._аргументы_конфига() == []


def test_аргументы_конфига_с_env(monkeypatch):
    monkeypatch.setenv("RCLONE_CONFIG", "/tmp/rc.conf")
    assert gdrive_rclone._аргументы_конфига() == ["--config", "/tmp/rc.conf"]


# ---------- _получить_remote_и_base ----------

def test_remote_и_base_дефолты(monkeypatch):
    monkeypatch.delenv("GDRIVE_REMOTE", raising=False)
    monkeypatch.delenv("GDRIVE_BASE", raising=False)
    assert gdrive_rclone._получить_remote_и_base() == ("gdrive", "big-data")


def test_remote_и_base_кастом(monkeypatch):
    monkeypatch.setenv("GDRIVE_REMOTE", "myremote")
    monkeypatch.setenv("GDRIVE_BASE", "/проект-А/")  # ведущие/хвостовые слэши режутся
    assert gdrive_rclone._получить_remote_и_base() == ("myremote", "проект-А")


# ---------- залить (push) ----------

def test_залить_без_rclone_возвращает_0(monkeypatch, capsys):
    """Без rclone в PATH/env — функция тихо выходит, печатая инструкцию."""
    monkeypatch.delenv("RCLONE_BIN", raising=False)
    with patch("harvester.gdrive_rclone.shutil.which", return_value=None):
        assert gdrive_rclone.залить() == 0
    assert "rclone не найден" in capsys.readouterr().out


def test_залить_state_only_формирует_copyto(monkeypatch, tmp_path):
    """state-only: вызов одной copyto-команды на state.json."""
    monkeypatch.setattr(gdrive_rclone, "_БАЗА", str(tmp_path))
    state_path = tmp_path / "harvester" / "state.json"
    state_path.parent.mkdir(parents=True)
    state_path.write_text("{}")
    monkeypatch.delenv("RCLONE_CONFIG", raising=False)
    monkeypatch.setenv("GDRIVE_REMOTE", "gdrive")
    monkeypatch.setenv("GDRIVE_BASE", "big-data")

    fake_run = MagicMock()
    fake_run.return_value = MagicMock(returncode=0)
    with patch("harvester.gdrive_rclone._путь_к_rclone", return_value="/r"):
        with patch("harvester.gdrive_rclone.subprocess.run", fake_run):
            assert gdrive_rclone.залить(только_state=True) == 1

    assert fake_run.call_count == 1
    команда = fake_run.call_args[0][0]
    assert команда[0] == "/r"
    assert "copyto" in команда
    assert str(state_path) in команда
    assert "gdrive:big-data/state/state.json" in команда


def test_залить_state_only_без_файла(monkeypatch, tmp_path, capsys):
    """state-only, но локального state.json нет — пропускаем."""
    monkeypatch.setattr(gdrive_rclone, "_БАЗА", str(tmp_path))
    fake_run = MagicMock()
    with patch("harvester.gdrive_rclone._путь_к_rclone", return_value="/r"):
        with patch("harvester.gdrive_rclone.subprocess.run", fake_run):
            assert gdrive_rclone.залить(только_state=True) == 0
    assert fake_run.call_count == 0
    assert "пропускаю state-step" in capsys.readouterr().out


def test_залить_полный_проход(monkeypatch, tmp_path):
    """Полный sync: state.json + pdf/docx/txt/meta/images — каждое отдельной командой."""
    monkeypatch.setattr(gdrive_rclone, "_БАЗА", str(tmp_path))
    monkeypatch.delenv("RCLONE_CONFIG", raising=False)
    monkeypatch.setenv("GDRIVE_REMOTE", "myremote")
    monkeypatch.setenv("GDRIVE_BASE", "корень")

    # Готовим раскладку: state.json + по одному файлу каждого типа в all_pdfs/
    # + один файл в harvested_meta/.
    (tmp_path / "harvester").mkdir()
    (tmp_path / "harvester" / "state.json").write_text("{}")
    (tmp_path / "all_pdfs").mkdir()
    (tmp_path / "all_pdfs" / "a.pdf").write_bytes(b"%PDF")
    (tmp_path / "all_pdfs" / "b.docx").write_bytes(b"PK")
    (tmp_path / "all_pdfs" / "c.txt").write_text("hi")
    (tmp_path / "harvested_meta").mkdir()
    (tmp_path / "harvested_meta" / "x.json").write_text("{}")
    (tmp_path / "extracted_images").mkdir()
    (tmp_path / "extracted_images" / "doc").mkdir()
    (tmp_path / "extracted_images" / "doc" / "page_1_img_1.png").write_bytes(b"png")

    fake_run = MagicMock(return_value=MagicMock(returncode=0))
    with patch("harvester.gdrive_rclone._путь_к_rclone", return_value="/r"):
        with patch("harvester.gdrive_rclone.subprocess.run", fake_run):
            успешных = gdrive_rclone.залить()

    # state + 5 маршрутов = 6 успешных вызовов
    assert успешных == 6
    assert fake_run.call_count == 6

    команды = [tuple(call.args[0]) for call in fake_run.call_args_list]
    # state.json — первая команда (copyto)
    assert "copyto" in команды[0]
    assert "myremote:корень/state/state.json" in команды[0]
    # PDF: copy с --include "*.pdf"
    assert any("copy" in к and "--include" in к and "*.pdf" in к and
               "myremote:корень/pdf/" in к for к in команды)
    # DOCX
    assert any("--include" in к and "*.docx" in к and
               "myremote:корень/docx/" in к for к in команды)
    # TXT
    assert any("--include" in к and "*.txt" in к and
               "myremote:корень/txt/" in к for к in команды)
    # meta — без --include
    мета = next(к for к in команды if "myremote:корень/meta/" in к)
    assert "--include" not in мета
    # images — без --include, сохраняет вложенные папки extracted_images/<sha>/
    картинки = next(к for к in команды if "myremote:корень/images/" in к)
    assert "--include" not in картинки
    assert str(tmp_path / "extracted_images") in картинки


def test_залить_пропускает_пустые_папки(monkeypatch, tmp_path):
    """Если all_pdfs/ пустая, harvested_meta/ нет — только state-операция."""
    monkeypatch.setattr(gdrive_rclone, "_БАЗА", str(tmp_path))
    (tmp_path / "harvester").mkdir()
    (tmp_path / "harvester" / "state.json").write_text("{}")
    (tmp_path / "all_pdfs").mkdir()  # есть, но пустая
    # harvested_meta не создаём

    fake_run = MagicMock(return_value=MagicMock(returncode=0))
    with patch("harvester.gdrive_rclone._путь_к_rclone", return_value="/r"):
        with patch("harvester.gdrive_rclone.subprocess.run", fake_run):
            успешных = gdrive_rclone.залить()

    assert успешных == 1
    assert fake_run.call_count == 1


def test_залить_dry_run_не_зовёт_subprocess(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(gdrive_rclone, "_БАЗА", str(tmp_path))
    (tmp_path / "harvester").mkdir()
    (tmp_path / "harvester" / "state.json").write_text("{}")

    fake_run = MagicMock()
    with patch("harvester.gdrive_rclone._путь_к_rclone", return_value="/r"):
        with patch("harvester.gdrive_rclone.subprocess.run", fake_run):
            gdrive_rclone.залить(dry_run=True, только_state=True)

    fake_run.assert_not_called()
    assert "DRY $" in capsys.readouterr().out


def test_залить_FileNotFoundError(monkeypatch, tmp_path, capsys):
    """Если в момент запуска rclone-бинарь исчез — _выполнить вернёт 127."""
    monkeypatch.setattr(gdrive_rclone, "_БАЗА", str(tmp_path))
    (tmp_path / "harvester").mkdir()
    (tmp_path / "harvester" / "state.json").write_text("{}")

    with patch("harvester.gdrive_rclone._путь_к_rclone", return_value="/r"):
        with patch("harvester.gdrive_rclone.subprocess.run",
                   side_effect=FileNotFoundError):
            gdrive_rclone.залить(только_state=True)
    out = capsys.readouterr().out
    assert "rclone не найден" in out


# ---------- подтянуть_state ----------

def test_pull_state_успех(monkeypatch, tmp_path):
    monkeypatch.setattr(gdrive_rclone, "_БАЗА", str(tmp_path))
    monkeypatch.setenv("GDRIVE_REMOTE", "gdrive")
    monkeypatch.setenv("GDRIVE_BASE", "big-data")
    monkeypatch.delenv("RCLONE_CONFIG", raising=False)

    fake_result = MagicMock(returncode=0, stderr="", stdout="")
    fake_run = MagicMock(return_value=fake_result)
    with patch("harvester.gdrive_rclone._путь_к_rclone", return_value="/r"):
        with patch("harvester.gdrive_rclone.subprocess.run", fake_run):
            assert gdrive_rclone.подтянуть_state() == 0

    команда = fake_run.call_args[0][0]
    assert команда[0] == "/r"
    assert "copyto" in команда
    assert "gdrive:big-data/state/state.json" in команда
    assert str(Path(tmp_path) / "harvester" / "state.json") in команда


def test_pull_state_когда_файла_нет_в_drive(monkeypatch, tmp_path, capsys):
    """rclone выдал 'not found' → возвращаем 0 (первый запуск, не падаем)."""
    monkeypatch.setattr(gdrive_rclone, "_БАЗА", str(tmp_path))
    fake_result = MagicMock(returncode=3,
                            stderr="ERROR: object not found",
                            stdout="")
    with patch("harvester.gdrive_rclone._путь_к_rclone", return_value="/r"):
        with patch("harvester.gdrive_rclone.subprocess.run", return_value=fake_result):
            assert gdrive_rclone.подтянуть_state() == 0
    assert "стартуем с нуля" in capsys.readouterr().out


def test_pull_state_dry_run_не_зовёт_subprocess(monkeypatch, tmp_path):
    monkeypatch.setattr(gdrive_rclone, "_БАЗА", str(tmp_path))
    fake_run = MagicMock()
    with patch("harvester.gdrive_rclone._путь_к_rclone", return_value="/r"):
        with patch("harvester.gdrive_rclone.subprocess.run", fake_run):
            gdrive_rclone.подтянуть_state(dry_run=True)
    fake_run.assert_not_called()


def test_pull_state_без_rclone(monkeypatch, capsys):
    monkeypatch.delenv("RCLONE_BIN", raising=False)
    with patch("harvester.gdrive_rclone.shutil.which", return_value=None):
        assert gdrive_rclone.подтянуть_state() == 0
    assert "пропускаю pull-state" in capsys.readouterr().out


# ---------- main / CLI ----------

def test_main_push_state_only(monkeypatch):
    monkeypatch.delenv("RCLONE_BIN", raising=False)
    with patch("harvester.gdrive_rclone.shutil.which", return_value=None):
        # Без rclone — просто отрабатывает без ошибки.
        assert gdrive_rclone.main(["push", "--state-only"]) == 0


def test_main_pull_state_dry_run(monkeypatch):
    monkeypatch.delenv("RCLONE_BIN", raising=False)
    with patch("harvester.gdrive_rclone.shutil.which", return_value=None):
        assert gdrive_rclone.main(["pull-state", "--dry-run"]) == 0


def test_main_неизвестная_команда(capsys):
    with pytest.raises(SystemExit):
        gdrive_rclone.main(["foo"])
