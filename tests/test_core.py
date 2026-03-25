import pytest
from core.env_validator import validate_environment
from core.mineru_client import MinerUConverter

def test_mineru_converter_init_empty():
    with pytest.raises(ValueError):
        MinerUConverter([])
        
    with pytest.raises(ValueError):
        MinerUConverter(["", "   "])

def test_mineru_converter_init_valid():
    converter = MinerUConverter(["test_key", "  "])
    assert converter.api_keys == ["test_key"]

def test_validate_environment_mocked(monkeypatch):
    import shutil
    monkeypatch.setattr(shutil, "which", lambda x: "/usr/bin/pandoc")
    try:
        validate_environment()
    except Exception as e:
        pytest.fail(f"validate_environment raised an exception: {e}")

def test_validate_environment_missing_pandoc(monkeypatch):
    import shutil
    monkeypatch.setattr(shutil, "which", lambda x: None)
    with pytest.raises(RuntimeError, match="未检测到 Pandoc 命令行工具"):
        validate_environment()
