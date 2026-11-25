"""rituel — les rendez-vous automatiques du hub, lancés par le Planificateur de tâches Windows
(tâches « Hub\\Matin », « Hub\\Soir », « Hub\\Vendredi » créées par install.py, jours ouvrés).
À la main : python rituel.py <moment>.

  matin     harvest, puis /point en mode non interactif (claude -p) dans le dossier du hub ; le brief
            est écrit dans <vault>/brief/AAAA-MM-JJ-point.md et présenté à l'ouverture du hub
  soir      dépose « /retex » dans la boîte de chaque sujet dont la session a travaillé aujourd'hui ;
            la session le fera au prochain message (ou à sa prochaine ouverture)
  vendredi  /rapport-hebdo puis /curate en mode non interactif ; brouillons dans <vault>/brief/
            (rien n'est envoyé à personne)
  note <texte>  ajoute une ligne au daily (hors du bloc harvest)

Le mode non interactif n'a que les outils listés dans "headless_allowed_tools" (hub.config.json) :
pas de connecteurs qui écrivent, pas de push. Chaque passage est noté dans le daily.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import harvest  # noqa: E402
import hubconf as hc  # noqa: E402


def headless(prompt: str, out_name: str, timeout: int = 1800) -> bool:
    claude = shutil.which("claude")
    out = hc.vault() / "brief" / f"{hc.now().date().isoformat()}-{out_name}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    if not claude:
        hc.daily_note(f"rituel : claude introuvable dans le PATH, {prompt} non lancé")
        return False
    cmd = [claude, "-p", prompt, "--allowedTools", *hc.config()["headless_allowed_tools"]]
    if os.environ.get("HUB_DRY_RUN") == "1":
        print("[dry-run]", " ".join(cmd))
        return True
    try:
        r = subprocess.run(cmd, cwd=hc.HUB, capture_output=True, text=True, encoding="utf-8",
                           timeout=timeout, env={**os.environ, "HUB_TOPIC": "hub"})
    except subprocess.TimeoutExpired:
        hc.daily_note(f"rituel : {prompt} arrêté au bout de {timeout // 60} min")
        return False
    body = r.stdout.strip() or f"_(sortie vide, code {r.returncode})_\n\n{r.stderr.strip()[-2000:]}"
    out.write_text(f"# {prompt} — {hc.now():%d/%m %H:%M} (rituel, sans l'utilisateur)\n\n{body}\n", encoding="utf-8")
    hc.daily_note(f"rituel : {prompt} → {hc.short(out)}" + ("" if r.returncode == 0 else f" (code {r.returncode})"))
    return r.returncode == 0


def active_topics() -> list[str]:
    today = hc.now().date()
    out = []
    for t in hc.topics():
        tr = hc.transcript(t["session"])
        if tr and t["slug"] != "hub":
            from datetime import datetime
            if datetime.fromtimestamp(tr.stat().st_mtime, hc.tz()).date() == today:
                out.append(t["slug"])
    return out


def soir():
    n = 0
    for slug in active_topics():
        box = hc.vault() / "inbox" / f"{slug}.md"
        if box.exists() and "/retex" in box.read_text(encoding="utf-8"):
            continue
        box.parent.mkdir(parents=True, exist_ok=True)
        with box.open("a", encoding="utf-8") as fh:
            fh.write(f"\n## {hc.now():%d/%m %H:%M} (rituel du soir)\n/retex\n")
        n += 1
    hc.daily_note(f"rituel soir : /retex déposé dans {n} boîte(s) de sujet")


def main():
    moment = sys.argv[1] if len(sys.argv) > 1 else ""
    if moment == "matin":
        harvest.write(hc.now().date(), harvest.block(hc.now().date()))
        headless("/point", "point")
    elif moment == "soir":
        soir()
    elif moment == "vendredi":
        if headless("/rapport-hebdo", "rapport-hebdo"):
            headless("/curate", "curate")
    elif moment == "note":
        print(hc.daily_note("rituel " + " ".join(sys.argv[2:])))
    else:
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
