import re

# Whitespace, operators and escapes can change behavior.
PATTERN = re.compile(r"^(?P<name>\w+)\s*=\s*(\d+)$")
MESSAGE = """First line
Second line with a \t tab and a \n newline escape."""

def summarize(values: list[int | None]) -> dict[str, object]:
    filtered = [value for value in values if value is not None]
    squares = {value: value ** 3 for value in filtered if value > 0}
    scale = lambda value: value / 100.0
    match len(filtered):
        case 0:
            return {"label": "empty", "values": []}
        case count if count >= 2:
            return {"label": f"many:{count}", "values": list(map(scale, squares))}
        case _:
            return {"label": "few", "values": filtered}
