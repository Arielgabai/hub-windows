---
name: curate
description: Le tri du vendredi — relire les frictions et pièges de la semaine dans le vault, repérer ce qui se répète et proposer de le transformer en règle (CLAUDE.md), en hook ou en skill. À utiliser quand l'utilisateur tape /curate, ou le vendredi après /rapport-hebdo.
---

# /curate — transformer les répétitions en règles

Principe : une friction payée deux fois ne doit pas l'être une troisième. Ce qu'on ne veut jamais
avoir à relire → **hook** (ex. `bin/garde.py`) ; convention, style, critère de fin → **CLAUDE.md** ;
savoir-faire réutilisable → **skill** ; fait durable → **context.md**.

## 1. Lire
- `<vault>/frictions.md` en entier, les « Conventions qui piègent » et « Décisions » de `context.md`.
- Les Logs des fiches `<vault>/projets/*.md` et les daily de la semaine : chercher les pièges, les
  blocages du garde (`⛔ garde`), les allers-retours, les corrections de l'utilisateur.
- `~/.claude/CLAUDE.md` et `CLAUDE.md` du hub, pour ne pas proposer ce qui existe déjà.

## 2. Trier
Pour chaque friction de la semaine : nouvelle, **répétée** (déjà vue, même sous une autre forme), ou
réglée. Ne retenir que les répétées et celles qui ont coûté cher (temps perdu, risque sur des données,
travail refait).

## 3. Proposer (au plus 3, du plus rentable au moins rentable)
Pour chacune : la friction, ses occurrences (dates, sources), la brique proposée, le texte ou le
changement exact, et ce que ça coûte. Signaler aussi une règle ou un garde-fou qui a gêné à tort.

## 4. Appliquer seulement avec feu vert
Rien n'est modifié sans accord de l'utilisateur (en mode non interactif : proposer seulement). Une fois
validé : faire le changement, marquer la ligne de `frictions.md` comme réglée (`✅ JJ/MM : …`), noter au
daily `/curate — <ce qui a changé>`. Un changement de script du hub se teste avant d'être appliqué
(`python -m unittest` dans le dépôt du hub s'il a des tests).
