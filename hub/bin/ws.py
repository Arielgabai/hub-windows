"""ws — bascule entre les sujets et passe des consignes aux sessions (version Windows, sans tmux).

  ws new <sujet> <dossier> [titre]   crée la fiche du sujet dans le vault et sa ligne dans topics.md
  ws open <sujet> [dossier] [session|new] [--force]
                                     ouvre le sujet : VS Code (défaut) ou un onglet Windows Terminal,
                                     selon "terminal" dans hub.config.json ; reprend la session inscrite
                                     dans topics.md, ou en démarre une nouvelle
  ws ls                              liste les sujets : statut, dernière activité, consignes en attente
  ws send <sujet> <texte>            dépose une consigne dans la boîte du sujet ; la session la reçoit
                                     au prochain message tapé (ou à son démarrage)
  ws inbox [sujet]                   montre les consignes pas encore remises

Pourquoi une boîte plutôt qu'un collage dans le terminal : Windows n'a pas tmux, et taper à la place de
l'utilisateur dans un terminal VS Code n'est pas fiable. La consigne attend donc la session : il suffit
d'aller dans l'onglet du sujet et d'envoyer un message (« go » suffit).
Variable HUB_DRY_RUN=1 : affiche les commandes au lieu de les lancer (tests).
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import hubconf as hc  # noqa: E402

DRY = os.environ.get("HUB_DRY_RUN") == "1"


def die(msg: str, code: int = 1):
    print(f"ws : {msg}", file=sys.stderr)
    sys.exit(code)


def launch(cmd: list[str], cwd: str | None = None, env: dict | None = None):
    if DRY:
        print("[dry-run]", " ".join(cmd), f"(dans {cwd})" if cwd else "")
        return
    subprocess.Popen(cmd, cwd=cwd, env={**os.environ, **(env or {})},
                     creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0) if os.name == "nt" else 0)


def find(slug: str) -> dict:
    for t in hc.topics():
        if t["slug"] == slug:
            return t
    return {}


def cmd_new(args: list[str]):
    if len(args) < 2:
        die("usage : ws new <sujet> <dossier> [titre]")
    slug, dossier, titre = args[0], args[1], " ".join(args[2:]) or args[0]
    if find(slug):
        die(f"le sujet {slug} existe déjà dans topics.md")
    v = hc.vault()
    modele = v / "projets" / "_modele.md"
    fiche = v / "projets" / f"{slug}.md"
    if not fiche.exists():
        body = modele.read_text(encoding="utf-8") if modele.exists() else "# {slug} — {titre}\n"
        body = (body.replace("{slug}", slug).replace("{titre}", titre).replace("{dossier}", dossier)
                .replace("{date}", f"{hc.now():%d/%m}"))
        fiche.parent.mkdir(parents=True, exist_ok=True)
        fiche.write_text(body, encoding="utf-8")
    f = hc.topics_file()
    text = f.read_text(encoding="utf-8")
    row = f"| {slug} | 🔥 | {dossier} | (nouvelle) |"
    marker = "<!-- index:fin -->"
    text = text.replace(marker, row + "\n" + marker) if marker in text else text.rstrip("\n") + "\n" + row + "\n"
    f.write_text(text, encoding="utf-8")
    print(f"sujet {slug} créé : fiche {hc.short(fiche)}, ligne ajoutée à topics.md")


def recently_active(sid: str, seconds: int = 120) -> bool:
    t = hc.transcript(sid)
    return bool(t) and time.time() - t.stat().st_mtime < seconds


def remember_open(slug: str, dossier: str):
    f = hc.vault() / "inbox" / ".ouvertures.json"
    f.parent.mkdir(parents=True, exist_ok=True)
    try:
        items = json.loads(f.read_text(encoding="utf-8")) if f.exists() else []
    except ValueError:
        items = []
    items = [i for i in items if i.get("slug") != slug and time.time() - i.get("at", 0) < 3600]
    items.append({"slug": slug, "dossier": dossier, "at": time.time()})
    f.write_text(json.dumps(items, ensure_ascii=False, indent=1), encoding="utf-8")


def cmd_open(args: list[str]):
    force = "--force" in args
    args = [a for a in args if a != "--force"]
    if not args:
        die("usage : ws open <sujet> [dossier] [session|new]")
    slug = args[0]
    t = find(slug)
    dossier = args[1] if len(args) > 1 else t.get("dossier", "")
    sid = args[2] if len(args) > 2 else (t.get("session") or "new")
    if not dossier:
        die(f"dossier inconnu pour {slug} : ws open {slug} <dossier>")
    dossier = str(hc.expand(dossier))
    if not Path(dossier).is_dir() and not DRY:
        die(f"le dossier {dossier} n'existe pas")
    if sid != "new" and recently_active(sid) and not force:
        die(f"la session {sid[:8]} a écrit il y a moins de 2 min : elle est sans doute déjà ouverte. "
            "Ne pas la lancer deux fois (--force pour passer outre).", 2)
    remember_open(slug, dossier)
    claude = ["claude", "-r", sid] if sid != "new" else ["claude", "-n", slug]
    mode = hc.config()["terminal"]
    if mode == "wt" and (shutil.which("wt") or DRY):
        inner = f"set HUB_TOPIC={slug}&& {' '.join(claude)}"
        launch(["wt", "-w", "hub", "new-tab", "--title", slug, "-d", dossier, "cmd", "/k", inner])
        print(f"onglet « {slug} » ouvert dans Windows Terminal ({' '.join(claude)})")
    else:
        code = shutil.which("code") or "code"
        launch([code, "-n", dossier])
        print(f"fenêtre VS Code ouverte sur {hc.short(dossier)}.")
        if sid != "new":
            print(f"Dans son terminal : claude -r {sid}   (ou, dans le panneau Claude Code, reprends la conversation {sid[:8]})")
        else:
            print(f"Dans son terminal : claude -n {slug}   (ou ouvre le panneau Claude Code) ; "
                  "la nouvelle session sera inscrite dans topics.md à son démarrage (dans les 15 min).")


def cmd_ls(_args: list[str]):
    box = hc.vault() / "inbox"
    rows = [("sujet", "statut", "dernière activité", "consignes")]
    for t in hc.topics():
        tr = hc.transcript(t["session"])
        last = time.strftime("%d/%m %H:%M", time.localtime(tr.stat().st_mtime)) if tr else "—"
        pending = box / f"{t['slug']}.md"
        n = pending.read_text(encoding="utf-8").count("\n## ") if pending.exists() else 0
        rows.append((t["slug"], t["statut"][:28], last, str(n) if n else ""))
    w = [max(len(r[i]) for r in rows) for i in range(4)]
    for r in rows:
        print("  ".join(c.ljust(w[i]) for i, c in enumerate(r)).rstrip())


def cmd_send(args: list[str]):
    if len(args) < 2:
        die("usage : ws send <sujet> <texte>")
    slug, msg = args[0], " ".join(args[1:]).strip()
    if not find(slug):
        die(f"sujet inconnu : {slug} (voir ws ls)")
    box = hc.vault() / "inbox" / f"{slug}.md"
    box.parent.mkdir(parents=True, exist_ok=True)
    with box.open("a", encoding="utf-8") as fh:
        fh.write(f"\n## {hc.now():%d/%m %H:%M}\n{msg}\n")
    print(f"consigne déposée pour {slug} : elle part au prochain message tapé dans sa session.")


def cmd_inbox(args: list[str]):
    box = hc.vault() / "inbox"
    files = [box / f"{args[0]}.md"] if args else sorted(box.glob("*.md"))
    shown = False
    for f in files:
        if f.exists():
            shown = True
            print(f"=== {f.stem}\n{f.read_text(encoding='utf-8').strip()}\n")
    if not shown:
        print("aucune consigne en attente")


def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help", "help"):
        print(__doc__.split("\n\n")[0].split("\n", 1)[1])
        return
    cmd, args = sys.argv[1], sys.argv[2:]
    {"new": cmd_new, "open": cmd_open, "ls": cmd_ls, "send": cmd_send, "inbox": cmd_inbox}.get(
        cmd, lambda a: die(f"commande inconnue : {cmd} (ws help)"))(args)


if __name__ == "__main__":
    main()
