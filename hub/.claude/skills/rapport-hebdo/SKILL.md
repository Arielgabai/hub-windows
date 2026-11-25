---
name: rapport-hebdo
description: Rédiger le récap de la semaine pour le manager ou l'équipe, à partir du vault, de git, des PR et des outils connectés, sans rien inventer. À utiliser quand l'utilisateur tape /rapport-hebdo, demande « le récap de la semaine », « le rapport hebdo », ou le vendredi en fin de journée.
---

# /rapport-hebdo — la semaine en un message

Destinataire : la personne indiquée dans `context.md` (manager, équipe). Elle veut savoir ce qui a
avancé, ce qui bloque et ce qui vient. Format par défaut : **message prêt à coller**. Chaque ligne est
adossée à une source lue pendant ce rapport ; pas de source, pas de ligne.

## 1. Fixer la période et ce qui a déjà été envoyé
- Par défaut du lundi au vendredi de la semaine en cours (la semaine écoulée si on est le week-end).
- Chercher le dernier récap : `<vault>/hebdo/`, les lignes `/rapport-hebdo` ou « récap » des daily.
  S'il couvre déjà une partie de la période, ne rédiger que le complément et le dire en tête.

## 2. Collecter
1. Fiches du vault : lignes de Log datées de la période (tout lire, elles ne sont pas toujours dans
   l'ordre), en-tête, « Où j'en suis », « Prochaine action ».
2. Daily de la période : sessions, commits, lignes `/point` et `/retex`. La section « Mes PR » du
   bloc harvest est un instantané : ne pas s'en servir pour dater un événement.
3. Git des dépôts de `hub.config.json` (`repos`) : `git log --all --since=<lundi> --until=<samedi>
   --author=<tes e-mails> --format="%h %ad %s" --date=format-local:"%d/%m %H:%M"`. Repérer le travail
   seulement local (`git branch -vv`, branche sans distant).
4. PR : `gh search prs --author=@me --updated=">=<lundi>"` plus les PR ouvertes même inactives, puis
   `gh pr view` pour l'état, les reviews et la CI.
5. Outils connectés (si disponibles) : tâches dont l'utilisateur est responsable, toutes celles non
   terminées (un statut en retard compte).
En cas de conflit entre sources : prendre la plus récente et précise, et lister l'écart en fin de rapport.

## 3. Rédiger
```
**Récap semaine du JJ/MM au JJ/MM**

**1. <Sujet> : <de quoi il s'agit> (<terminé / en cours / en attente>)**
- **<Livrable ou étape>** ([#PR](url)) : ce qui a été fait, avec le résultat ou la preuve.
- **Décision (JJ/MM, avec qui)** : quoi et pourquoi.
- **Reste** : ce qui manque pour finir.

**Autres sujets** : une ligne chacun.

**Semaine prochaine** : 2 à 4 points, échéances en premier.
```
Phrases courtes, résultats chiffrés quand la source les donne, termes métier plutôt que noms de
fonctions, pas de hash de commit (le travail local se dit « en local, pas encore de PR »). Ne pas
parler du hub ni de l'outillage personnel. Jamais de donnée sensible.

## 4. Vérifier avant de rendre
Sous le récap, « **Avant d'envoyer, vérifie** » : récap déjà envoyé qui recoupe la période, jours sans
trace, travail seulement local (branches, hash), écarts entre sources, sujets volontairement omis.

## 5. Archiver, ne pas envoyer
- Écrire le récap dans `<vault>/hebdo/<AAAA>-S<semaine ISO>.md` avec la période et la date en tête.
- Daily : `python bin/rituel.py note "/rapport-hebdo SNN rédigé"`.
- **Ne jamais l'envoyer** sans feu vert explicite : proposer de le coller soi-même, ou de le déposer en
  brouillon dans la messagerie si un connecteur le permet.
