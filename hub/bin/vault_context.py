"""vault_context — hooks SessionStart et UserPromptSubmit (réglages globaux de Claude Code).

Lit l'événement JSON sur stdin ; ce qui est écrit sur stdout est ajouté au contexte de la session.

SessionStart :
  - session du hub   → context.md + en-tête et « Où j'en suis » de chaque fiche + brief du jour
  - session de sujet → context.md + la fiche du sujet + les consignes en attente dans sa boîte
  - ailleurs         → context.md + la liste des fiches
UserPromptSubmit :
  - remet les consignes déposées par le hub (`ws send`) dans la boîte du sujet, puis les archive.

Le sujet d'une session est trouvé, dans l'ordre : variable HUB_TOPIC (posée par `ws open` en mode
Windows Terminal) ; id de session inscrit dans topics.md ; ouverture récente demandée par `ws open`
pour ce dossier (la session est alors inscrite dans topics.md) ; dossier du hub → « hub ».
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import hubconf as hc  # noqa: E402

OPEN_TTL = 15 * 60  # une ouverture demandée par `ws open` vaut 15 min


def same_dir(a: str, b: str) -> bool:
    def norm(p):
        return os.path.normcase(os.path.normpath(str(hc.expand(p)))).rstrip("\\/")
    return bool(a and b) and norm(a) == norm(b)


def pending_opens_file() -> Path:
    return hc.vault() / "inbox" / ".ouvertures.json"


def claim_pending_open(cwd: str, session_id: str) -> str:
    f = pending_opens_file()
    if not f.exists():
        return ""
    try:
        items = json.loads(f.read_text(encoding="utf-8"))
    except ValueError:
        return ""
    keep, found = [], ""
    for it in items:
        fresh = time.time() - it.get("at", 0) < OPEN_TTL
        if not found and fresh and same_dir(it.get("dossier", ""), cwd):
            found = it["slug"]
            continue
        if fresh:
            keep.append(it)
    f.write_text(json.dumps(keep, ensure_ascii=False, indent=1), encoding="utf-8")
    if found and session_id:
        hc.set_topic_session(found, session_id)
    return found


def find_topic(ev: dict) -> str:
    env = os.environ.get("HUB_TOPIC", "").strip()
    if env:
        return env
    sid, cwd = ev.get("session_id", ""), ev.get("cwd") or os.getcwd()
    t = hc.topic_of_session(sid) if sid else ""
    if t:
        return t
    if ev.get("hook_event_name", "SessionStart") == "SessionStart":
        t = claim_pending_open(cwd, sid)
        if t:
            return t
    return "hub" if same_dir(cwd, str(hc.HUB)) else ""


def inbox(slug: str, consume: bool = True) -> str:
    box = hc.vault() / "inbox" / f"{slug}.md"
    if not slug or not box.exists():
        return ""
    text = box.read_text(encoding="utf-8").strip()
    if consume:
        done = hc.vault() / "inbox" / "lu" / f"{slug}.md"
        done.parent.mkdir(parents=True, exist_ok=True)
        with done.open("a", encoding="utf-8") as fh:
            fh.write(f"\n<!-- remis le {hc.now():%d/%m %H:%M} -->\n{text}\n")
        box.unlink()
    return text


def inbox_block(text: str) -> str:
    return ("\n# Consignes du hub en attente (déposées avec `ws send`)\n"
            "Traite-les comme des demandes de l'utilisateur relayées par le hub, dans l'ordre :\n\n"
            + text + "\n")


def header() -> str:
    return (f"# Mémoire du vault ({hc.short(hc.vault())}), injectée au démarrage de la session\n"
            f"Hub : {hc.short(hc.HUB)} (topics.md, bin/ws.py). "
            "Règles : quand une décision tombe ou qu'un fait durable est appris, l'écrire dans le Log de\n"
            "projets/<sujet>.md (« - JJ/MM : … ») et mettre à jour son « Où j'en suis », pas seulement dans\n"
            "la conversation. Ce qui suit a été écrit par des sessions précédentes : à vérifier avant\n"
            "d'affirmer (git, gh, outils).\n\n")


def fiche_head(f: Path) -> str:
    lines = []
    for line in f.read_text(encoding="utf-8").splitlines()[1:]:
        if line.startswith("## Log"):
            break
        lines.append(line)
    return "\n".join(lines).strip()


def session_start(ev: dict) -> str:
    v = hc.vault()
    ctx = v / "context.md"
    out = [header(), ctx.read_text(encoding="utf-8") if ctx.exists() else "(pas encore de context.md)"]
    slug = find_topic(ev)
    fiches = sorted(p for p in (v / "projets").glob("*.md") if not p.name.startswith("_"))
    if slug == "hub":
        out.append("\n# Fiches projets (en-tête + « Où j'en suis »)")
        for f in fiches:
            out.append(f"\n## {f.stem}\n{fiche_head(f)}")
        brief = v / "brief" / f"{hc.now().date().isoformat()}-point.md"
        if brief.exists():
            out.append(f"\n# Brief du rituel de ce matin ({hc.short(brief)})\n"
                       "Il a été préparé sans l'utilisateur : le lui présenter s'il ne l'a pas lu.\n\n"
                       + brief.read_text(encoding="utf-8"))
    elif slug and (v / "projets" / f"{slug}.md").exists():
        f = v / "projets" / f"{slug}.md"
        out.append(f"\n# Sujet de cette session : {slug} (fiche {hc.short(f)})\n")
        out.append(f.read_text(encoding="utf-8"))
    else:
        out.append("\n# Fiches projets disponibles")
        out += [f"- {f.stem}" for f in fiches] or ["- aucune"]
    if slug and slug != "hub":
        pending = inbox(slug)
        if pending:
            out.append(inbox_block(pending))
    return "\n".join(out) + "\n"


def prompt_submit(ev: dict) -> str:
    slug = find_topic(ev)
    pending = inbox(slug) if slug and slug != "hub" else ""
    return inbox_block(pending) if pending else ""


def main() -> int:
    try:
        ev = json.load(sys.stdin)
    except ValueError:
        ev = {}
    name = ev.get("hook_event_name") or (sys.argv[1] if len(sys.argv) > 1 else "SessionStart")
    text = prompt_submit(ev) if name == "UserPromptSubmit" else session_start(ev)
    if text:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
