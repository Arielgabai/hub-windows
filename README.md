# Hub Claude Code pour Windows

Un « hub » pour piloter plusieurs sujets de travail avec Claude Code, sous Windows et VS Code :

- **une session Claude par sujet**, qui retrouve son contexte à chaque démarrage ;
- **un hub** (une session Claude dans le dossier `hub/`) qui tient ta todo, fait le point sur tous
  les sujets, te fait basculer de l'un à l'autre et passe des consignes aux autres sessions ;
- **un vault** : une mémoire en Markdown (fiches de sujet, journal du jour, pièges, décisions),
  injectée au démarrage de chaque session et rangée par `/retex` ;
- **un rituel** automatique : point du matin, retex du soir, rapport et tri du vendredi ;
- **un garde-fou** qui bloque certains gestes, quoi que décide l'agent (push sur main, écriture dans
  un `.env`, lecture de dossiers de données protégés).

Tout est en Python (bibliothèque standard seulement), sans tmux ni WSL.

## Prérequis

| Outil | Installation | Rôle |
|---|---|---|
| Python 3.10+ | `winget install Python.Python.3.12` | scripts du hub |
| Git for Windows | `winget install Git.Git` | vault versionné, commits (et Git Bash, utilisé par Claude Code) |
| Claude Code | voir la documentation d'Anthropic | les sessions |
| VS Code | `winget install Microsoft.VisualStudioCode` | une fenêtre par sujet (par défaut) |
| GitHub CLI (facultatif) | `winget install GitHub.cli` puis `gh auth login` | PR et CI dans le point du jour |
| Windows Terminal (facultatif) | déjà présent sur Windows 11 | un onglet par sujet au lieu de VS Code |

## Installation

```powershell
git clone <ce dépôt> hub-windows
cd hub-windows
powershell -ExecutionPolicy Bypass -File .\install.ps1
# options : --hub D:\hub --vault D:\vault --terminal wt --matin 09:00 --sans-taches --dry-run
```

L'installation n'écrase rien :
1. copie `hub/` vers `~/hub` et `vault/` vers `~/vault`, et initialise le vault en dépôt git ;
2. copie le skill `/retex` et le modèle `CLAUDE.md` (« Je suis ») dans `~/.claude`. Si tu as déjà un
   `CLAUDE.md`, le modèle est posé à côté (`CLAUDE.hub-modele.md`) ;
3. ajoute trois hooks à `~/.claude/settings.json`, après en avoir fait une copie
   (`settings.json.avant-hub`) :
   - `SessionStart` injecte le vault ;
   - `UserPromptSubmit` remet les consignes du hub ;
   - `PreToolUse` lance le garde-fou ;
4. crée `ws.cmd` (et `ws` pour Git Bash) dans `~/hub/bin` ;
5. crée les tâches planifiées `Hub\Matin`, `Hub\Soir`, `Hub\Vendredi` et `Hub\VaultSync`.

Ensuite :
1. Remplis `~/.claude/CLAUDE.md` (qui tu es, tes règles) et `~/vault/context.md`.
2. Relis `~/hub/hub.config.json` : dépôts suivis, e-mails git, dossiers de données protégés,
   terminal.
