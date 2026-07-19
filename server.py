from __future__ import annotations

import base64
import ctypes
import json
import os
import re
import subprocess
import time
import unicodedata
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Literal

from mcp.server.fastmcp import FastMCP


SEARCH_ENDPOINT = "https://music.163.com/api/search/get/web"

MEDIA_KEYS = {
    "play_pause": 0xB3,
    "stop": 0xB2,
    "next": 0xB0,
    "previous": 0xB1,
    "volume_up": 0xAF,
    "volume_down": 0xAE,
    "mute": 0xAD,
}

APP_SHORTCUTS = {
    "like": (0x11, 0x12, ord("L")),       # Ctrl+Alt+L
    "lyrics": (0x11, 0x12, ord("D")),     # Ctrl+Alt+D
    "mini_mode": (0x11, 0x12, ord("M")),  # Ctrl+Alt+M
}

KEYEVENTF_KEYUP = 0x0002

mcp = FastMCP(
    "GPT CloudMusic Control",
    instructions=(
        "Local-only controls for the NetEase Cloud Music desktop client. "
        "Use search_and_play to play a requested song or playlist. Use "
        "control_netease for playback and volume controls. The server never "
        "reads browser cookies, account credentials, listening history, or "
        "private files."
    ),
)


def _cloudmusic_exe() -> Path:
    configured = os.environ.get("CLOUDMUSIC_EXE")
    if configured:
        return Path(configured).expanduser()

    candidates = [
        Path(os.environ.get("PROGRAMFILES", r"C:\Program Files"))
        / "NetEase"
        / "CloudMusic"
        / "cloudmusic.exe",
        Path(os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)"))
        / "NetEase"
        / "CloudMusic"
        / "cloudmusic.exe",
        Path.home() / "AppData" / "Local" / "NetEase" / "CloudMusic" / "cloudmusic.exe",
    ]
    return next((path for path in candidates if path.is_file()), candidates[0])


def _require_cloudmusic_exe() -> Path:
    executable = _cloudmusic_exe()
    if not executable.is_file():
        raise FileNotFoundError(f"NetEase Cloud Music executable not found: {executable}")
    return executable


def _is_cloudmusic_running() -> bool:
    completed = subprocess.run(
        ["tasklist", "/FI", "IMAGENAME eq cloudmusic.exe", "/FO", "CSV", "/NH"],
        check=False,
        capture_output=True,
        text=True,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    return "cloudmusic.exe" in completed.stdout.lower()


def _tap_virtual_key(virtual_key: int) -> None:
    user32 = ctypes.windll.user32
    user32.keybd_event(virtual_key, 0, 0, 0)
    user32.keybd_event(virtual_key, 0, KEYEVENTF_KEYUP, 0)


def _send_hotkey(keys: tuple[int, ...]) -> None:
    user32 = ctypes.windll.user32
    for key in keys:
        user32.keybd_event(key, 0, 0, 0)
    time.sleep(0.03)
    for key in reversed(keys):
        user32.keybd_event(key, 0, KEYEVENTF_KEYUP, 0)


def _search(query: str, kind: Literal["song", "playlist"], limit: int = 5) -> list[dict]:
    cleaned_query = query.strip()
    if not cleaned_query:
        raise ValueError("Search query cannot be empty")
    if not 1 <= limit <= 10:
        raise ValueError("limit must be between 1 and 10")

    search_type = 1 if kind == "song" else 1000
    params = urllib.parse.urlencode(
        {
            "s": cleaned_query,
            "type": search_type,
            "offset": 0,
            "total": "true",
            "limit": limit,
        }
    )
    request = urllib.request.Request(
        f"{SEARCH_ENDPOINT}?{params}",
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "Referer": "https://music.163.com/",
        },
    )

    with urllib.request.urlopen(request, timeout=10) as response:
        payload = json.load(response)

    if payload.get("code") != 200:
        raise RuntimeError(f"NetEase search returned code {payload.get('code')!r}")

    result = payload.get("result") or {}
    if kind == "song":
        items = result.get("songs") or []
        return [
            {
                "id": int(item["id"]),
                "name": item.get("name", ""),
                "artists": [artist.get("name", "") for artist in item.get("artists", [])],
                "album": (item.get("album") or {}).get("name", ""),
            }
            for item in items[:limit]
        ]

    items = result.get("playlists") or []
    return [
        {
            "id": int(item["id"]),
            "name": item.get("name", ""),
            "creator": (item.get("creator") or {}).get("nickname", ""),
            "track_count": item.get("trackCount"),
        }
        for item in items[:limit]
    ]


