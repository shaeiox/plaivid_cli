"""Small formatting helpers shared by inventory-page components."""


def display(value: int | float | str | None, *, suffix: str = "") -> str:
    """Render absent inventory data as an em dash rather than a fabricated zero."""
    return "—" if value is None else f"{value}{suffix}"
