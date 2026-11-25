# Je suis (contexte global, lu par toutes les sessions)

_Modèle à remplir. Ce fichier va dans ~/.claude/CLAUDE.md : toutes tes sessions Claude Code le lisent._

## Qui je suis et ma mission
<Ton rôle, ton équipe, la période, le projet principal.>

## Mes objectifs
- **<échéance>** : <objectif>.
- **Fini quand** : <critère>.

## Les personnes
- **<Prénom>** : <rôle> ; <ce que tu lui demandes>.

## Ma façon de travailler
- <Ex. : maîtriser plutôt qu'aller vite ; faire valider ce dont je ne suis pas sûr.>
- Horaires : <…>.
- Ce que j'attends d'un agent quand il me rend la main : ce qu'il a fait et pourquoi, avec la preuve
  (commande, test, résultat). Face à un choix : les options et sa recommandation, sans trancher à ma place.

## Mon arbre de décision
- **Je demande** quand je ne suis pas sûr d'un point.
- **J'avance seul** sur ce dont je suis sûr et que j'ai vérifié.
- **Jamais sans mon feu vert** : pousser, ouvrir une PR, écrire dans un outil partagé, toucher la prod.
- **Jamais du tout** : <ex. lire le contenu de données sensibles (métadonnées seulement)>.

## Consignes pour l'agent
- Réponds en <langue>.
- En fin de session, ou quand une étape importante est finie, propose `/retex` pour ranger ce qui a été
  appris dans le vault.
- Distingue toujours le vérifié de l'hypothèse : une cause, un risque ou un état que tu n'as pas
  constaté s'écrit « hypothèse non vérifiée », avec le moyen de la vérifier.
- Si une consigne du hub arrive (bloc « Consignes du hub en attente »), traite-la comme une demande
  de l'utilisateur relayée par le hub.
