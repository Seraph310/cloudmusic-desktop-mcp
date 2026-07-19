# CloudMusic Desktop MCP

A small, local-only MCP server that lets an AI control the official NetEase
Cloud Music desktop client on Windows.

It searches through NetEase's anonymous HTTPS endpoint, opens the selected song
or playlist in the installed desktop client through its `orpheus://` protocol,
and uses an allowlist of Windows media keys for playback controls. It does not
replace the official player or create a second playback process.

> This is an independent community project. It is not affiliated with,
> endorsed by, or supported by NetEase Cloud Music.

## Prerequisites

- Windows 10 or Windows 11.
- The official NetEase Cloud Music desktop client installed.
- A personal account signed in to the desktop client is recommended. The
  account determines which subscribed or paid tracks the client can play.
- Python 3.11 or newer.
- A local MCP host that can launch a stdio server, such as Codex or Claude
  Desktop.

The MCP never reads the signed-in account, browser cookies, credentials,
listening history, playlists, or local music library.

## Install

```powershell
git clone https://github.com/Seraph310/cloudmusic-desktop-mcp.git
cd cloudmusic-desktop-mcp
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
```

If the executable is installed outside a standard NetEase directory, set
`CLOUDMUSIC_EXE` to its full path in the MCP configuration.

### Codex configuration

Add the following to `%USERPROFILE%\.codex\config.toml`, replacing both paths:

```toml
[mcp_servers.cloudmusic]
command = 'C:\path\to\cloudmusic-desktop-mcp\.venv\Scripts\python.exe'
args = ['C:\path\to\cloudmusic-desktop-mcp\server.py']
startup_timeout_sec = 30

[mcp_servers.cloudmusic.env]
CLOUDMUSIC_EXE = 'C:\path\to\CloudMusic\cloudmusic.exe'
```

Restart the MCP host after changing its configuration.

## Tools

| Tool | Purpose |
| --- | --- |
| `get_netease_status` | Check the configured executable and running state |
| `launch_netease_music` | Start the official desktop client |
| `search_music` | Search songs or playlists without playing |
| `search_and_play` | Search and play an unambiguous match |
| `play_netease_item` | Play a known numeric song or playlist ID |
| `control_netease` | Play/pause, stop, skip, mute, or use Windows volume keys |
| `send_netease_shortcut` | Send an allowlisted like, lyrics, or mini-mode shortcut |

When an artist is supplied, `search_and_play` refuses to play unless it finds
one exact normalized title/artist match. This avoids silently choosing a cover
version. Optional app shortcuts must first be configured to the matching global
shortcuts inside NetEase Cloud Music.

## Tested environment

- Windows 11 64-bit, build `26200`.
- NetEase Cloud Music desktop client `3.1.24.204791`.
- Python `3.11.5`.

Other recent Windows client versions may work but have not yet been verified.

## Safety choices

- HTTPS-only search.
- No Selenium, ChromeDriver, cookies, account credentials, or remote debugging.
- No arbitrary commands, URLs, keyboard input, or shell execution.
- Does not kill or restart an existing Cloud Music process.
- Opens only allowlisted `orpheus://` commands built from numeric result IDs.

## Optional hardware companion

Pair this server with
[Halo PixelBar MCP](https://github.com/Seraph310/halo-pixelbar-mcp) so an MCP
host can coordinate music with the speaker's ambient light, pixel screen, and
independent hardware volume.

## Related project

[luuu-h/netease-music-mcp](https://github.com/luuu-h/netease-music-mcp)
inspired this project and offers a different, feature-rich approach using
`neteasecli`, `mpv`, synchronized lyrics, and a local web player. Choose that
project when you want an independent player UI; choose this one when you want
to keep using the official Windows desktop client without importing cookies
into the MCP.

## Test

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

## License

[MIT](LICENSE)
