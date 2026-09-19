from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

# Backslash must be handled first, and its replacement must not be re-escaped.
_ESCAPES = [
    ("\\", r"\textbackslash{}"),
    ("&", r"\&"),
    ("%", r"\%"),
    ("$", r"\$"),
    ("#", r"\#"),
    ("_", r"\_"),
    ("{", r"\{"),
    ("}", r"\}"),
    ("~", r"\textasciitilde{}"),
    ("^", r"\textasciicircum{}"),
]

_SMART = {
    "–": "--", "—": "---", "‘": "`", "’": "'",
    "“": "``", "”": "''", "…": r"\ldots{}", " ": "~",
}

_PAGES_RE = re.compile(r"Output written on .*?\((\d+) pages?,")
_TEXERR_RE = re.compile(r"^! (.+)$", re.MULTILINE)


def tex_escape(text: str) -> str:
    """Make arbitrary text safe to drop into a LaTeX document."""
    if not text:
        return ""
    out = text
    for ch, rep in _SMART.items():
        out = out.replace(ch, rep)
    # Split on the backslash replacement so we never double-escape it.
    parts = out.split("\\")
    escaped = []
    for part in parts:
        for ch, rep in _ESCAPES[1:]:
            part = part.replace(ch, rep)
        escaped.append(part)
    return r"\textbackslash{}".join(escaped)


def make_env(templates_dir: Path | None = None) -> Environment:
    """Jinja with LaTeX-safe delimiters, so << >> and <% %> replace {{ }} and {% %}."""
    if templates_dir is None:
        from rfactory.config import settings

        templates_dir = settings.templates_dir
    env = Environment(
        loader=FileSystemLoader(templates_dir),
        block_start_string="<%",
        block_end_string="%>",
        variable_start_string="<<",
        variable_end_string=">>",
        comment_start_string="<#",
        comment_end_string="#>",
        trim_blocks=True,
        lstrip_blocks=True,
        autoescape=False,
        undefined=StrictUndefined,
    )
    env.filters["tex"] = tex_escape
    return env


class LatexError(RuntimeError):
    pass


@dataclass(slots=True)
class CompileResult:
    pdf: bytes
    pages: int
    log: str


def compile_tex(
    tex_source: str,
    *,
    jobname: str = "document",
    aux_files: dict[str, Path] | None = None,
    extra_sources: dict[str, str] | None = None,
    passes: int = 1,
    engine_name: str | None = None,
) -> CompileResult:
    """Compile LaTeX to PDF in a scratch dir.

    aux_files maps a destination filename (e.g. 'TLCresume.sty') to a path copied in
    alongside the .tex. extra_sources maps a destination filename to literal text,
    for generated companions such as the cover letter's info.tex and body.tex."""
    if engine_name is None:
        from rfactory.config import settings

        engine_name = settings.latex_engine
    engine = shutil.which(engine_name)
    if engine is None:
        raise LatexError(
            f"{engine_name} not found on PATH. Install MacTeX/BasicTeX, "
            "or set RF_LATEX_ENGINE."
        )

    with tempfile.TemporaryDirectory(prefix="rfactory-") as tmp:
        work = Path(tmp)
        (work / f"{jobname}.tex").write_text(tex_source, encoding="utf-8")
        for dest, src in (aux_files or {}).items():
            shutil.copy(Path(src), work / dest)
        for dest, text in (extra_sources or {}).items():
            (work / dest).write_text(text, encoding="utf-8")

        log = ""
        for _ in range(max(1, passes)):
            proc = subprocess.run(
                [engine, "-interaction=nonstopmode", "-halt-on-error", f"{jobname}.tex"],
                cwd=work,
                capture_output=True,
                text=True,
                timeout=120,
            )
            log_path = work / f"{jobname}.log"
            log = log_path.read_text(encoding="utf-8", errors="replace") if log_path.exists() else proc.stdout
            if proc.returncode != 0:
                errors = _TEXERR_RE.findall(log) or [proc.stdout[-1500:]]
                raise LatexError("LaTeX failed:\n" + "\n".join(errors[:5]))

        pdf_path = work / f"{jobname}.pdf"
        if not pdf_path.exists():
            raise LatexError("LaTeX reported success but produced no PDF.")

        match = _PAGES_RE.search(log)
        return CompileResult(pdf=pdf_path.read_bytes(), pages=int(match.group(1)) if match else 0, log=log)
