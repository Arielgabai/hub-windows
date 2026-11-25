"""harvest — collecte les métadonnées du jour dans <vault>/daily/AAAA-MM-JJ.md.

`python harvest.py` pour aujourd'hui, `python harvest.py 2026-01-15` pour un autre jour.
Lancé par le rituel du matin ; peut l'être à la main ou toutes les heures (Planificateur de tâches).
MÉTADONNÉES SEULEMENT : titres, heures, compteurs, chemins, états. Jamais le contenu des messages, des
fichiers ni des données. Le bloc entre les marqueurs est réécrit à chaque passage ; le reste du daily
(notes à la main, retex) n'est pas touché.
Sources : transcripts Claude Code (~/.claude/projects), git des dépôts listés dans hub.config.json
("repos"), et GitHub par la CLI gh si elle est installée et "github" vaut true.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from datetime import date, datetime, time, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import hubconf as hc  # noqa: E402

EDIT_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}
TMP = str(Path(tempfile.gettempdir())).replace("\\", "/").lower()


def run(*cmd, cwd=None) -> str:
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, encoding="utf-8", timeout=60)
    if r.returncode:
        msg = (r.stderr or r.stdout).strip().splitlines()
        raise RuntimeError(msg[-1] if msg else f"code {r.returncode}")
    return r.stdout


def ts(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(hc.tz())


HOME_N = str(hc.HOME).replace("\\", "/").lower()


def is_tmp(p) -> bool:
    """Dossier temporaire (sessions jetables, scratchpad) ; un chemin sous HOME n'en est jamais un."""
    s = str(p or "").replace("\\", "/").lower()
    if s.startswith(HOME_N + "/"):
        return False
    return s.startswith(TMP) or s.startswith("/tmp/")


def sessions(day: date) -> list[str]:
    start = datetime.combine(day, time.min, hc.tz())
    end = start + timedelta(days=1)
    names = {t["session"]: t["slug"] for t in hc.topics() if t["session"]}
    rows = []
    for f in hc.claude_projects().glob("*/*.jsonl"):
        if datetime.fromtimestamp(f.stat().st_mtime, hc.tz()) < start:
            continue
        title = cwd = branch = first = last = None
        prompts, files = 0, []
        with f.open(encoding="utf-8", errors="replace") as fh:
            for line in fh:
                try:
                    d = json.loads(line)
                except ValueError:
                    continue
                if d.get("type") == "custom-title":
                    title = d.get("customTitle")
                t = d.get("timestamp")
                if not t or d.get("type") not in ("user", "assistant"):
                    continue
                when = ts(t)
                if not (start <= when < end):
                    continue
                first, last = first or when, when
                cwd, branch = d.get("cwd", cwd), d.get("gitBranch", branch)
                msg = d.get("message") or {}
                if (d["type"] == "user" and not d.get("isSidechain") and not d.get("isMeta")
                        and isinstance(msg.get("content"), str)):
                    prompts += 1
                if d["type"] == "assistant":
                    for c in msg.get("content") or []:
                        if isinstance(c, dict) and c.get("type") == "tool_use" and c.get("name") in EDIT_TOOLS:
                            inp = c.get("input") or {}
                            p = inp.get("file_path") or inp.get("notebook_path")
                            if p and p not in files and not is_tmp(p):
                                files.append(p)
        if not first or is_tmp(cwd):
            continue
        sid = f.stem
        name = names.get(sid) or title or sid[:8]
        row = (f"- **{name}** · {first:%H:%M}–{last:%H:%M} · {prompts} demande(s) · "
               f"`{Path(cwd).name if cwd else '?'}`"
               + (f" · branche `{branch}`" if branch and branch != "HEAD" else "")
               + f" · session `{sid[:8]}`")
        if files:
            row += "\n  - fichiers modifiés : " + ", ".join(f"`{hc.short(p)}`" for p in files[:10])
            row += f" (+{len(files) - 10})" if len(files) > 10 else ""
        rows.append((first, row))
    return [r for _, r in sorted(rows)] or ["- aucune"]


def commits(day: date) -> list[str]:
    cfg = hc.config()
    since = datetime.combine(day, time.min, hc.tz())
    until = since + timedelta(days=1)
    repos = [hc.expand(r) for r in cfg["repos"]] + [hc.HUB]
    emails = set(cfg["git_emails"])
    for repo in repos:
        try:
            emails.add(run("git", "config", "user.email", cwd=repo).strip())
        except Exception:  # noqa: BLE001
            pass
    emails.discard("")
    out = []
    for repo in repos:
        if not (repo / ".git").exists():
            continue
        try:
            args = ["git", "log", "--all", f"--since={since.isoformat()}", f"--until={until.isoformat()}",
                    "--date=iso-strict", "--format=%h|%ad|%D|%s"]
            args += [f"--author={e}" for e in sorted(emails)]
            log = run(*args, cwd=repo)
        except Exception as e:  # noqa: BLE001
            out.append(f"- `{repo.name}` : _indisponible ({e})_")
            continue
        for line in log.splitlines():
            h, when, refs, subj = line.split("|", 3)
            hm = datetime.fromisoformat(when).astimezone(hc.tz()).strftime("%H:%M")
            ref = next((r.strip() for r in refs.replace("HEAD -> ", "").split(",")
                        if r.strip() and "/" not in r and not r.strip().startswith("tag:")), "")
            out.append(f"- `{repo.name}` {hm} `{h}` {subj}" + (f" (`{ref}`)" if ref else ""))
    return out or ["- aucun"]


