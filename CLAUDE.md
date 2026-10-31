@AGENTS.md

# Agenti

Agenti locali verticali (pi) richiamabili su richiesta, motore solo GPU (llama-swap su Unraid) e second brain (KB in
Markdown con indice locale). **Leggere prima `docs/PROGETTO.md`**: architettura, ripartizione dell'hardware e decisioni
aperte (D-A1…D-A7), da chiarire con l'utente prima di costruire ciò che ne dipende.

Regole:
- Velocità prima di tutto: ciò che deve essere veloce sta in GPU; CPU solo per cose minuscole, e sulla CPU di Unraid
  (la AI-VM ha 4 vCPU).
- Ogni agente carica solo le sue skill e i suoi strumenti; niente capacità che non gli servono.
- Unraid e AI-VM: modifiche consentite dall'utente; riportare in questo repository ogni passo manuale in forma
  ripetibile (script o configurazione), mai solo a mano.
- Niente segreti nel repository, nella KB o nei log.
- Lingua di documenti, commenti e messaggi di commit: italiano.

Comandi utili in questa VM: `/piano <richiesta>` scrive PLAN.md per l'esecutore locale; `/revisione`
confronta il lavoro con il piano; `progetto stato agenti` mostra l'avanzamento; `progetto avvia
agenti` approva il piano e fa partire l'esecuzione con il modello locale.
