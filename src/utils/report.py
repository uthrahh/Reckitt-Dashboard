"""
report.py

Shared formatting helpers for the pipeline's production-style console
log. WHY A SEPARATE MODULE (vs inline print formatting in main.py):
every stage (ingestion, validation, cleaning, feature engineering, star
schema, export) needs the same banner/section/key-value style — putting
it here keeps main.py focused on orchestration, not string formatting,
and keeps the log format consistent if it's ever changed in one place.
"""

SEPARATOR_WIDTH = 50


def print_section(title: str) -> None:
    """Prints a banner section header, e.g. '=== INGESTION ==='."""
    bar = "=" * SEPARATOR_WIDTH
    print(bar)
    print(title)
    print(bar)


def print_kv(label: str, value) -> None:
    """Prints a single 'Label : Value' line."""
    print(f"{label} : {value}")


def print_subsection(title: str) -> None:
    """Prints a lightweight sub-heading within a section (no border)."""
    print(f"\n{title}")


def print_close() -> None:
    """Prints the closing bar for a section, with a trailing blank line."""
    print("=" * SEPARATOR_WIDTH)
    print()


def format_bytes(num_bytes: int) -> str:
    """Formats a byte count as a human-readable size string."""
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"
