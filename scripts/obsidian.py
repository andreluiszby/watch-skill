#!/usr/bin/env python3
"""Save a watch note into an Obsidian vault chosen per request. Local addition, not upstream.

`--list` prints the vaults registered in Obsidian. Saving copies the note and its
frames into `<vault>/<channel>/<title>/` (or `<vault>/Watch/<title>/` without a
channel) and never overwrites an existing note.
Pure stdlib.
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import unicodedata
from pathlib import Path
from urllib.parse import quote

from runtime import configure_stdio

DEFAULT_FOLDER = 'Watch'
FRAME_LINK = re.compile(r'!\[\[([^\]|/\\]+\.(?:jpe?g|png))((?:\|[^\]]*)?)\]\]', re.I)


def registry_path() -> Path:
    system = platform.system()
    if system == 'Darwin':
        return Path.home() / 'Library' / 'Application Support' / 'obsidian' / 'obsidian.json'
    if system == 'Windows':
        return Path(os.environ.get('APPDATA', Path.home() / 'AppData' / 'Roaming')) / 'obsidian' / 'obsidian.json'
    return Path(os.environ.get('XDG_CONFIG_HOME', Path.home() / '.config')) / 'obsidian' / 'obsidian.json'


def list_vaults() -> list[dict]:
    """Vaults Obsidian knows about that still exist on disk, most recently used first."""
    try:
        data = json.loads(registry_path().read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return []
    vaults = []
    for entry in (data.get('vaults') or {}).values():
        path = Path(str(entry.get('path') or ''))
        if path.is_dir():
            vaults.append({'name': path.name, 'path': str(path), 'ts': entry.get('ts') or 0})
    vaults.sort(key=lambda v: v['ts'], reverse=True)
    return [{'name': v['name'], 'path': v['path']} for v in vaults]


def resolve_vault(choice: str) -> Path:
    """A registered vault name (case- and accent-insensitive) or the path of a folder containing `.obsidian`."""
    vaults = list_vaults()
    matches = [v for v in vaults if plain(v['name']) == plain(choice)]
    if len(matches) == 1:
        return Path(matches[0]['path'])
    if len(matches) > 1:
        paths = ', '.join(v['path'] for v in matches)
        raise SystemExit(f'Several vaults are named {choice!r}: {paths}. Pass the full path instead.')
    path = Path(choice).expanduser()
    if path.is_dir() and (path / '.obsidian').is_dir():
        return path.resolve()
    names = ', '.join(v['name'] for v in vaults) or 'none registered'
    raise SystemExit(f'No Obsidian vault matches {choice!r}. Available vaults: {names}.')


def safe_name(title: str) -> str:
    """A file name Obsidian accepts and can link to."""
    name = re.sub(r'[\\/:*?"<>|#^\[\]]', ' ', title)
    name = re.sub(r'\s+', ' ', name).strip(' .')
    return name[:100].rstrip(' .') or 'video'


def plain(name: str) -> str:
    """Comparison key that ignores case and accents."""
    text = unicodedata.normalize('NFKD', name.strip())
    return ''.join(c for c in text if not unicodedata.combining(c)).casefold()


def channel_folder(base: Path, channel: str) -> str:
    """Reuse the user's folder for this channel; otherwise name a new one after it."""
    key = plain(channel)
    existing = sorted(d.name for d in base.iterdir() if d.is_dir() and not d.name.startswith('.')) if base.is_dir() else []
    for name in existing:
        if plain(name) == key:
            return name
    # A folder such as "UGREEN" serves the channel "UGREEN: Decifrando a Ciência das Construções".
    prefixes = [n for n in existing if key.startswith(plain(n)) and not key[len(plain(n)):][:1].isalnum()]
    if prefixes:
        return max(prefixes, key=len)
    short = re.split(r'\s*[:|]\s*|\s+[-–—]\s+', channel.strip(), maxsplit=1)[0]
    return safe_name(short if len(short) >= 2 else channel)


def save(vault: Path, title: str, note_text: str, frames: list[Path], folder: str | None, channel: str | None) -> dict:
    if folder is None:
        folder = '' if channel else DEFAULT_FOLDER
    parts = [safe_name(p) for p in re.split(r'[\\/]+', folder) if p.strip()]
    base = vault.joinpath(*parts)
    if channel and channel.strip():
        base = base / channel_folder(base, channel)
    name = safe_name(title)
    target, n = base / name, 2
    while target.exists():
        target, n = base / f'{name} {n}', n + 1
    target.mkdir(parents=True)

    copied = {}
    for frame in frames:
        if not frame.is_file():
            raise SystemExit(f'Frame not found: {frame}')
        shutil.copy2(frame, target / frame.name)
        copied[frame.name] = (target / frame.name).relative_to(vault).as_posix()

    # Frame names repeat across videos, so embeds must carry the vault-relative path.
    def qualify(match):
        path = copied.get(match.group(1))
        return f'![[{path}{match.group(2)}]]' if path else match.group(0)

    note = target / f'{target.name}.md'
    note.write_text(FRAME_LINK.sub(qualify, note_text), encoding='utf-8', newline='\n')
    return {
        'vault': vault.name,
        'vault_path': str(vault),
        'note': note.relative_to(vault).as_posix(),
        'frames_copied': len(copied),
        'url': 'obsidian://open?path=' + quote(str(note), safe=''),
    }


def main() -> int:
    configure_stdio()
    parser = argparse.ArgumentParser(description='Save a watch note into an Obsidian vault.')
    parser.add_argument('--list', action='store_true', help='Print the registered vaults as JSON and exit')
    parser.add_argument('--vault', help='Registered vault name, or the path of a vault folder')
    parser.add_argument('--title', help='Note title; also names the folder holding the note and frames')
    parser.add_argument('--note', help='Markdown file with the note body, or - for stdin')
    parser.add_argument('--frame', action='append', default=[], type=Path, help='Frame to copy; repeatable')
    parser.add_argument('--channel', help='Channel or uploader; the note goes in that channel\'s folder')
    parser.add_argument('--folder', help=f'Folder inside the vault that holds the channel folders (default: vault root, or {DEFAULT_FOLDER} without a channel)')
    parser.add_argument('--open', action='store_true', help='Open the saved note in Obsidian')
    args = parser.parse_args()

    if args.list:
        print(json.dumps(list_vaults(), ensure_ascii=False, indent=2))
        return 0
    if not (args.vault and args.title and args.note):
        parser.error('--vault, --title, and --note are required to save')

    vault = resolve_vault(args.vault)
    text = sys.stdin.read() if args.note == '-' else Path(args.note).read_text(encoding='utf-8')
    result = save(vault, args.title, text, args.frame, args.folder, args.channel)
    if args.open:
        opener = {'Darwin': ['open'], 'Windows': ['cmd', '/c', 'start', '']}.get(platform.system(), ['xdg-open'])
        try:
            subprocess.run([*opener, result['url']], check=False, capture_output=True)
        except OSError:
            pass
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
