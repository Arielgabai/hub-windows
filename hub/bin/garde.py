"""garde — hook PreToolUse (réglages globaux) : les lois du hub, appliquées à chaque appel d'outil.

Lit l'appel d'outil en JSON sur stdin ; code 2 + message sur stderr = appel bloqué (le message est
renvoyé à Claude). Trois lois, réglées dans hub.config.json :
  1. pas de push sur une branche protégée ("protected_branches", défaut main/master), sauf dans les
     dépôts listés dans "push_ok_repos" (le vault, le hub…) ;
  2. pas d'écriture dans un fichier .env (.env, .env.*, *.env, .envrc ; .env.example/sample/template permis) ;
  3. pas de lecture du CONTENU des dossiers listés dans "protected_data" (motifs avec *, ex.
     "~/projets/*/data") ; les métadonnées restent permises (ls, dir, wc, du, stat, Get-ChildItem…) ;
     "protected_data_allow" rouvre des sous-dossiers.
Pour passer outre : l'utilisateur lance la commande lui-même (préfixe « ! » dans Claude Code).
Les chemins Windows (C:\\…, C:/…, /c/…) et POSIX sont reconnus.
"""
from __future__ import annotations

import fnmatch
import json
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import hubconf as hc  # noqa: E402

ENV_OK = {".env.example", ".env.sample", ".env.template"}
READ_VERBS = {
    # POSIX / Git Bash
    "cat", "head", "tail", "less", "more", "grep", "egrep", "fgrep", "rg", "awk", "gawk", "sed", "cut",
    "sort", "uniq", "column", "jq", "od", "xxd", "hexdump", "strings", "diff", "nl", "tac", "zcat", "bat",
    "vim", "vi", "nano", "duckdb", "sqlite3", "paste", "join", "tr", "iconv", "base64", "openssl", "scp",
    "curl", "csvlook", "csvcut", "xsv",
    # Windows : cmd et PowerShell
    "type", "findstr", "get-content", "gc", "select-string", "sls", "import-csv", "ipcsv",
    "notepad", "code", "excel", "start", "invoke-item", "ii",
}


def block(msg: str):
    sys.stderr.write(f"⛔ garde : {msg}\nSi c'est voulu, l'utilisateur lance la commande lui-même (préfixe « ! »).\n")
    sys.exit(2)


def norm(p: str, cwd: str = "") -> str:
    """Chemin absolu normalisé, séparateurs /, minuscules sous Windows, /c/x → c:/x."""
    p = os.path.expandvars(os.path.expanduser(p.strip().strip("'\"")))
    p = p.replace("\\", "/")
    m = re.match(r"^/([a-zA-Z])/(.*)", p)
    if m and (os.name == "nt" or re.match(r"^[a-zA-Z]:", cwd.replace("\\", "/"))):
        p = f"{m.group(1)}:/{m.group(2)}"
    absolute = p.startswith("/") or re.match(r"^[a-zA-Z]:/", p)
    if not absolute and cwd:
        p = cwd.replace("\\", "/").rstrip("/") + "/" + p
    drive = ""
    m = re.match(r"^([a-zA-Z]:)(/.*)$", p)
    if m:
        drive, p = m.group(1).lower(), m.group(2)
    parts = []
    for seg in p.split("/"):
        if seg in ("", "."):
            continue
        if seg == "..":
            parts and parts.pop()
        else:
            parts.append(seg)
    out = drive + "/" + "/".join(parts)
    return out.lower() if (drive or os.name == "nt") else out


def patterns(key: str) -> list[str]:
    return [norm(p).rstrip("/") for p in hc.config().get(key, [])]


def in_data(p: str, cwd: str) -> bool:
    if not p:
        return False
    path = norm(p, cwd)
    def under(pats):
        for pat in pats:
            depth = pat.count("/")
            prefix = "/".join(path.split("/")[: depth + 1])
            if path.count("/") >= depth and fnmatch.fnmatchcase(prefix, pat):
                return True
        return False
    return under(patterns("protected_data")) and not under(patterns("protected_data_allow"))


def is_env(path: str) -> bool:
    b = re.split(r"[\\/]", path.rstrip("/\\"))[-1].lower()
    if b in ENV_OK:
        return False
    return b == ".env" or b.startswith(".env.") or b.endswith(".env") or b == ".envrc"


def words(cmd: str) -> list[str]:
    # les \ des chemins Windows deviennent / : sinon le découpage POSIX les mange
    cmd = cmd.replace("\\", "/")
    try:
        return shlex.split(cmd, posix=True)
    except ValueError:
        return cmd.split()


def segments(cmd: str) -> list[str]:
    return [s for s in re.split(r"\|\||&&|[;|\n]", cmd) if s.strip()]


def git_out(*args: str) -> str:
    try:
        return subprocess.run(["git", *args], capture_output=True, text=True, timeout=5).stdout.strip()
    except Exception:  # noqa: BLE001
        return ""


