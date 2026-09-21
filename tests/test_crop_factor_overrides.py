"""Tests for user-configured crop factor overrides via photocheck.toml.

Built-in table covers common bodies. Users with unusual cameras
(e.g. Fuji GFX, OM System OM-1, Sony RX1) can extend it by adding
[[crop_factors]] entries to photocheck.toml.
"""

import tomllib
from pathlib import Path
from unittest.mock import patch

import pytest

from photocheck.cli import _apply_crop_factor_overrides
from photocheck.core.extractor import (
    CAMERA_CROP_FACTORS,
    get_crop_factor,
    set_crop_factor_overrides,
)


@pytest.fixture(autouse=True)
def _reset_overrides():
    """Reset module state between tests so they don't leak."""
    yield
    set_crop_factor_overrides(None)


class TestSetCropFactorOverrides:
    """Module-level state management."""

    def test_none_resets_to_builtins(self):
        """Passing None reverts to the built-in table."""
        set_crop_factor_overrides([("FooCam", 1.7)])
        assert get_crop_factor("FooCam") == 1.7
        set_crop_factor_overrides(None)
        assert get_crop_factor("FooCam") == 1.0  # unknown → default

    def test_user_entry_beats_shorter_builtin(self):
        """User entry with longer prefix wins over shorter built-in.

        Example: built-in "ILCE-7" → 1.0 (FF). User adds
        "ILCE-7C" → 1.0 explicitly (longer prefix wins).
        """
        set_crop_factor_overrides([("ILCE-7C", 1.0)])
        # Both yield 1.0 here so this only verifies the lookup doesn't crash
        assert get_crop_factor("ILCE-7CM2") == 1.0

    def test_user_can_override_builtin_factor(self):
        """User entry with longer prefix overrides built-in factor.

        Built-in: "ILCE-6" → 1.5 (APS-C). User adds "ILCE-6400"
        → 1.0 to mark their specific body as FF (e.g. a 6400 with
        full-frame sensor mod). Longer prefix wins.
        """
        set_crop_factor_overrides([("ILCE-6400", 1.0)])
        assert get_crop_factor("ILCE-6400") == 1.0
        # Other ILCE-6xxx bodies still use built-in 1.5
        assert get_crop_factor("ILCE-6700") == 1.5


class TestApplyFromConfig:
    """The cli.py helper that loads photocheck.toml."""

    def test_no_config_returns_zero(self, tmp_path, monkeypatch):
        """Missing config file → 0 overrides applied, no error."""
        monkeypatch.chdir(tmp_path)
        assert _apply_crop_factor_overrides() == 0

    def test_loads_toml_array_of_tables(self, tmp_path, monkeypatch):
        """[[crop_factors]] with match + factor entries are loaded."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "photocheck.toml").write_text(
            '[[crop_factors]]\nmatch = "OM-1"\nfactor = 2.0\n\n'
            '[[crop_factors]]\nmatch = "GFX 100"\nfactor = 0.79\n'
        )
        n = _apply_crop_factor_overrides()
        assert n == 2
        assert get_crop_factor("OM-1") == 2.0
        assert get_crop_factor("GFX 100") == 0.79

    def test_skips_invalid_entries(self, tmp_path, monkeypatch):
        """Entries missing match/factor or with bad types are silently skipped."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "photocheck.toml").write_text(
            '[[crop_factors]]\nmatch = "GoodModel"\nfactor = 1.5\n\n'
            '[[crop_factors]]\nmatch = "NoFactor"\n\n'  # missing factor
            '[[crop_factors]]\nfactor = 1.5\n\n'        # missing match
            '[[crop_factors]]\nmatch = "BadFactor"\nfactor = "not-a-number"\n'
        )
        n = _apply_crop_factor_overrides()
        assert n == 1
        assert get_crop_factor("GoodModel") == 1.5
        assert get_crop_factor("BadFactor") == 1.0  # not applied

    def test_empty_section_returns_zero(self, tmp_path, monkeypatch):
        """[crop_factors] present but empty → 0 overrides."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "photocheck.toml").write_text("[crop_factors]\n")
        assert _apply_crop_factor_overrides() == 0

    def test_uses_builtin_for_known_body(self, tmp_path, monkeypatch):
        """Built-in table still resolves known bodies when no overrides exist."""
        monkeypatch.chdir(tmp_path)
        # No overrides file → built-ins apply
        assert _apply_crop_factor_overrides() == 0
        # Built-in 80D → 1.6
        assert get_crop_factor("Canon EOS 80D") == 1.6

    def test_user_adds_unusual_camera(self, tmp_path, monkeypatch):
        """User can add a body not in the built-in table (e.g. Fuji GFX 100S)."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "photocheck.toml").write_text(
            '[[crop_factors]]\nmatch = "GFX100S"\nfactor = 0.79\n'
        )
        _apply_crop_factor_overrides()
        assert get_crop_factor("GFX100S") == 0.79

    def test_malformed_toml_silently_ignored(self, tmp_path, monkeypatch):
        """If photocheck.toml is corrupt, overrides silently disabled."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "photocheck.toml").write_text("not valid toml {{{}}")
        # Should not raise; built-ins still apply
        assert _apply_crop_factor_overrides() == 0
        assert get_crop_factor("Canon EOS 80D") == 1.6