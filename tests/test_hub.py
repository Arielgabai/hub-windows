"""Tests du hub : python -m unittest discover -s tests -v (depuis la racine du dépôt).

Chaque test travaille dans un dossier temporaire (HOME, hub et vault factices) : rien n'est écrit
dans ton vrai ~/.claude ni dans ton vrai vault.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BIN = REPO / "hub" / "bin"
PY = sys.executable
SID = "11111111-2222-3333-4444-555555555555"
SID2 = "66666666-7777-8888-9999-000000000000"


class Sandbox(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="hubtest-"))
        self.home = self.tmp / "home"
        self.hub = self.home / "hub"
        self.vault = self.home / "vault"
        self.work = self.home / "projets" / "alpha"
        self.work.mkdir(parents=True)
        shutil.copytree(REPO / "hub", self.hub)
        shutil.copytree(REPO / "vault", self.vault)
        cfg = json.loads((self.hub / "hub.config.json").read_text(encoding="utf-8"))
        cfg.update({"vault": str(self.vault), "github": False,
                    "protected_data": [str(self.home / "projets" / "*" / "data")],
                    "protected_data_allow": [str(self.home / "projets" / "*" / "data" / "inventaire")],
                    "push_ok_repos": [str(self.hub)]})
        (self.hub / "hub.config.json").write_text(json.dumps(cfg), encoding="utf-8")
        self.env = {**os.environ, "HOME": str(self.home), "USERPROFILE": str(self.home),
                    "HUB_DIR": str(self.hub), "HUB_DRY_RUN": "1", "PYTHONIOENCODING": "utf-8"}
        self.env.pop("HUB_TOPIC", None)
        self.env.pop("HUB_VAULT", None)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_py(self, script, *args, stdin=None, env=None, cwd=None):
        return subprocess.run([PY, str(BIN / script), *args], input=stdin, capture_output=True, text=True,
                              encoding="utf-8", env={**self.env, **(env or {})}, cwd=cwd or self.home)

    def ws(self, *args, **kw):
        return self.run_py("ws.py", *args, **kw)

    def topics(self):
        return (self.hub / "topics.md").read_text(encoding="utf-8")

    def fake_transcript(self, sid, cwd, when=None, prompts=("bonjour",), edits=()):
        d = self.home / ".claude" / "projects" / "proj"
        d.mkdir(parents=True, exist_ok=True)
        when = when or datetime.now(timezone.utc)
        t = when.isoformat().replace("+00:00", "Z")
        lines = [{"type": "custom-title", "customTitle": "titre-session"}]
        for p in prompts:
            lines.append({"type": "user", "timestamp": t, "cwd": str(cwd), "gitBranch": "feature-x",
                          "message": {"role": "user", "content": p}})
        for e in edits:
            lines.append({"type": "assistant", "timestamp": t, "cwd": str(cwd),
                          "message": {"content": [{"type": "tool_use", "name": "Edit", "input": {"file_path": e}}]}})
        f = d / f"{sid}.jsonl"
        f.write_text("\n".join(json.dumps(x) for x in lines) + "\n", encoding="utf-8")
        return f


class TestWs(Sandbox):
    def test_new_cree_fiche_et_ligne(self):
        r = self.ws("new", "alpha", str(self.work), "Sujet alpha")
        self.assertEqual(r.returncode, 0, r.stderr)
        fiche = (self.vault / "projets" / "alpha.md").read_text(encoding="utf-8")
        self.assertIn("# alpha — Sujet alpha", fiche)
        self.assertIn(f"| alpha | 🔥 | {self.work} | (nouvelle) |", self.topics())
        self.assertLess(self.topics().index("| alpha |"), self.topics().index("<!-- index:fin -->"))
        self.assertEqual(self.ws("new", "alpha", str(self.work)).returncode, 1)  # doublon refusé

    def test_send_inbox_ls(self):
        self.ws("new", "alpha", str(self.work))
        self.assertEqual(self.ws("send", "inconnu", "x").returncode, 1)
        self.assertEqual(self.ws("send", "alpha", "fais", "le", "test").returncode, 0)
        self.ws("send", "alpha", "deuxième")
        box = (self.vault / "inbox" / "alpha.md").read_text(encoding="utf-8")
        self.assertIn("fais le test", box)
        self.assertIn("deuxième", box)
        ls = self.ws("ls").stdout
        self.assertRegex(ls, r"alpha\s+🔥\s+—\s+2")

    def test_open_vscode_et_wt(self):
        self.ws("new", "alpha", str(self.work))
        r = self.ws("open", "alpha")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("[dry-run]", r.stdout)
        self.assertIn("-n " + str(self.work), r.stdout)
        opens = json.loads((self.vault / "inbox" / ".ouvertures.json").read_text(encoding="utf-8"))
        self.assertEqual(opens[0]["slug"], "alpha")
        cfg = json.loads((self.hub / "hub.config.json").read_text(encoding="utf-8"))
        cfg["terminal"] = "wt"
        (self.hub / "hub.config.json").write_text(json.dumps(cfg), encoding="utf-8")
        r = self.ws("open", "alpha", str(self.work), SID)
        self.assertIn("set HUB_TOPIC=alpha&& claude -r " + SID, r.stdout)

    def test_open_refuse_session_deja_active(self):
        self.ws("new", "alpha", str(self.work))
        self.fake_transcript(SID, self.work)
        r = self.ws("open", "alpha", str(self.work), SID)
        self.assertEqual(r.returncode, 2)
        self.assertEqual(self.ws("open", "alpha", str(self.work), SID, "--force").returncode, 0)


class TestVaultContext(Sandbox):
    def hook(self, event, sid, cwd, env=None):
        ev = {"hook_event_name": event, "session_id": sid, "cwd": str(cwd)}
        return self.run_py("vault_context.py", stdin=json.dumps(ev), env=env)

    def test_hub_voit_les_fiches_et_le_brief(self):
        self.ws("new", "alpha", str(self.work), "Sujet alpha")
        day = datetime.now().date().isoformat()
        (self.vault / "brief" / f"{day}-point.md").write_text("BRIEF-DU-JOUR", encoding="utf-8")
        out = self.hook("SessionStart", SID, self.hub).stdout
        self.assertIn("# Contexte", out)
        self.assertIn("## alpha", out)
        self.assertIn("BRIEF-DU-JOUR", out)
        self.assertNotIn("_modele", out)

    def test_nouvelle_session_reclamee_puis_consignes(self):
        self.ws("new", "alpha", str(self.work), "Sujet alpha")
        self.ws("open", "alpha")
        self.ws("send", "alpha", "CONSIGNE-1")
        out = self.hook("SessionStart", SID, self.work).stdout
        self.assertIn("Sujet de cette session : alpha", out)
        self.assertIn("CONSIGNE-1", out)
        self.assertIn(f"| alpha | 🔥 | {self.work} | {SID} |", self.topics())
        self.assertFalse((self.vault / "inbox" / "alpha.md").exists())
        self.assertIn("CONSIGNE-1", (self.vault / "inbox" / "lu" / "alpha.md").read_text(encoding="utf-8"))
        # consigne suivante : remise au prochain message tapé
        self.ws("send", "alpha", "CONSIGNE-2")
        out = self.hook("UserPromptSubmit", SID, self.work).stdout
        self.assertIn("CONSIGNE-2", out)
        self.assertEqual(self.hook("UserPromptSubmit", SID, self.work).stdout, "")

    def test_session_inconnue_ne_prend_rien(self):
        self.ws("new", "alpha", str(self.work))
        self.ws("send", "alpha", "CONSIGNE")
        out = self.hook("SessionStart", SID2, self.home).stdout
        self.assertIn("Fiches projets disponibles", out)
        self.assertNotIn("CONSIGNE", out)
        self.assertEqual(self.hook("UserPromptSubmit", SID2, self.home).stdout, "")

    def test_variable_hub_topic(self):
        self.ws("new", "alpha", str(self.work))
        out = self.hook("SessionStart", SID2, self.home, env={"HUB_TOPIC": "alpha"}).stdout
        self.assertIn("Sujet de cette session : alpha", out)


class TestGarde(Sandbox):
    def garde(self, tool, inp, cwd):
        r = self.run_py("garde.py", stdin=json.dumps({"tool_name": tool, "tool_input": inp, "cwd": str(cwd)}))
        return "BLOQUE" if r.returncode == 2 else "PASSE" if r.returncode == 0 else f"ERREUR {r.stderr}"

    def git_repo(self, path, branch):
        path.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "init", "-q", "-b", branch], cwd=path, check=True)
        return path

    def test_lois(self):
        data = self.work / "data" / "client1" / "export.csv"
        data.parent.mkdir(parents=True)
        main_repo = self.git_repo(self.home / "depot-main", "main")
        feat_repo = self.git_repo(self.home / "depot-feat", "feature")
        hub_repo = self.git_repo(self.hub, "main")
        cases = [
            ("BLOQUE", "Bash", {"command": "git push origin main"}, feat_repo),
            ("BLOQUE", "Bash", {"command": "git push origin HEAD:master"}, feat_repo),
            ("BLOQUE", "Bash", {"command": "git push"}, main_repo),
            ("BLOQUE", "Bash", {"command": f"git -C {main_repo} push"}, feat_repo),
            ("BLOQUE", "Bash", {"command": "git push --all origin"}, feat_repo),
            ("PASSE", "Bash", {"command": "git push -u origin feature"}, feat_repo),
            ("PASSE", "Bash", {"command": "git push origin main"}, hub_repo),
            ("PASSE", "Bash", {"command": "git log main"}, main_repo),
            ("BLOQUE", "Write", {"file_path": str(self.work / ".env")}, self.work),
            ("BLOQUE", "Edit", {"file_path": "C:\\Users\\moi\\app\\prod.env"}, self.work),
            ("BLOQUE", "Bash", {"command": "echo A=1 >> .env"}, self.work),
            ("BLOQUE", "Bash", {"command": "cp .env.example .env"}, self.work),
            ("BLOQUE", "PowerShell", {"command": "Set-Content -Path .env -Value 'A=1'"}, self.work),
            ("PASSE", "Write", {"file_path": str(self.work / ".env.example")}, self.work),
            ("PASSE", "Bash", {"command": "grep -c A .env"}, self.work),
            ("BLOQUE", "Read", {"file_path": str(data)}, self.home),
            ("BLOQUE", "Bash", {"command": "head -5 data/client1/export.csv"}, self.work),
            ("BLOQUE", "Bash", {"command": f"cat {data} | wc -l"}, self.home),
            ("BLOQUE", "PowerShell", {"command": "Get-Content data\\client1\\export.csv -TotalCount 3"}, self.work),
            ("BLOQUE", "Bash", {"command": "python -c \"print(open('data/client1/export.csv').read())\""}, self.work),
            ("BLOQUE", "Grep", {"pattern": "x", "path": str(self.work / "data")}, self.work),
            ("PASSE", "Bash", {"command": "wc -l data/client1/export.csv"}, self.work),
            ("PASSE", "Bash", {"command": "ls -la data/client1"}, self.work),
            ("PASSE", "PowerShell", {"command": "Get-ChildItem data\\client1"}, self.work),
            ("PASSE", "Read", {"file_path": str(self.work / "data" / "inventaire" / "liste.csv")}, self.work),
            ("PASSE", "Read", {"file_path": str(self.work / "README.md")}, self.work),
        ]
        bad = []
        for exp, tool, inp, cwd in cases:
            got = self.garde(tool, inp, cwd)
            if got != exp:
                bad.append(f"{exp} attendu, {got} obtenu : {tool} {inp} (cwd {cwd.name})")
        self.assertEqual(bad, [], "\n".join(bad))

    def test_chemins_windows(self):
        sys.path.insert(0, str(BIN))
        import garde
        self.assertEqual(garde.norm("/c/Users/Moi/x", "C:\\Users"), "c:/users/moi/x")
        self.assertEqual(garde.norm("..\\b\\c.txt", "C:\\a\\d"), "c:/a/b/c.txt")
        self.assertTrue(garde.is_env("C:\\app\\.env"))
        self.assertFalse(garde.is_env("C:\\app\\.env.example"))


class TestHarvestRituel(Sandbox):
    def test_harvest_ecrit_le_bloc_sans_toucher_le_reste(self):
        self.ws("new", "alpha", str(self.work))
        self.ws("open", "alpha")
        self.fake_transcript(SID, self.work, prompts=("a", "b"), edits=(str(self.work / "x.py"),))
        ev = {"hook_event_name": "SessionStart", "session_id": SID, "cwd": str(self.work)}
        self.run_py("vault_context.py", stdin=json.dumps(ev))  # inscrit SID pour alpha
        day = datetime.now().date().isoformat()
        daily = self.vault / "daily" / f"{day}.md"
        daily.parent.mkdir(parents=True, exist_ok=True)
        daily.write_text("# jour\n- 09:00 : note à la main\n", encoding="utf-8")
        for _ in range(2):  # deux passages : le bloc est remplacé, pas dupliqué
            r = self.run_py("harvest.py")
            self.assertEqual(r.returncode, 0, r.stderr)
        text = daily.read_text(encoding="utf-8")
        self.assertIn("- 09:00 : note à la main", text)
        self.assertEqual(text.count("<!-- harvest:début -->"), 1)
        self.assertIn("**alpha**", text)
        self.assertIn("2 demande(s)", text)
        self.assertIn("branche `feature-x`", text)
        self.assertIn("x.py", text)
        self.assertIn("gh absent ou désactivé", text)

    def test_rituel_note_soir_matin(self):
        self.ws("new", "alpha", str(self.work))
        self.ws("open", "alpha")
        self.fake_transcript(SID, self.work)
        ev = {"hook_event_name": "SessionStart", "session_id": SID, "cwd": str(self.work)}
        self.run_py("vault_context.py", stdin=json.dumps(ev))
        self.run_py("harvest.py")
        r = self.run_py("rituel.py", "note", "essai")
        self.assertIn("rituel essai", r.stdout)
        r = self.run_py("rituel.py", "soir")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("/retex", (self.vault / "inbox" / "alpha.md").read_text(encoding="utf-8"))
        self.run_py("rituel.py", "soir")  # pas de doublon
        self.assertEqual((self.vault / "inbox" / "alpha.md").read_text(encoding="utf-8").count("/retex"), 1)
        daily = (self.vault / "daily" / f"{datetime.now().date().isoformat()}.md").read_text(encoding="utf-8")
        self.assertLess(daily.index("rituel essai"), daily.index("<!-- harvest:début -->"))
        self.assertIn("/retex déposé dans 1 boîte(s)", daily)
        r = self.run_py("rituel.py", "matin", env={"PATH": os.environ["PATH"]})
        self.assertEqual(r.returncode, 0, r.stderr)


class TestInstall(unittest.TestCase):
    def test_installation_complete_puis_relance_idempotente(self):
        tmp = Path(tempfile.mkdtemp(prefix="hubinst-"))
        try:
            home = tmp / "home"
            home.mkdir()
            (home / ".claude").mkdir()
            (home / ".claude" / "settings.json").write_text(json.dumps({"theme": "dark"}), encoding="utf-8")
            env = {**os.environ, "HOME": str(home), "USERPROFILE": str(home)}
            for _ in range(2):
                r = subprocess.run([PY, str(REPO / "install.py"), "--sans-taches"], capture_output=True,
                                   text=True, encoding="utf-8", env=env)
                self.assertEqual(r.returncode, 0, r.stderr)
            s = json.loads((home / ".claude" / "settings.json").read_text(encoding="utf-8"))
            self.assertEqual(s["theme"], "dark")
            for ev in ("SessionStart", "UserPromptSubmit", "PreToolUse"):
                self.assertEqual(len(s["hooks"][ev]), 1, ev)  # pas de doublon à la 2e installation
            self.assertTrue((home / ".claude" / "settings.json.avant-hub").exists())
            self.assertTrue((home / ".claude" / "skills" / "retex" / "SKILL.md").exists())
            self.assertTrue((home / ".claude" / "CLAUDE.md").exists())
            cfg = json.loads((home / "hub" / "hub.config.json").read_text(encoding="utf-8"))
            self.assertEqual(cfg["vault"], str(home / "vault").replace("\\", "/"))
            self.assertTrue((home / "vault" / ".git").exists())
            self.assertTrue((home / "hub" / "bin" / "ws.cmd").exists())
            # le hook installé fonctionne
            cmd = s["hooks"]["SessionStart"][0]["hooks"][0]["command"]
            r = subprocess.run(cmd, shell=True, input=json.dumps({"session_id": SID, "cwd": str(home / "hub")}),
                               capture_output=True, text=True, encoding="utf-8", env=env)
            self.assertIn("# Contexte", r.stdout)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
