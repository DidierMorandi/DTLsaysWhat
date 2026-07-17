# DTLsaysWhat

DTLsaysWhat est un outil d'inventaire système Windows inspiré du célèbre **WHAT** écrit par Stanley Rabinowitz pour DEC VAX/VMS dans les années 80.

L'objectif est de fournir, depuis une simple commande, un rapport complet et lisible sur l'état d'une machine Windows, sans installation complexe ni infrastructure centrale.

## Fonctionnalités

- Informations système
- Inventaire matériel
- Mémoire physique et virtuelle
- Disques et volumes
- Cartes graphiques
- Configuration réseau
- Utilisateurs locaux
- Services Windows
- Processus en cours
- Programmes au démarrage
- Sécurité Windows
- Mises à jour installées
- Pilotes installés
- Tâches planifiées
- Partages SMB
- Sessions SMB actives
- Fichiers ouverts via SMB
- Événements récents
- Virtualisation
- Rapport texte
- Rapport HTML

## Installation

Prérequis :

- Windows 10 ou Windows 11
- Python 3.10 ou supérieur

Installer les dépendances :

```bash
pip install psutil wmi pywin32
```

## Utilisation

Afficher l'aide :

```bash
python dtlsayswhat.py -h
```

Rapport système :

```bash
python dtlsayswhat.py system
```

Rapport réseau :

```bash
python dtlsayswhat.py network
```

Rapport complet :

```bash
python dtlsayswhat.py all
```

Rapport sur une machine distante :

```bash
python dtlsayswhat.py system --computer PC-BEN-001
```

Langue anglaise :

```bash
python dtlsayswhat.py system --lang en
```

## Philosophie

DTLsaysWhat privilégie :

- la simplicité ;
- la lisibilité ;
- l'absence d'infrastructure complexe ;
- l'esprit des outils d'administration DEC/VMS.

## Documentation

- Guide utilisateur
- Manuel de référence

## Licence

Ce projet est distribué sous licence MIT.

## Mise à jour - 14 juin 2026

Le code courant annonce `APP_VERSION = "v1.0-10"` dans `DTLsaysWhat.py`.

Points confirmés :

- L'outil accepte `--lang fr|en` pour les libellés principaux.
- `--computer NOM_OU_IP` peut interroger une machine distante via WMI lorsque les droits et le réseau le permettent.
- `--output` / `-o` écrit un rapport texte.
- Au lancement interactif, les deux choix produisent un rapport complet : privé ou partageable anonymisé.
- Un second menu permet de sélectionner tous les chapitres ou plusieurs chapitres par leur numéro.
- `--anonymize` génère directement un rapport partageable ; `--report-type private|shareable` permet d'automatiser ce choix.
- Le rapport HTML s'ouvre automatiquement à la fin du traitement ; `--no-open` désactive cette ouverture.
- Le contenu détaillé n'est plus affiché dans la console, mais les rapports TXT et HTML sont toujours enregistrés.
- Pendant la génération, une ligne unique affiche le chapitre en cours et se réécrit sur place.
- Sans catégorie explicite, le périmètre est `all`. Une catégorie comme `system` ou `network` permet volontairement de produire un rapport partiel en ligne de commande.
- Les catégories disponibles incluent `system`, `hardware`, `memory`, `disk`, `gpu`, `network`, `software`, `services`, `processes`, `startup`, `security`, `updates`, `drivers`, `users`, `tasks`, `shares`, `events`, `perf`, `virt` et `all`.
- Le dépôt contient maintenant des guides utilisateur et manuels de référence en français et en anglais.
- `DTLsaysWhat_PREDATOR_example.html` est présent comme exemple de sortie HTML.
