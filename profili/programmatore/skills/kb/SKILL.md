---
name: kb
description: Cerca, legge e salva note nella knowledge base personale (second brain) dell'utente. Usala per recuperare decisioni, convenzioni e contesto già scritti, e per salvare il risultato di un lavoro.
---

# Knowledge base

La KB è una cartella di Markdown. Comando: `kb` (variabili `KB_DIR` e `KB_DB` già impostate).

- Cercare: `kb cerca "parole chiave"` → elenco `percorso: titolo` con un estratto. Usa poche parole precise.
- Leggere: `kb leggi percorso/della/nota.md`.
- Salvare il proprio lavoro: `echo "testo" | kb salva --agente <nome> --titolo "Titolo" [--progetto <nome>]`
  → scrive in `inbox/`; non scrivere mai altrove nella KB.

Non mettere mai credenziali o segreti nella KB.