def _build_play_url(kind: Literal["song", "playlist"], item_id: int) -> str:
    if kind not in {"song", "playlist"}:
        raise ValueError(f"Unsupported item kind: {kind}")
    if int(item_id) <= 0:
        raise ValueError("item_id must be a positive integer")

    command = {"type": kind, "id": str(int(item_id)), "cmd": "play"}
    encoded = base64.b64encode(
        json.dumps(command, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).decode("ascii")
    return f"orpheus://{encoded}"


def _normalized_name(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    return re.sub(r"[\W_]+", "", normalized, flags=re.UNICODE)


def _select_song_match(matches: list[dict], title: str, artist: str = "") -> dict | None:
    if not matches:
        return None
    if not artist.strip():
        return matches[0]

    wanted_title = _normalized_name(title)
    wanted_artist = _normalized_name(artist)
    for match in matches:
        artists = match.get("artists") or []
        if (
            _normalized_name(match.get("name", "")) == wanted_title
            and len(artists) == 1
            and _normalized_name(artists[0]) == wanted_artist
        ):
            return match
    return None


def _open_play_url(play_url: str) -> None:
    if not play_url.startswith("orpheus://"):
        raise ValueError("Only the orpheus:// protocol is allowed")
    _require_cloudmusic_exe()
    os.startfile(play_url)


@mcp.tool()
def get_netease_status() -> dict:
    """Check the configured NetEase Cloud Music path and whether it is running."""
    executable = _cloudmusic_exe()
    return {
        "configured_path": str(executable),
        "executable_exists": executable.is_file(),
        "running": _is_cloudmusic_running(),
        "privacy": "No account data, cookies, history, or private files are read.",
    }


@mcp.tool()
def launch_netease_music() -> dict:
    """Open the local NetEase Cloud Music desktop client via Windows ShellExecute."""
    executable = _require_cloudmusic_exe()
    if not _is_cloudmusic_running():
        os.startfile(str(executable))
        return {"success": True, "message": "NetEase Cloud Music is opening."}
    return {"success": True, "message": "NetEase Cloud Music is already running."}


@mcp.tool()
def search_music(
    query: str,
    kind: Literal["song", "playlist"] = "song",
    limit: int = 5,
) -> dict:
    """Search NetEase Cloud Music over HTTPS without reading account credentials."""
    matches = _search(query=query, kind=kind, limit=limit)
    return {"query": query, "kind": kind, "count": len(matches), "matches": matches}


@mcp.tool()
def search_and_play(
    query: str,
    kind: Literal["song", "playlist"] = "song",
    artist: str = "",
) -> dict:
    """Search and play a song or playlist; artist can prevent playing a wrong cover version."""
    matches = _search(query=query, kind=kind, limit=10 if artist and kind == "song" else 5)
    if not matches:
        return {"success": False, "message": f"No matching {kind} found for: {query}"}

    selected = (
        _select_song_match(matches, title=query, artist=artist)
        if kind == "song"
        else matches[0]
    )
    if selected is None:
        return {
            "success": False,
            "message": (
                f"No unambiguous exact match for {query!r} by {artist!r}; "
                "nothing was played. Use search_music to inspect candidates."
            ),
            "candidates": matches,
        }

    _open_play_url(_build_play_url(kind=kind, item_id=int(selected["id"])))
    return {
        "success": True,
        "message": f"Playing the top {kind} match.",
        "selected": selected,
    }


@mcp.tool()
def play_netease_item(
    item_id: int,
    kind: Literal["song", "playlist"] = "song",
) -> dict:
    """Play a known NetEase song or playlist ID in the desktop client."""
    _open_play_url(_build_play_url(kind=kind, item_id=item_id))
    return {"success": True, "kind": kind, "id": item_id}


@mcp.tool()
def control_netease(
    action: Literal[
        "play_pause",
        "stop",
        "next",
        "previous",
        "volume_up",
        "volume_down",
        "mute",
    ],
    repeats: int = 1,
) -> dict:
    """Control playback with Windows media keys; repeats is limited to 1-10."""
    if action not in MEDIA_KEYS:
        raise ValueError(f"Unsupported action: {action}")
    if not 1 <= repeats <= 10:
        raise ValueError("repeats must be between 1 and 10")

    for index in range(repeats):
        _tap_virtual_key(MEDIA_KEYS[action])
        if index + 1 < repeats:
            time.sleep(0.08)
    return {"success": True, "action": action, "repeats": repeats}


@mcp.tool()
def send_netease_shortcut(
    action: Literal["like", "lyrics", "mini_mode"],
) -> dict:
    """Send a whitelisted NetEase global shortcut; the matching shortcut must be enabled in the app."""
    if action not in APP_SHORTCUTS:
        raise ValueError(f"Unsupported shortcut action: {action}")
    _send_hotkey(APP_SHORTCUTS[action])
    return {
        "success": True,
        "action": action,
        "note": "This requires the corresponding global shortcut to be enabled in NetEase Cloud Music.",
    }


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
