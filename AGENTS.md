# Regole per gli agenti — progetto agenti

Questo progetto si lavora in due: **Claude** (Claude Code, piano Max) scrive analisi e piani e rivede il
lavoro; un **modello locale** (esecutore AI-VM) esegue i passi del piano uno alla volta.

- Il lavoro e' guidato da `PLAN.md`: un passo alla volta, nell'ordine; i passi fatti sono `- [x]`.
- Ogni passo indica i file da toccare e una **verifica** (comando) che deve passare.
- Non modificare file non citati dal passo corrente, se non strettamente necessario.
- Non uscire mai dalla cartella del progetto.
- Commit e push li fa il sistema (ramo indicato in `PLAN.md`); l'esecutore non usa git.
- Se un passo e' ambiguo o impossibile, fermarsi e spiegarlo: verra' spezzato in passi piu' piccoli.

## Note del progetto
(linguaggio, comandi di build e test, convenzioni: le completa Claude con l'analisi iniziale)
