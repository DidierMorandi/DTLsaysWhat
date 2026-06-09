# DTLsaysWhat

DTLsaysWhat est un outil d'inventaire système Windows inspiré du célèbre **WHAT** écrit par Stanley Rabinowitz pour DEC VAX/VMS dans les années 80.

L'objectif du projet est de fournir, à partir d'une simple commande, un rapport complet et lisible sur l'état d'une machine Windows, sans installation complexe ni dépendance à une infrastructure centrale.

## Fonctionnalités

* Informations système
* Inventaire matériel
* Mémoire physique et virtuelle
* Disques et volumes
* Cartes graphiques
* Configuration réseau
* Utilisateurs locaux
* Services Windows
* Processus en cours d'exécution
* Programmes au démarrage
* Sécurité Windows
* Mises à jour installées
* Pilotes installés
* Tâches planifiées
* Partages SMB
* Sessions SMB actives
* Fichiers ouverts via SMB
* Événements récents
* Virtualisation
* Rapport texte
* Rapport HTML

## Installation

Prérequis :

* Windows 10 ou Windows 11
* Python 3.10 ou supérieur

Installer les dépendances :

```bash
pip install psutil wmi pywin32
```

## Utilisation

Afficher les catégories disponibles :

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

## Sorties

DTLsaysWhat génère :

* un rapport texte (.txt)
* un rapport HTML (.html)

Les rapports sont enregistrés dans le répertoire courant.

## Philosophie

DTLsaysWhat privilégie :

* la simplicité
* la lisibilité
* l'absence d'infrastructure complexe
* l'esprit des outils d'administration DEC/VMS

## Documentation

* User Guide
* Reference Manual

## Licence

Ce projet est distribué sous licence MIT.
