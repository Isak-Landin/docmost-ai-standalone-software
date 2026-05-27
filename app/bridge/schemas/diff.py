from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class DiffHunk:
    kind: str
    local_start_line: int
    local_end_line: int
    remote_start_line: int
    remote_end_line: int
    local_lines: list[str] = field(default_factory=list)
    remote_lines: list[str] = field(default_factory=list)
