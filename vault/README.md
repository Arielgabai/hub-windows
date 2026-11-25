# Vault

Mémoire partagée par toutes les sessions Claude du hub (injectée au démarrage par `vault_context.py`).

- `context.md` : qui tu es, personnes, dépôts, pièges, décisions transverses.
- `projets/<sujet>.md` : une fiche par sujet (`_modele.md` sert de gabarit à `ws new`).
- `daily/AAAA-MM-JJ.md` : le journal du jour (bloc automatique de harvest + lignes des sessions).
- `frictions.md` : les pièges payés, relus au /curate.
- `brief/` : sorties des rituels non interactifs (point du matin, rapport et curate du vendredi).
- `hebdo/` : rapports hebdo archivés.
- `inbox/` : consignes déposées par `ws send`, remises à la session du sujet (`inbox/lu/` = historique).
- `portable/` : leçons de méthode réutilisables ailleurs, sans aucun nom propre.

Jamais de donnée sensible ici : métadonnées seulement. Si le vault a un dépôt distant, `vault_sync.py`
le synchronise toutes les heures : garde ce dépôt **privé**.
