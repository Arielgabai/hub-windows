"""install — installe le hub sur ce poste (Windows ; marche aussi sous Linux/macOS sauf les tâches planifiées).

  python install.py [--hub DIR] [--vault DIR] [--terminal vscode|wt] [--sans-taches] [--dry-run]
                    [--matin 09:15] [--soir 18:00] [--vendredi 17:00]

Ce que fait l'installation (rien n'est écrasé : un fichier déjà présent est gardé) :
  1. copie hub/ vers --hub (défaut ~/hub) et vault/ vers --vault (défaut ~/vault), puis git init du vault ;
  2. copie le skill /retex et le modèle « Je suis » dans ~/.claude (si absents) ;
  3. ajoute à ~/.claude/settings.json les hooks SessionStart, UserPromptSubmit et PreToolUse
     (copie de sauvegarde settings.json.avant-hub) ;
  4. crée les raccourcis ws.cmd / ws (Git Bash) dans <hub>/bin ;
  5. sous Windows, crée les tâches planifiées Hub\\Matin, Hub\\Soir, Hub\\Vendredi, Hub\\VaultSync.
--dry-run : affiche ce qui serait fait, sans rien écrire.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent
HOME = Path.home()
DRY = False


def say(msg: str):
    print(("[dry-run] " if DRY else "") + msg)


def copy_tree(src: Path, dst: Path):
    for f in sorted(src.rglob("*")):
        if f.is_dir() or "__pycache__" in f.parts:
            continue
        target = dst / f.relative_to(src)
        if target.exists():
            continue
        say(f"copie {target}")
        if not DRY:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, target)


def posix(p: Path) -> str:
    return str(p).replace("\\", "/")


def hook_cmd(py: str, script: Path, *args: str) -> str:
    return " ".join([f'"{posix(Path(py))}"', f'"{posix(script)}"', *args])


def merge_hooks(settings: Path, py: str, hub: Path):
    data = json.loads(settings.read_text(encoding="utf-8")) if settings.exists() else {}
    hooks = data.setdefault("hooks", {})
    wanted = {
        "SessionStart": (None, hook_cmd(py, hub / "bin" / "vault_context.py", "SessionStart")),
        "UserPromptSubmit": (None, hook_cmd(py, hub / "bin" / "vault_context.py", "UserPromptSubmit")),
        "PreToolUse": ("Bash|PowerShell|Read|Edit|Write|MultiEdit|NotebookEdit|Grep",
                       hook_cmd(py, hub / "bin" / "garde.py")),
    }
    changed = False
    for event, (matcher, cmd) in wanted.items():
        groups = hooks.setdefault(event, [])
        present = any(h.get("command") == cmd for g in groups for h in g.get("hooks", []))
        if present:
            continue
        group = {"hooks": [{"type": "command", "command": cmd, "timeout": 10}]}
        if matcher:
            group["matcher"] = matcher
        groups.append(group)
        changed = True
        say(f"hook {event} → {cmd}")
    if changed and not DRY:
        if settings.exists():
            shutil.copy2(settings, settings.with_name("settings.json.avant-hub"))
        settings.parent.mkdir(parents=True, exist_ok=True)
        settings.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write(path: Path, text: str):
    say(f"écrit {path}")
    if not DRY:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n" if path.suffix != ".cmd" else "\r\n")


def tasks(py: str, hub: Path, matin: str, soir: str, vendredi: str):
    rituel, sync = hub / "bin" / "rituel.py", hub / "bin" / "vault_sync.py"
    jours = "MON,TUE,WED,THU,FRI"
    specs = [
        ("Hub\\Matin", ["/SC", "WEEKLY", "/D", jours, "/ST", matin], f'"{py}" "{rituel}" matin'),
        ("Hub\\Soir", ["/SC", "WEEKLY", "/D", jours, "/ST", soir], f'"{py}" "{rituel}" soir'),
        ("Hub\\Vendredi", ["/SC", "WEEKLY", "/D", "FRI", "/ST", vendredi], f'"{py}" "{rituel}" vendredi'),
        ("Hub\\VaultSync", ["/SC", "HOURLY", "/ST", "00:05"], f'"{py}" "{sync}"'),
    ]
    for name, sched, run in specs:
        cmd = ["schtasks", "/Create", "/F", "/TN", name, "/TR", run, *sched]
        say("tâche planifiée : " + " ".join(cmd))
        if not DRY:
            r = subprocess.run(cmd, capture_output=True, text=True)
            if r.returncode:
                print(f"  ⚠️ échec ({r.stderr.strip() or r.stdout.strip()})")


def main():
    global DRY
    ap = argparse.ArgumentParser(description="Installe le hub")
    ap.add_argument("--hub", default=str(HOME / "hub"))
    ap.add_argument("--vault", default=str(HOME / "vault"))
    ap.add_argument("--terminal", choices=["vscode", "wt"], default="vscode")
    ap.add_argument("--matin", default="09:15")
    ap.add_argument("--soir", default="18:00")
    ap.add_argument("--vendredi", default="17:00")
    ap.add_argument("--sans-taches", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    DRY = a.dry_run
    hub, vault = Path(a.hub).expanduser().resolve(), Path(a.vault).expanduser().resolve()
    py = sys.executable
    claude_dir = HOME / ".claude"

    copy_tree(SRC / "hub", hub)
    copy_tree(SRC / "vault", vault)
    cfg_path = hub / "hub.config.json"
    cfg = json.loads((SRC / "hub" / "hub.config.json").read_text(encoding="utf-8"))
    if cfg_path.exists() and not DRY:
        cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    cfg["vault"] = posix(vault)
    cfg["terminal"] = a.terminal
    cfg.setdefault("push_ok_repos", [])
    for p in (posix(hub), posix(vault)):
        if p not in cfg["push_ok_repos"]:
            cfg["push_ok_repos"].append(p)
    write(cfg_path, json.dumps(cfg, ensure_ascii=False, indent=2) + "\n")

    copy_tree(SRC / "claude-user" / "skills", claude_dir / "skills")
    user_md = claude_dir / "CLAUDE.md"
    modele = (SRC / "claude-user" / "CLAUDE.md").read_text(encoding="utf-8")
    write(user_md if not user_md.exists() else claude_dir / "CLAUDE.hub-modele.md", modele)
    merge_hooks(claude_dir / "settings.json", py, hub)

    write(hub / "bin" / "ws.cmd", f'@"{py}" "%~dp0ws.py" %*\n')
    write(hub / "bin" / "ws", f'#!/bin/sh\nexec "{posix(Path(py))}" "$(dirname "$0")/ws.py" "$@"\n')

    if not (vault / ".git").exists():
        say(f"git init {vault}")
        if not DRY:
            subprocess.run(["git", "init", "-q"], cwd=vault)
    if os.name == "nt" and not a.sans_taches:
        tasks(py, hub, a.matin, a.soir, a.vendredi)
    elif not a.sans_taches:
        say("tâches planifiées : seulement sous Windows (sous Linux/macOS, utiliser cron ou systemd)")

    print(f"""
Hub installé dans {hub}, vault dans {vault}.
Reste à faire (voir README) :
  1. remplir ~/.claude/CLAUDE.md (qui tu es, tes règles) et {vault / 'context.md'} ;
  2. relire {cfg_path} (dépôts suivis, e-mails git, données protégées) ;
  3. ajouter {hub / 'bin'} au PATH utilisateur pour taper `ws` partout ;
  4. ouvrir {hub} dans VS Code et lancer Claude Code : c'est le hub.""")


if __name__ == "__main__":
    main()
