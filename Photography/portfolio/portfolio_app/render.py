"""Template rendering for the portfolio site.

Thin wrapper around ``string.Template``: templates live in ``templates/``
(sibling of ``portfolio_app/``) and use ``$var`` placeholders.
``safe_substitute`` is used so CSS/JS braces — and any placeholder a caller
does not supply — pass through untouched; a literal dollar sign in a template
must be written ``$$``.

Templates are re-read from disk on every render (they are tiny, and this
keeps design iteration live without a server restart — same philosophy as
the ``no-cache`` headers in ``photo_server.py``).
"""
from __future__ import annotations

from html import escape as html_escape  # re-exported: canonical escaper for callers
from pathlib import Path
from string import Template

from . import config

__all__ = ["render", "html_escape", "TEMPLATE_DIR"]

TEMPLATE_DIR: Path = config.ROOT / "templates"


def render(template_name: str, **ctx) -> str:
    """Render ``templates/<template_name>`` with ``$var`` substitution.

    Values are substituted verbatim (``str()``-converted by ``Template``):
    callers MUST ``html_escape`` any user-controlled string *before* passing
    it in. Unknown placeholders are left as-is (``safe_substitute``).
    """
    text = (TEMPLATE_DIR / template_name).read_text(encoding="utf-8")
    return Template(text).safe_substitute(ctx)
