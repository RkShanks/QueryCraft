"""Write or verify the canonical OpenAPI document from the FastAPI app."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

DEFAULT_OUTPUT = Path(__file__).resolve().parents[1] / "openapi.json"
SCHEMA_ENVIRONMENT_DEFAULTS = {
    "DATABASE_URL": "postgresql+asyncpg://openapi:openapi@localhost/openapi",
    "PLATFORM_ENCRYPTION_KEY": "openapi-generation-only",
}


def canonical_openapi_bytes() -> bytes:
    """Return the deterministic UTF-8 representation of the runtime schema."""
    for variable_name, default_value in SCHEMA_ENVIRONMENT_DEFAULTS.items():
        os.environ.setdefault(variable_name, default_value)
    from app.main import create_app

    schema = create_app().openapi()
    document = json.dumps(schema, ensure_ascii=False, indent=2, sort_keys=True)
    return f"{document}\n".encode()


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Fail when the output file differs instead of writing it.",
    )
    return parser.parse_args()


def main() -> int:
    """Generate the document, or check the checked-in copy for drift."""
    arguments = _arguments()
    generated = canonical_openapi_bytes()
    if arguments.check:
        if not arguments.output.exists() or arguments.output.read_bytes() != generated:
            print(f"OpenAPI drift detected: regenerate {arguments.output}")
            return 1
        return 0

    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_bytes(generated)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
