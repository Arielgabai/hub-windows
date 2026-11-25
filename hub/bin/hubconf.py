"""hubconf — configuration et fonctions communes aux scripts du hub.

La configuration vit dans <hub>/hub.config.json. Le dossier du hub est celui qui contient bin/
(ou la variable d'environnement HUB_DIR) ; le vault est indiqué dans la configuration.
Bibliothèque standard uniquement : le hub doit tourner avec un Python nu (3.10+).
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime
from pathlib import Path

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover
    ZoneInfo = None  # type: ignore

HUB = Path(os.environ.get("HUB_DIR") or Path(__file__).resolve().parent.parent)
HOME = Path.home()
SID_RE = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
HARVEST_BEGIN, HARVEST_END = "<!-- harvest:début -->", "<!-- harvest:fin -->"

DEFAULTS = {
    "vault": "~/vault",
    "timezone": "Europe/Paris",
    "repos": [],
    "git_emails": [],
    "github": True,
    "terminal": "vscode",
    "max_fronts": 3,
    "push_ok_repos": [],
    "protected_branches": ["main", "master"],
    "protected_data": [],
    "protected_data_allow": [],
    "headless_allowed_tools": [
        "Read", "Edit", "Write", "Glob", "Grep",
        "Bash(git:*)", "Bash(gh:*)", "Bash(python:*)", "Bash(py:*)",
    ],
}


def expand(p: str | Path) -> Path:
    return Path(os.path.expandvars(os.path.expanduser(str(p))))


def config() -> dict:
    f = HUB / "hub.config.json"
    data = json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
    return {**DEFAULTS, **{k: v for k, v in data.items() if not k.startswith("_")}}


def vault() -> Path:
    return expand(os.environ.get("HUB_VAULT") or config()["vault"])


def tz():
    name = config()["timezone"]
    return ZoneInfo(name) if ZoneInfo and name else None


def now() -> datetime:
    return datetime.now(tz())


def topics_file() -> Path:
    return HUB / "topics.md"


def topics() -> list[dict]:
    """Lignes de l'index de topics.md : | slug | statut | dossier | session |."""
    out = []
    f = topics_file()
    if not f.exists():
        return out
    for line in f.read_text(encoding="utf-8").splitlines():
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 4 or not re.fullmatch(r"[a-z0-9][a-z0-9-]*", cells[0]):
            continue
        sids = SID_RE.findall(cells[3])
        out.append({"slug": cells[0], "statut": cells[1], "dossier": cells[2].strip("`"),
                    "session": sids[0] if sids else ""})
    return out


def topic_of_session(session_id: str) -> str:
    for t in topics():
        if t["session"] and t["session"] == session_id:
            return t["slug"]
    return ""


def set_topic_session(slug: str, session_id: str) -> bool:
    """Inscrit l'id de session dans la colonne « Session Claude » de la ligne du sujet."""
    f = topics_file()
    if not f.exists():
        return False
    lines = f.read_text(encoding="utf-8").splitlines(keepends=True)
    for i, line in enumerate(lines):
        cells = line.strip().strip("|").split("|")
        if len(cells) >= 4 and cells[0].strip() == slug:
            cells[3] = f" {session_id} "
            lines[i] = "|" + "|".join(cells) + "|" + ("\n" if line.endswith("\n") else "")
            f.write_text("".join(lines), encoding="utf-8")
            return True
    return False


def claude_projects() -> Path:
    return HOME / ".claude" / "projects"


def transcript(session_id: str) -> Path | None:
    if not session_id:
        return None
    hits = list(claude_projects().glob(f"*/{session_id}.jsonl"))
    return hits[0] if hits else None


def daily_path(day=None) -> Path:
    day = day or now().date()
    return vault() / "daily" / f"{day.isoformat()}.md"


def daily_note(text: str) -> str:
    """Ajoute « - HH:MM : texte » au daily du jour, hors du bloc harvest (juste avant lui)."""
    f = daily_path()
    f.parent.mkdir(parents=True, exist_ok=True)
    line = f"- {now():%H:%M} : {text}"
    body = f.read_text(encoding="utf-8") if f.exists() else f"# {now():%d/%m/%Y}\n"
    if HARVEST_BEGIN in body:
        i = body.index(HARVEST_BEGIN)
        head = body[:i].rstrip("\n")
        body = head + "\n" + line + "\n\n" + body[i:]
    else:
        body = body.rstrip("\n") + "\n" + line + "\n"
    f.write_text(body, encoding="utf-8")
    return line


def short(p: str | Path) -> str:
    s = str(p)
    for base in (str(HOME), str(HOME).replace("\\", "/")):
        if s.startswith(base):
            return "~" + s[len(base):].replace("\\", "/")
    return s.replace("\\", "/")
