# Advanced-Compilation

## Equipe

- Félix JOSQUIN : fonctions
- Léo SEGUIN : tableaux
- Julien COMMES : string
- Enzo DAMION : pointeurs

## Structure du dossier

- README.md
- moule.asm
- compilo.py
- test

## Execution

Pour le pretty-printer :

    python3 compile.py pp ./test/test?.nanoC

Pour le compilateur :

    python3 compile.py cp ./test/test?.nanoC
    ./prgm var1 var2 ...

## Features

Les features n'ont pas été testées pour être interfonctionnelles.

### Pointeurs

Opérationels :

- pointeurs simples
- doubles pointeurs

Non-opérationels :

- malloc
- écrire sur l'adresse d'un pointeur
