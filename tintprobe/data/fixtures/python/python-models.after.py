from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar

# Keep the public model readable while reviewing defaults.
@dataclass(frozen=False)
class Job:
    """A queued task with an optional output directory."""
    retries: int = 3
    output: Path | None = None
    tags: ClassVar[tuple[str, ...]] = ("batch", "python")

    @property
    def label(self) -> str:
        return f"job:{self.retries:02d} / {self.output!s}"
