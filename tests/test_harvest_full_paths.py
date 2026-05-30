"""Регрессия C9: harvester.harvest_full запускает скрипты из pipeline/, не из корня.

До фикса harvest_full звал `python ingest_v2.py` от cwd=корень репо. Скрипты
живут в `pipeline/ingest_v2.py`. subprocess не находил их и падал с rc=2
(FileNotFoundError из python -c). _запустить ловил исключение и записывал
rc=1, но harvest_full.main всё равно возвращал 0 — и loop считал итерацию
успешной. В итоге CI делал harvest, но никогда не делал ingest+embed.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from harvester import harvest_full


def test_C9_ingest_шаг_использует_pipeline_путь(monkeypatch, tmp_path):
    """`команда_ingest` должна указывать на pipeline/ingest_v2.py, не на ingest_v2.py.

    Раньше subprocess стартовал с cwd=корень репо и не мог найти `ingest_v2.py`,
    потому что файл живёт в pipeline/. Молча падал, в логах rc != 0, но
    harvest_full всё равно возвращал 0 и loop крутил пустые итерации.
    """
    запуски: list[list[str]] = []

    def фейк_запуск(команда, окруж=None):
        запуски.append(команда)
        return 0, 0.1

    monkeypatch.setattr(harvest_full, "_запустить", фейк_запуск)
    # Эмулируем что rclone, Drive и S3 всё пропускают
    monkeypatch.delenv("GDRIVE_REMOTE", raising=False)
    monkeypatch.delenv("RCLONE_CONFIG", raising=False)
    monkeypatch.delenv("S3_BUCKET", raising=False)
    monkeypatch.setattr(harvest_full, "ПАПКА_ЛОГОВ", str(tmp_path / "logs"))

    harvest_full.main(["--budget", "1", "--time-limit-min", "5"])

    # Должно быть 3 шага: harvest, ingest, embed (Drive/S3 шаги пропущены через env)
    скрипты = [команда[1] for команда in запуски]
    assert any("pipeline" in путь and "ingest_v2.py" in путь for путь in скрипты), (
        "ingest_v2.py должен запускаться из pipeline/, не из корня. "
        f"Команды: {скрипты}"
    )
    assert any("pipeline" in путь and "embed_resume_v2.py" in путь for путь in скрипты), (
        "embed_resume_v2.py должен запускаться из pipeline/, не из корня. "
        f"Команды: {скрипты}"
    )
    # И не должно быть прямого вызова без pipeline/
    плохих = [путь for путь in скрипты if путь in ("ingest_v2.py", "embed_resume_v2.py")]
    assert плохих == [], (
        f"Найдены вызовы скриптов из корня (баг C9): {плохих}"
    )


def test_C9_pipeline_файлы_существуют():
    """Сам pipeline/ должен содержать запускаемые скрипты — иначе фикс не имеет смысла."""
    репо = Path(__file__).resolve().parent.parent
    assert (репо / "pipeline" / "ingest_v2.py").is_file()
    assert (репо / "pipeline" / "embed_resume_v2.py").is_file()
    # И что в корне их НЕТ — иначе обе ветки будут работать
    assert not (репо / "ingest_v2.py").is_file()
    assert not (репо / "embed_resume_v2.py").is_file()
