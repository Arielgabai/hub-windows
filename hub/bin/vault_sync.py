"""vault_sync — commit, pull --rebase et push du vault s'il a un dépôt distant.

Lancé toutes les heures par la tâche « Hub\\VaultSync » ; peut l'être à la main. Sans dépôt distant,
se contente du commit local (l'historique reste utile pour revenir en arrière).
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import hubconf as hc  # noqa: E402


def git(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=hc.vault(), capture_output=True, text=True, check=check)


def main():
    v = hc.vault()
    if not (v / ".git").exists():
        print(f"{hc.short(v)} n'est pas un dépôt git : rien à synchroniser")
        return
    git("add", "-A")
    if git("diff", "--cached", "--quiet", check=False).returncode:
        git("commit", "-q", "-m", f"auto : {hc.now():%Y-%m-%d %H:%M}")
    if git("remote", check=False).stdout.strip():
        git("pull", "-q", "--rebase", "--autostash")
        git("push", "-q")
    print(f"{hc.now():%Y-%m-%d %H:%M:%S} vault synchronisé ({git('rev-parse', '--short', 'HEAD').stdout.strip()})")


if __name__ == "__main__":
    main()
