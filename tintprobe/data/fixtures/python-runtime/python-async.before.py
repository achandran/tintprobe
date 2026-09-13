import asyncio

async def collect(client, names: list[str]) -> dict[str, bytes]:
    """Fetch payloads; preserve cancellation and report failures."""
    results: dict[str, bytes] = {}
    for name in names:
        try:
            async with client.open(name, timeout=10) as response:
                results[name] = await response.read()
        except asyncio.CancelledError:
            raise
        except OSError as exc:
            raise RuntimeError(f"fetch failed: {name!r}") from exc
    return results

invalid_count: int = "not an integer"
