from pathlib import Path

import pytest
import yaml

from workshop.config import load_config

ROOT = Path(__file__).resolve().parents[1]


def test_offline_default_has_no_live_authority():
    config = load_config(ROOT / "demo.yaml")
    assert not config.security.allow_live_read
    assert not config.security.allow_live_write
    assert config.fabric.workspace_id is None


@pytest.mark.parametrize(
    ("section", "key", "value"),
    [
        ("fabric", "sandbox", "false"),
        ("fabric", "workspace_id", "../../other"),
        ("fabric", "workspace_name", "name.Workspace/other"),
        ("security", "allow_live_read", 1),
        ("security", "approved_data", "production"),
        ("security", "allow_live_write", True),
        ("fabric", "typo", "ignored?"),
    ],
)
def test_rejects_unsafe_or_unknown_values(tmp_path, section, key, value):
    data = yaml.safe_load((ROOT / "demo.yaml").read_text())
    data[section][key] = value
    path = tmp_path / "demo.yaml"
    path.write_text(yaml.safe_dump(data))
    with pytest.raises(ValueError):
        load_config(path)


def test_rejects_duplicate_yaml_keys(tmp_path):
    path = tmp_path / "demo.yaml"
    path.write_text("version: 1\nversion: 2\n")
    with pytest.raises(ValueError, match="duplicate"):
        load_config(path)


def test_live_reads_require_a_selected_tenant_and_workspace(tmp_path):
    data = yaml.safe_load((ROOT / "demo.yaml").read_text())
    data["security"]["allow_live_read"] = True
    path = tmp_path / "demo.yaml"
    path.write_text(yaml.safe_dump(data))
    with pytest.raises(ValueError, match="tenant"):
        load_config(path)
