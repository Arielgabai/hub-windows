---
name: retex
description: Retour d'expérience de fin de session — ranger dans le vault ce que la session a fait, décidé et appris (fiche du sujet, décisions, pièges, daily). À utiliser quand l'utilisateur tape /retex, dit « fais le retex », « range ce qu'on a appris », ou en fin de session / d'étape.
---

# /retex — ranger ce que la session a appris

But : la prochaine session sur ce sujet (qui reçoit le vault au démarrage) repart d'où on en est, sans
qu'on lui réexplique rien. On écrit des **faits sourcés et courts**, pas un compte rendu.

## 1. Trouver le sujet et ce qui est déjà rangé
- Le sujet de la session est indiqué dans le contexte injecté au démarrage (« Sujet de cette
  session : … ») ; sinon le chercher dans l'index de `topics.md` du hub par l'id de session, ou
  demander à l'utilisateur. Le chemin du vault est la clé `vault` de `hub.config.json` (défaut `~/vault`).
- Relire la fiche `<vault>/projets/<sujet>.md`, `context.md` et `frictions.md` **maintenant** (le hub
  et d'autres sessions y écrivent).
- Ce qui est déjà au Log n'est pas à réécrire : ne ranger que ce qui est nouveau depuis le dernier
  retex de cette session (ou depuis son début).

## 2. Faire l'inventaire (depuis la conversation, vérifié par les outils)
Lister, chacun avec sa source (commit, PR, commande, message, échange avec l'utilisateur) :
- **Fait** : ce qui a changé dans le monde (commit, PR ouverte, run lancé, page modifiée).
- **Décidé** : par qui, quoi, pourquoi.
- **Appris** : un fait durable sur le code, les données, les outils ou l'organisation.
- **Piège payé** : du temps perdu, une fausse piste, un outil qui a menti ou échoué.
- **En attente** : feu vert demandé, question posée à quelqu'un, CI en cours.
Vérifier ce qui peut l'être (`git log`, `gh pr view`) plutôt que de se fier à sa mémoire.

## 3. Écrire (modifications ciblées, jamais réécrire un fichier entier)
- **Fiche du sujet** : en-tête (Statut, Branche, PR, **Prochaine action**) ; « Où j'en suis (JJ/MM) »
  réécrit pour refléter l'état actuel (3-6 lignes) ; Log : une ligne par fait / décision / attente,
  `- JJ/MM : … (source)`.
- **`context.md`**, seulement si c'est transverse : Décisions, Conventions qui piègent, Personnes, Dépôts.
- **`frictions.md`** : chaque piège payé → `| JJ/MM | friction | réponse proposée |`. Si la même
  friction y est déjà, le dire : c'est une répétition, candidate à devenir une règle.
- **Daily** du jour, hors du bloc harvest : `- HH:MM : /retex <sujet> — <une ligne>`.
- **`portable/`** : seulement une leçon de méthode sans aucun nom propre ; la proposer plutôt que
  l'écrire d'office.

## 4. Règles
- Jamais de donnée sensible (contenu de fichier client, secret) : métadonnées,
  compteurs, chemins, noms de variables seulement.
- Ne rien inventer : pas de source → ne pas l'écrire (ou le marquer « à vérifier »).
- Court : une ligne de Log = une phrase. Le hash ou le numéro de PR suffit.

## 5. Rendre compte
Afficher `git -C <vault> diff --stat` puis les lignes ajoutées ou changées, regroupées par fichier, et
signaler ce qui a été laissé de côté (et pourquoi). Ne pas commiter : `vault_sync.py` le fait.
