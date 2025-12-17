from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator


@dataclass
class FollowState:
    path: str
    offset: int = 0
    inode: int | None = None


def _inode_of(path: Path) -> int | None:
    try:
        return path.stat().st_ino
    except FileNotFoundError:
        return None


def load_state(state_path: Path, log_path: Path) -> FollowState:
    if not state_path.exists():
        return FollowState(path=str(log_path), offset=0, inode=_inode_of(log_path))
    try:
        raw = json.loads(state_path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("state not dict")
        return FollowState(
            path=str(raw.get("path") or str(log_path)),
            offset=int(raw.get("offset") or 0),
            inode=(int(raw["inode"]) if "inode" in raw and raw["inode"] is not None else None),
        )
    except Exception:
        return FollowState(path=str(log_path), offset=0, inode=_inode_of(log_path))


def save_state(state_path: Path, state: FollowState) -> None:
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(
        json.dumps({"path": state.path, "offset": state.offset, "inode": state.inode}),
        encoding="utf-8",
    )


def follow_json_lines(
    log_path: Path,
    state_path: Path,
    poll_s: float = 0.5,
    start_at_end: bool = True,
) -> Iterator[dict[str, Any]]:
    """
    Follow a JSONL file with basic rotation/truncation handling.

    - Uses inode+offset to continue from previous position.
    - If the file is truncated or rotated, resets offset safely.
    """
    state = load_state(state_path=state_path, log_path=log_path)

    if start_at_end and state.offset == 0 and log_path.exists():
        try:
            state.offset = log_path.stat().st_size
            state.inode = _inode_of(log_path)
            save_state(state_path, state)
        except FileNotFoundError:
            pass

    while True:
        if not log_path.exists():
            time.sleep(poll_s)
            continue

        current_inode = _inode_of(log_path)
        try:
            size = log_path.stat().st_size
        except FileNotFoundError:
            time.sleep(poll_s)
            continue

        rotated = state.inode is not None and current_inode is not None and current_inode != state.inode
        truncated = size < state.offset
        if rotated or truncated:
            state.offset = 0
            state.inode = current_inode
            save_state(state_path, state)

        try:
            with log_path.open("rb") as f:
                f.seek(state.offset, os.SEEK_SET)
                while True:
                    line = f.readline()
                    if not line:
                        break
                    state.offset = f.tell()
                    state.inode = current_inode
                    save_state(state_path, state)
                    try:
                        obj = json.loads(line.decode("utf-8", errors="replace"))
                        if isinstance(obj, dict):
                            yield obj
                    except Exception:
                        continue
        except FileNotFoundError:
            pass

        time.sleep(poll_s)

