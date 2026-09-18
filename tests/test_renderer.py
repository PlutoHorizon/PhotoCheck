"""Tests for photocheck.report.renderer."""

import pytest

from photocheck.report.renderer import (
    get_env,
    render_lenses,
    render_report,
)


def test_get_env_returns_jinja2_environment():
    env = get_env()
    assert hasattr(env, "get_template")
    assert callable(env.get_template)


def test_render_report_creates_file(tmp_path, sample_metadata):
    from photocheck.report.stats import compute_all
    stats = compute_all(sample_metadata, top_n=5)
    context = {**stats, "charts_dir": "charts", "generated_at": "2026-09-18"}
    output = tmp_path / "index.html"
    render_report(context, output)
    assert output.exists()
    content = output.read_text(encoding="utf-8")
    assert "FE 35mm F1.4 GM" in content
    assert "html" in content.lower()


def test_render_report_with_empty_data(tmp_path, empty_metadata):
    from photocheck.report.stats import compute_all
    stats = compute_all(empty_metadata, top_n=5)
    context = {**stats, "charts_dir": "charts", "generated_at": "2026-09-18"}
    output = tmp_path / "index.html"
    render_report(context, output)
    assert output.exists()
    content = output.read_text(encoding="utf-8")
    assert "<!DOCTYPE" in content or "<html" in content


def test_render_lenses_creates_file(tmp_path, sample_metadata):
    from photocheck.report.stats import compute_all
    stats = compute_all(sample_metadata, top_n=5)
    context = {**stats, "charts_dir": "charts", "generated_at": "2026-09-18"}
    output = tmp_path / "lenses.html"
    render_lenses(context, output)
    assert output.exists()
