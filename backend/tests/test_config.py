"""Configuration validation tests."""

from __future__ import annotations

import pytest
from conftest import make_settings
from pydantic import ValidationError


def test_default_settings_are_valid() -> None:
    settings = make_settings()
    assert settings.agentguard_base_url == "http://127.0.0.1:8000"
    assert settings.agentguard_api_timeout == 15.0
    assert settings.cors_origin_list == ["http://localhost:5173"]


@pytest.mark.parametrize(
    "bad_url",
    [
        "ftp://127.0.0.1:8000",                      # wrong scheme
        "http://user:pass@127.0.0.1:8000",           # embedded credentials
        "http://127.0.0.1:8000/v1/system/health",    # path not allowed
        "http://127.0.0.1:8000?x=1",                 # query not allowed
        "http://127.0.0.1:8000#frag",                # fragment not allowed
        "http://127.0.0.1:99999",                    # invalid port
        "http://",                                   # no host
    ],
)
def test_rejects_invalid_agentguard_base_url(bad_url: str) -> None:
    with pytest.raises(ValidationError):
        make_settings(agentguard_base_url=bad_url)


@pytest.mark.parametrize("timeout", [0.0, -1.0, 121.0, 500])
def test_rejects_out_of_range_timeout(timeout: float) -> None:
    with pytest.raises(ValidationError):
        make_settings(agentguard_api_timeout=timeout)


def test_rejects_wildcard_cors_origin() -> None:
    with pytest.raises(ValidationError):
        make_settings(app_cors_origins="*")


def test_allows_trailing_slash_on_base_url() -> None:
    settings = make_settings(agentguard_base_url="http://127.0.0.1:8000/")
    assert settings.agentguard_base_url == "http://127.0.0.1:8000"


def test_data_mode_override_survives_validation() -> None:
    settings = make_settings(app_data_mode="synthetic")
    assert settings.app_data_mode == "synthetic"
