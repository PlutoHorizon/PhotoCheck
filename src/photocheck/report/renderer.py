"""Jinja2 rendering for the HTML report."""

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape


_TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"


def get_env() -> Environment:
    """Return a Jinja2 Environment with autoescape enabled for HTML."""
    return Environment(
        loader=FileSystemLoader(str(_TEMPLATE_DIR)),
        autoescape=select_autoescape(["html"]),
        keep_trailing_newline=True,
    )


def render_report(context: dict, output_path: Path) -> None:
    """Render the main report template to output_path."""
    env = get_env()
    template = env.get_template("report.html.j2")
    output_path.write_text(template.render(**context), encoding="utf-8")


def render_lenses(context: dict, output_path: Path) -> None:
    """Render the all-lenses subpage template to output_path."""
    env = get_env()
    template = env.get_template("lenses.html.j2")
    output_path.write_text(template.render(**context), encoding="utf-8")
