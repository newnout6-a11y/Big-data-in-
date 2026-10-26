"""Проверка фактических env/if выражений workflow без секретов и сети."""
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml


def _evaluate(expression, config, remote):
    # Используем подмножество Actions expressions из env/if этого workflow.
    expression = expression.removeprefix("${{").removesuffix("}}").strip()
    return eval(expression.replace("&&", " and ").replace("||", " or "),
                {"__builtins__": {}},
                {"env": SimpleNamespace(RCLONE_CONFIG_CONTENT=config),
                 "vars": SimpleNamespace(GDRIVE_REMOTE=remote)})


@pytest.mark.parametrize("config,remote,expected", [
    ("", "", ""), ("", "custom", ""),
    ("configured", "", "gdrive"), ("configured", "custom", "custom"),
])
def test_drive_is_enabled_only_when_workflow_installs_and_configures_it(config, remote, expected):
    workflow = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "harvest.yml"
    steps = yaml.safe_load(workflow.read_text(encoding="utf-8"))["jobs"]["harvest"]["steps"]
    loop = next(step for step in steps if step["name"].startswith("Run harvester.loop"))
    assert _evaluate(loop["env"]["GDRIVE_REMOTE"], config, remote) == expected
    for step in steps:
        if step["name"] in {"Install rclone", "Write rclone.conf from secret"} or step["name"].startswith("Restore Drive"):
            assert bool(_evaluate(step["if"], config, remote)) == bool(expected)
