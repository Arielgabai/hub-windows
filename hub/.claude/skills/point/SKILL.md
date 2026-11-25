---
name: point
description: Faire le point sur tous les sujets de l'utilisateur (sessions, git/PR/CI, outils connectés) et remettre la todo et les fiches du vault à jour. À utiliser quand l'utilisateur dit « fais le point », « on en est où », « point du matin / du soir », ou tape /point.
---

# /point — le point sur tous les sujets

Objectif : en une lecture, l'utilisateur sait **ce qui a bougé depuis le dernier point** et **ce qui
l'attend**, et `topics.md` + les fiches du vault sont à jour. Ne rien inventer : chaque affirmation
vient d'une source lue pendant ce point.

Le chemin du vault est la clé `vault` de `hub.config.json`.

## 1. Rafraîchir et lire la base
1. `python bin/harvest.py` (rafraîchit le bloc automatique du daily du jour).
2. Lire `<vault>/daily/<aujourd'hui>.md`, et celui de la veille si le dernier point date d'hier.
   Le dernier point = la dernière ligne `- HH:MM : /point` hors du bloc harvest (sinon : début de journée).
3. Lire la todo et l'index de `topics.md`, et les fiches `<vault>/projets/*.md` des sujets non ✅
   (en-tête + « Où j'en suis » + fin du Log).
4. Si un brief du rituel existe pour aujourd'hui (`<vault>/brief/<date>-point.md`), partir de lui et
   ne refaire que ce qui a changé depuis.

## 2. L'état des sessions
- `ws ls` : dernière activité de chaque session et consignes encore en attente dans les boîtes.
- Pour une session active depuis le dernier point, lire la fin de son transcript
  (`~/.claude/projects/*/<session>.jsonl`, dernières réponses de l'assistant) : a-t-elle posé une
  question, demandé un feu vert, fini une étape ?
- PR des sujets actifs non couvertes par le daily : `gh pr view <n> -R <owner/repo> --json state,reviewDecision,statusCheckRollup`.

## 3. Outils connectés (lecture seule, seulement s'ils sont disponibles dans la session)
Gestion de tâches, messagerie, agenda, wiki : ne lire que ce qui concerne l'utilisateur depuis le
dernier point (tâches dont il est responsable, mentions, messages directs, réunions du jour).
Pour chaque élément retenu : qui, où, quand, et **en une ligne ce qui est attendu de lui ou ce qui a
été décidé**. Signaler les écarts entre le statut d'une tâche dans l'outil et la réalité des fiches ;
proposer la mise à jour, **ne jamais l'écrire sans feu vert**.
En mode non interactif (rituel du matin), sauter cette étape et l'indiquer dans le brief.

## 4. Restituer (court, dans cet ordre)
1. **Ce qui t'attend** : actions qui ne dépendent que de l'utilisateur (feu vert demandé par une
   session, réponse attendue, review, décision), triées par urgence ; rappeler les échéances proches.
2. **Ce qui a bougé** depuis le dernier point : par sujet, 1-2 lignes, avec la source.
3. **Sessions** : une ligne par sujet actif avec son état (attend l'utilisateur / travaille / au repos).
4. **Écarts à corriger** : outil vs réalité, fiche périmée, todo cochable.
5. **Charge** : nombre de fronts 🔥 ; au-delà de `max_fronts`, le dire et proposer quoi mettre en pause.
Puis « Je propose de… » : la prochaine action concrète. Ne pas lancer de travail sur les sujets.

## 5. Mettre à jour (fichiers locaux uniquement, sans demander)
- `topics.md` : cocher les todos faits (avec la preuve courte), ajouter les nouveaux, statut de l'index.
- Fiches : « Où j'en suis », « Prochaine action », et une ligne `- JJ/MM : …` au Log par fait nouveau.
- Daily, hors du bloc harvest : `python bin/rituel.py note "/point — <faits marquants>"`.
- Lister à la fin les fichiers modifiés. Outils partagés : **jamais** d'écriture sans feu vert.