def check_push(cmd: str, cwd: str):
    protected = set(hc.config()["protected_branches"])
    ok_repos = set(patterns("push_ok_repos"))
    for seg in segments(cmd):
        w = words(seg)
        if "git" not in [os.path.basename(x).lower().removesuffix(".exe") for x in w] or "push" not in w:
            continue
        repo_dir = cwd
        m = re.search(r"\b(?:cd|Set-Location|sl)\s+(\S+)", cmd, re.I)
        if m:
            repo_dir = m.group(1).strip("'\"")
        if "-C" in w and w.index("-C") + 1 < len(w):
            repo_dir = w[w.index("-C") + 1]
        repo_abs = norm(repo_dir, cwd)
        top = git_out("-C", repo_abs, "rev-parse", "--show-toplevel")
        top_n = norm(top) if top else repo_abs
        if top_n in ok_repos:
            continue
        args = w[w.index("push") + 1:]
        if any(a in ("--all", "--mirror") for a in args):
            block("push --all/--mirror interdit sur les dépôts de travail.")
        refs = [a for a in args if not a.startswith("-")][1:]  # après le remote
        names = "|".join(re.escape(b) for b in protected)
        if names and any(re.search(rf"(^|:|/)({names})$", r) for r in refs):
            block(f"push vers une branche protégée interdit ({top or repo_dir}). Pousser une branche et ouvrir une PR.")
        if not refs:
            br = git_out("-C", repo_abs, "branch", "--show-current")
            if br in protected:
                block(f"push depuis la branche protégée {br} interdit ({top or repo_dir}).")


def check_shell(cmd: str, cwd: str):
    check_push(cmd, cwd)
    # loi 2 : écriture dans un .env (redirection, tee, Set-Content, Out-File, Add-Content, cp, mv, sed -i)
    for m in re.finditer(r"(?:>>?|\btee\b(?:\s+-a)?)\s*([^\s;&|]+)", cmd):
        if is_env(m.group(1)):
            block(f"écriture dans {m.group(1)} interdite (fichier .env).")
    for m in re.finditer(r"\b(?:Set-Content|Add-Content|Out-File|sc|ac)\b[^;|\n]*?(?:-(?:Path|FilePath|LiteralPath)\s+)?([^\s;|]*\.env[\w.]*|[^\s;|]*\.envrc)", cmd, re.I):
        if is_env(m.group(1)):
            block(f"écriture dans {m.group(1)} interdite (fichier .env).")
    for seg in segments(cmd):
        w = words(seg)
        if not w:
            continue
        verb = os.path.basename(w[0]).lower().removesuffix(".exe")
        if verb in ("cp", "mv", "install", "truncate", "ln", "copy", "move", "copy-item", "move-item", "cpi", "mi") \
                or (verb == "sed" and any(a.startswith("-i") for a in w)):
            targets = [a for a in w[1:] if not a.startswith("-")]
            if targets and is_env(targets[-1]):
                block(f"écriture dans {targets[-1]} interdite (fichier .env).")
        # loi 3 : lecture du contenu des données protégées
        if verb == "sudo" and len(w) > 1:
            w, verb = w[1:], os.path.basename(w[1]).lower()
        touches = [a for a in w[1:] if not a.startswith("-") and in_data(a, cwd)]
        if not touches:
            continue
        if verb in READ_VERBS or (verb.startswith(("python", "py", "node", "pwsh", "powershell")) and
                                  any(x in w for x in ("-c", "-e", "-Command", "-command"))):
            block(f"lecture du contenu de données protégées interdite ({touches[0]}) : "
                  "métadonnées seulement (ls, dir, wc -l, du, stat, Get-ChildItem).")
    # code inline (python -c, heredoc, node -e, pwsh -Command…) qui cite un chemin protégé
    if re.search(r"\b(python[0-9.]*|py|node|ruby|perl|Rscript|pwsh|powershell)\b[^\n]*(\s-c\b|\s-e\b|\s-Command\b|<<)", cmd, re.I):
        for tok in re.findall(r"[\w.:~/\\+-]+", cmd):
            if ("/" in tok or "\\" in tok) and in_data(tok, cwd):
                block(f"lecture du contenu de données protégées interdite ({tok}) dans du code inline. "
                      "Si c'est du code qui CITE ce chemin sans le lire, écris-le avec l'outil Edit/Write.")
    # redirection d'entrée depuis la zone
    for m in re.finditer(r"<\s*([^\s;&|<]+)", cmd):
        if in_data(m.group(1), cwd):
            block(f"lecture du contenu de données protégées interdite ({m.group(1)}).")


def main():
    try:
        ev = json.load(sys.stdin)
    except ValueError:
        return
    tool, inp = ev.get("tool_name", ""), ev.get("tool_input") or {}
    cwd = ev.get("cwd") or os.getcwd()
    if tool in ("Bash", "PowerShell"):
        check_shell(inp.get("command", ""), cwd)
    elif tool in ("Edit", "Write", "MultiEdit", "NotebookEdit"):
        p = inp.get("file_path") or inp.get("notebook_path") or ""
        if p and is_env(p):
            block(f"écriture dans {p} interdite (fichier .env).")
    elif tool == "Read":
        p = inp.get("file_path", "")
        if p and in_data(p, cwd):
            block(f"lecture du contenu de données protégées interdite ({p}) : métadonnées seulement.")
    elif tool == "Grep":
        p = inp.get("path", "")
        if p and in_data(p.rstrip("/\\") + "/x", cwd):
            block(f"recherche dans le contenu de données protégées interdite ({p}).")


if __name__ == "__main__":
    main()
