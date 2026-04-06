"""CLI entry point: shacl2pydantic shapes.ttl [-o models.py]."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import click

from .generator import generate_code
from .parser import parse_file


@click.command()
@click.argument("ttl_path", type=click.Path())
@click.option("-o", "--output", type=click.Path(), default=None, help="Write to file")
@click.version_option(version="0.1.0", prog_name="shacl2pydantic")
def cli(ttl_path: str, output: str | None) -> None:
    """Convert SHACL Turtle file to Pydantic v2 model classes."""
    log = logging.getLogger("shacl2pydantic")
    log.setLevel(logging.WARNING)
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
    log.addHandler(handler)

    try:
        code = generate_code(parse_file(ttl_path))
    except FileNotFoundError:
        click.echo(f"Error: File not found: {ttl_path}", err=True)
        raise SystemExit(1)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)

    if output:
        Path(output).write_text(code)
    else:
        click.echo(code, nl=False)


def main() -> None:
    """Entry point for console_scripts."""
    cli()