def ci_summary(checks) -> str:
    if not checks:
        return "pas de CI"
    st = {"ok": 0, "ko": 0, "en cours": 0}
    for c in checks:
        concl = (c.get("conclusion") or c.get("state") or "").upper()
        if concl in ("SUCCESS", "NEUTRAL", "SKIPPED"):
            st["ok"] += 1
        elif concl in ("FAILURE", "ERROR", "TIMED_OUT", "CANCELLED", "ACTION_REQUIRED"):
            st["ko"] += 1
        else:
            st["en cours"] += 1
    mark = "❌ " if st["ko"] else "⏳ " if st["en cours"] else "✅ "
    return mark + ", ".join(f"{v} {k}" for k, v in st.items() if v)


def gh_ok() -> bool:
    return bool(hc.config()["github"]) and shutil.which("gh") is not None


def prs(day: date) -> list[str]:
    if not gh_ok():
        return ["- _gh absent ou désactivé_"]
    out = []
    try:
        seen = set()
        for extra in (["--state=open"], [f"--updated=>={day.isoformat()}"]):
            for p in json.loads(run("gh", "search", "prs", "--author=@me", *extra, "--json", "number,repository")):
                seen.add((p["repository"]["nameWithOwner"], p["number"]))
        for repo, n in sorted(seen):
            v = json.loads(run("gh", "pr", "view", str(n), "-R", repo, "--json",
                               "title,state,isDraft,reviewDecision,statusCheckRollup,updatedAt"))
            state = {"MERGED": "✅ mergée", "CLOSED": "fermée"}.get(v["state"], "brouillon" if v["isDraft"] else "ouverte")
            review = {"APPROVED": "approuvée", "CHANGES_REQUESTED": "changements demandés",
                      "REVIEW_REQUIRED": "review attendue"}.get(v.get("reviewDecision") or "", "")
            out.append(f"- {repo}#{n} {v['title']} · {state}" + (f" · {review}" if review else "")
                       + (f" · CI {ci_summary(v.get('statusCheckRollup'))}" if v["state"] == "OPEN" else "")
                       + f" · maj {ts(v['updatedAt']):%d/%m %H:%M}")
    except Exception as e:  # noqa: BLE001
        out.append(f"- _indisponible ({e})_")
    return out or ["- aucune"]


def review_requests() -> list[str]:
    if not gh_ok():
        return ["- _gh absent ou désactivé_"]
    try:
        mine = json.loads(run("gh", "search", "prs", "--state=open", "--json", "number,title,repository,author",
                              "--", "user-review-requested:@me"))
    except Exception as e:  # noqa: BLE001
        return [f"- _indisponible ({e})_"]
    return [f"- {p['repository']['nameWithOwner']}#{p['number']} {p['title']} (de {p['author']['login']})"
            for p in mine] or ["- aucune"]


def block(day: date) -> str:
    return "\n".join([
        hc.HARVEST_BEGIN,
        f"## Collecte automatique (harvest, {hc.now():%d/%m %H:%M})",
        "_Métadonnées seulement, réécrit à chaque passage : ne pas éditer ce bloc._",
        "", "### Sessions Claude", *sessions(day),
        "", "### Commits", *commits(day),
        "", "### Mes PR (ouvertes ou mises à jour ce jour)", *prs(day),
        "", "### Reviews qu'on m'a demandées", *review_requests(),
        hc.HARVEST_END,
    ])


def write(day: date, text_block: str) -> Path:
    f = hc.daily_path(day)
    f.parent.mkdir(parents=True, exist_ok=True)
    text = f.read_text(encoding="utf-8") if f.exists() else f"# {day:%d/%m/%Y}\n"
    if hc.HARVEST_BEGIN in text and hc.HARVEST_END in text:
        text = text[:text.index(hc.HARVEST_BEGIN)] + text_block + text[text.index(hc.HARVEST_END) + len(hc.HARVEST_END):]
    else:
        text = text.rstrip("\n") + "\n\n" + text_block + "\n"
    f.write_text(text, encoding="utf-8")
    return f


def main():
    day = date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else hc.now().date()
    f = write(day, block(day))
    print(f"{hc.now():%Y-%m-%d %H:%M:%S} harvest → {hc.short(f)}")


if __name__ == "__main__":
    main()
