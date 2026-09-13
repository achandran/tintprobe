"""Color measurements for opaque sRGB; heuristic metrics are not certification."""
from coloraide.everything import ColorAll as Color

def rgb(hex_color: str) -> list[int]:
    value = hex_color.removeprefix("#")
    return [int(value[index : index + 2], 16) for index in (0, 2, 4)]


def wcag(foreground: str, background: str) -> float:
    return Color(foreground).contrast(Color(background), method="wcag21")


def apca(foreground: str, background: str) -> float:
    """APCA 0.1.9 W3/SAPC-8 calculation for opaque sRGB colors.

    Ported from the W3-licensed `apca-w3` reference implementation. Negative
    values represent light text on a dark background. Keep the sign because
    APCA is polarity-sensitive.
    """

    def y(hex_color: str) -> float:
        r, g, b = (channel / 255 for channel in rgb(hex_color))
        return 0.2126729 * r**2.4 + 0.7151522 * g**2.4 + 0.0721750 * b**2.4

    text_y, background_y = y(foreground), y(background)
    black_threshold = 0.022
    black_clamp = 1.414
    if text_y < black_threshold:
        text_y += (black_threshold - text_y) ** black_clamp
    if background_y < black_threshold:
        background_y += (black_threshold - background_y) ** black_clamp
    if abs(background_y - text_y) < 0.0005:
        return 0.0

    if background_y > text_y:
        sapc = (background_y**0.56 - text_y**0.57) * 1.14
        return 0.0 if sapc < 0.1 else (sapc - 0.027) * 100

    sapc = (background_y**0.65 - text_y**0.62) * 1.14
    return 0.0 if sapc > -0.1 else (sapc + 0.027) * 100


def oklch(hex_color: str) -> tuple[float, float, float]:
    lightness, chroma, hue = Color(hex_color).convert("oklch").coords()
    return lightness, chroma, hue


def delta_e(first: str, second: str, simulation: str = "normal") -> float:
    left, right = Color(first), Color(second)
    if simulation in {"protan", "deutan", "tritan"}:
        left = left.filter(simulation, 1, method="machado")
        right = right.filter(simulation, 1, method="machado")
    elif simulation == "grayscale":
        left = left.filter("grayscale", 1)
        right = right.filter("grayscale", 1)
    return left.delta_e(right, method="ok")


def simulated_hex(hex_color: str, simulation: str) -> str:
    color = Color(hex_color)
    if simulation in {"protan", "deutan", "tritan"}:
        color = color.filter(simulation, 1, method="machado")
    elif simulation == "grayscale":
        color = color.filter("grayscale", 1)
    return color.convert("srgb").to_string(hex=True).upper()
