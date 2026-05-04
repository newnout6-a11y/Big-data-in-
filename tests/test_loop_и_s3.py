"""Тесты для harvester.loop и harvester.s3_upload."""
from __future__ import annotations

from unittest.mock import MagicMock, patch


from harvester import loop, s3_upload


# ---------- loop.py ----------

def test_loop_валидирует_границы(capsys):
    """work_min_low > work_min_high → код 2."""
    код = loop.main(["--work-min-low", "100", "--work-min-high", "50"])
    assert код == 2
    assert "work-min-low" in capsys.readouterr().out


def test_loop_останавливается_после_max_iterations(monkeypatch):
    """max_iterations=2 → выход после 2 итераций."""
    итераций = []

    def моковый_запуск(args, work_min):
        итераций.append(work_min)
        return 0  # успех → пойдём на сон

    def моковый_сон(минут):
        pass  # мгновенный сон в тестах

    monkeypatch.setattr(loop, "_запустить_итерацию", моковый_запуск)
    monkeypatch.setattr(loop, "_сон_минут", моковый_сон)

    код = loop.main([
        "--max-iterations", "2",
        "--work-min-low", "10", "--work-min-high", "20",
        "--sleep-min-low", "0", "--sleep-min-high", "1",
    ])
    assert код == 0
    assert len(итераций) == 2
    # Каждый work_min должен быть в диапазоне
    for wm in итераций:
        assert 10 <= wm <= 20


def test_loop_sleep_после_ошибки(monkeypatch, capsys):
    """Если итерация упала с returncode != 0 — пауза SLEEP_ON_ERROR_MIN, затем повтор."""
    счётчик = {"n": 0}

    def моковый_запуск(args, work_min):
        счётчик["n"] += 1
        if счётчик["n"] == 1:
            return 1  # первая упала
        return 0  # вторая ок

    вызовы_сна: list[float] = []
    def моковый_сон(минут):
        вызовы_сна.append(минут)

    monkeypatch.setattr(loop, "_запустить_итерацию", моковый_запуск)
    monkeypatch.setattr(loop, "_сон_минут", моковый_сон)

    код = loop.main([
        "--max-iterations", "2",
        "--work-min-low", "10", "--work-min-high", "10",
        "--sleep-min-low", "0", "--sleep-min-high", "0",
    ])
    assert код == 0
    assert счётчик["n"] == 2
    # Первый сон должен быть SLEEP_ON_ERROR_MIN (5 минут после ошибки)
    assert вызовы_сна[0] == loop.SLEEP_ON_ERROR_MIN


def test_loop_сбрасывает_прервано_при_повторном_запуске(monkeypatch):
    """Если main() вызывается дважды в том же процессе, флаг _прервано
    должен сбрасываться — иначе второй вызов пропустит все итерации."""
    loop._прервано = True  # симулируем состояние после предыдущего сигнала
    итераций: list[int] = []

    def моковый_запуск(args, work_min):
        итераций.append(work_min)
        return 0

    monkeypatch.setattr(loop, "_запустить_итерацию", моковый_запуск)
    monkeypatch.setattr(loop, "_сон_минут", lambda m: None)

    код = loop.main([
        "--max-iterations", "1",
        "--work-min-low", "10", "--work-min-high", "10",
        "--sleep-min-low", "0", "--sleep-min-high", "0",
    ])
    assert код == 0
    assert len(итераций) == 1, "флаг не сбросился, итерация не запустилась"


# ---------- s3_upload.py ----------

def test_s3_нет_кредов_возвращает_none(monkeypatch, capsys):
    """Без env-переменных клиент не создаётся."""
    for k in ("S3_ENDPOINT_URL", "S3_BUCKET", "S3_ACCESS_KEY", "S3_SECRET_KEY"):
        monkeypatch.delenv(k, raising=False)
    клиент, bucket = s3_upload._получить_клиент()
    assert клиент is None and bucket is None
    assert "креды не заданы" in capsys.readouterr().out


def test_s3_загрузить_без_кредов_возвращает_0(monkeypatch):
    for k in ("S3_ENDPOINT_URL", "S3_BUCKET", "S3_ACCESS_KEY", "S3_SECRET_KEY"):
        monkeypatch.delenv(k, raising=False)
    assert s3_upload.загрузить() == 0


def test_s3_собрать_файлы_пропускает_несуществующие_папки(tmp_path, monkeypatch):
    """Если all_pdfs/ / harvested_meta/ не существуют — пустой список."""
    monkeypatch.setattr(s3_upload, "_БАЗА", str(tmp_path))
    assert s3_upload._собрать_локальные_файлы("") == []


def test_s3_собрать_файлы_обнаруживает_pdf(tmp_path, monkeypatch):
    """Реальные файлы в all_pdfs/ → попадают в список с правильными ключами."""
    monkeypatch.setattr(s3_upload, "_БАЗА", str(tmp_path))
    pdf_dir = tmp_path / "all_pdfs"
    pdf_dir.mkdir()
    (pdf_dir / "test.pdf").write_bytes(b"%PDF-fake")
    meta_dir = tmp_path / "harvested_meta"
    meta_dir.mkdir()
    (meta_dir / "test.json").write_text("{}", encoding="utf-8")

    файлы = s3_upload._собрать_локальные_файлы("")
    ключи = [k for _, k in файлы]
    assert "all_pdfs/test.pdf" in ключи
    assert "harvested_meta/test.json" in ключи


def test_s3_собрать_файлы_с_префиксом(tmp_path, monkeypatch):
    monkeypatch.setattr(s3_upload, "_БАЗА", str(tmp_path))
    pdf_dir = tmp_path / "all_pdfs"
    pdf_dir.mkdir()
    (pdf_dir / "x.pdf").write_bytes(b"data")
    файлы = s3_upload._собрать_локальные_файлы("harvester/")
    assert файлы[0][1] == "harvester/all_pdfs/x.pdf"


def test_s3_загрузить_пропускает_существующие(tmp_path, monkeypatch):
    """Если HeadObject говорит что ключ есть — не заливаем повторно."""
    monkeypatch.setattr(s3_upload, "_БАЗА", str(tmp_path))
    pdf_dir = tmp_path / "all_pdfs"
    pdf_dir.mkdir()
    (pdf_dir / "a.pdf").write_bytes(b"data-a")
    (pdf_dir / "b.pdf").write_bytes(b"data-b")

    for k, v in {
        "S3_ENDPOINT_URL": "https://fake",
        "S3_BUCKET": "test-bucket",
        "S3_ACCESS_KEY": "ak",
        "S3_SECRET_KEY": "sk",
    }.items():
        monkeypatch.setenv(k, v)

    клиент = MagicMock()
    # a уже есть, b новый
    def head_side(Bucket, Key):
        if Key.endswith("a.pdf"):
            return {}
        raise _эмулировать_no_such_key()
    клиент.head_object.side_effect = head_side

    with patch.object(s3_upload, "_получить_клиент", return_value=(клиент, "test-bucket")):
        залито = s3_upload.загрузить()

    assert клиент.upload_file.call_count == 1
    args, _ = клиент.upload_file.call_args
    assert args[2].endswith("b.pdf")  # третий арг — Key
    assert залито == 1


def _эмулировать_no_such_key():
    """Ошибка NoSuchKey через botocore.ClientError."""
    from botocore.exceptions import ClientError
    return ClientError(
        {"Error": {"Code": "404", "Message": "Not Found"}},
        "HeadObject",
    )