3. Ajoute `~/hub/bin` à ton PATH utilisateur (Paramètres > Variables d'environnement) pour taper
   `ws` partout.
4. Ouvre `~/hub` dans VS Code et lance Claude Code : c'est le hub.

## Au quotidien

| Tu veux… | Dans le hub, dis ou tape |
|---|---|
| savoir ce qui t'attend | `/point` (ou lis le brief du matin, que le hub te présente) |
| ouvrir un nouveau sujet | « nouveau sujet X dans D:\code\projet » → `ws new x D:\code\projet "titre"` |
| passer à un sujet | « on passe à X » → le hub rappelle où tu en étais et lance `ws open x` |
| donner une consigne à un sujet | `ws send x "relance les tests et dis-moi"` |
| ranger ce qu'une session a appris | `/retex` dans la session du sujet |
| le récap de la semaine | `/rapport-hebdo` (brouillon, jamais envoyé sans toi) |
| transformer les pièges répétés en règles | `/curate` |

### Basculer entre les sujets

Sans tmux, `ws open` ouvre le dossier du sujet dans une nouvelle fenêtre VS Code. Avec
`"terminal": "wt"`, il ouvre un onglet Windows Terminal nommé d'après le sujet. Il reprend la session
Claude inscrite dans `topics.md` :
- **Windows Terminal** : la session démarre toute seule (`claude -r <id>`).
- **VS Code** : `ws open` affiche la commande à lancer dans le terminal de la fenêtre
  (`claude -r <id>`). Tu peux aussi reprendre la conversation depuis le panneau Claude Code.
- **Nouveau sujet** : la première session qui démarre dans son dossier dans les 15 minutes est
  inscrite automatiquement dans `topics.md`.

`ws open` refuse de lancer une session qui a écrit il y a moins de 2 minutes, parce qu'elle est
sûrement déjà ouverte. Deux instances de la même session se marchent dessus.

### Passer une consigne à une session

Sous Linux, le hub peut taper dans le terminal d'une autre session (tmux). Ce n'est pas fiable sous
Windows, alors on passe par une **boîte** :
1. `ws send x "…"` écrit la consigne dans `vault/inbox/x.md` ;
2. le hook `UserPromptSubmit` de la session X la lui remet au prochain message que tu y tapes. Va dans
   la fenêtre du sujet et envoie « go ». Si la session n'est pas ouverte, elle la reçoit à son
   démarrage ;
3. la consigne remise est archivée dans `vault/inbox/lu/`.

`ws ls` montre les consignes encore en attente, et `ws inbox` leur texte.

### Le rituel

Les tâches tournent du lundi au vendredi (heures réglables à l'installation) :

| Tâche | Ce qu'elle fait |
|---|---|
| Matin (09:15) | `harvest` relève les sessions, commits et PR du jour dans le daily. Puis `/point` tourne en mode non interactif (`claude -p`) et écrit le brief dans `vault/brief/`. Le hub te le présente à son ouverture et complète avec les connecteurs (messagerie, tâches) si tu en as. |
| Soir (18:00) | dépose `/retex` dans la boîte de chaque sujet actif dans la journée |
| Vendredi (17:00) | `/rapport-hebdo` puis `/curate`, en brouillons dans `vault/brief/` |
| Toutes les heures | `vault_sync.py` commite le vault, et le pousse s'il a un dépôt distant **privé** |

Le mode non interactif n'a que les outils listés dans `headless_allowed_tools` : il lit, écrit dans le
vault et le hub, et consulte git et gh. Le garde-fou s'applique aussi à lui. Si l'ordinateur était
éteint à l'heure prévue, la tâche ne rattrape pas : lance-la à la main avec
`python ~/hub/bin/rituel.py matin`.

### Le garde-fou (`garde.py`)

Il passe sur chaque appel d'outil et bloque, avec un message renvoyé à l'agent :
1. un `git push` vers `main` / `master` (`protected_branches`), sauf dans les dépôts de
   `push_ok_repos` (le hub et le vault y sont ajoutés à l'installation) ;
2. une écriture dans un `.env` (`.env.example`, `.env.sample` et `.env.template` restent permis), par
   l'outil Write ou Edit, une redirection, `cp`, `Set-Content`… ;
3. la lecture du **contenu** des dossiers listés dans `protected_data` (motifs `*` permis, par exemple
   `~/code/*/data`). Les métadonnées restent permises : `ls`, `dir`, `wc -l`, `du`, `Get-ChildItem`.

Pour passer outre ponctuellement, lance la commande toi-même dans Claude Code avec le préfixe `!`.

## Structure

```
hub/                       → ~/hub (le dossier où tourne la session du hub)
  CLAUDE.md                consignes du hub
  topics.md                todo + index des sujets (slug | statut | dossier | session)
  hub.config.json          réglages
  .claude/skills/          /point, /curate, /rapport-hebdo
  bin/                     ws.py, harvest.py, rituel.py, vault_context.py, garde.py, vault_sync.py
vault/                     → ~/vault (la mémoire ; voir vault/README.md)
claude-user/               → ~/.claude (skill /retex, modèle CLAUDE.md « Je suis »)
install.ps1, install.py    installation
tests/                     python -m unittest discover -s tests
```

## Tests

```powershell
python -m unittest discover -s tests -v
```

Les tests tournent dans un dossier temporaire, avec un HOME, un hub et un vault factices.

## Limites connues

- Le hub ne voit pas l'écran des autres sessions. Il sait seulement quand elles ont écrit pour la
  dernière fois (transcripts dans `~/.claude/projects`), et peut relire la fin d'un transcript.
- Une consigne n'est remise qu'au prochain message tapé dans la session du sujet.
- Les tâches planifiées ne tournent que si la session Windows est ouverte (option par défaut de
  `schtasks`).
- Les rituels non interactifs n'ont pas les connecteurs (messagerie, gestion de tâches) : le point
  du matin les laisse au hub, qui les lit quand tu l'ouvres.
