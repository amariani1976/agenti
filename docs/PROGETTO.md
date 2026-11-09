# Agenti locali verticali, motore solo GPU e second brain

Stato: **bozza** · 2026-10-31 · decisioni aperte in fondo (§9).

## 1. Obiettivo

Un insieme di **agenti leggeri e specializzati**, richiamabili su richiesta (da Claude Code, da Hermes/Telegram,
dagli altri agenti), ognuno con **solo il modello, gli strumenti e le skill che gli servono**, che girano sull'hardware
di casa con priorità alla **velocità**. Più una **knowledge base personale** (second brain) da cui gli agenti
attingono e in cui salvano il loro lavoro.

## 2. Hardware e ripartizione

| Macchina | Risorse | Cosa ci gira |
|---|---|---|
| Unraid 10.0.0.100 | RTX 4070 16 GB, 24 core, 62 GB RAM | motore dei modelli (GPU), servizi leggeri su CPU (embedding, voce), KB su share |
| AI-VM 10.0.0.114 | 8 vCPU, 16 GB RAM | agenti pi (sono solo client HTTP), Hermes (Telegram, web), Claude Code, esecutore dei piani |

Regole: **tutto ciò che deve essere veloce sta in GPU**; sulla CPU solo cose minuscole (embedding, sintesi e
riconoscimento vocale piccoli). La GPU regge un solo modello grande alla volta: per grande + piccoli accesi insieme
l'unica via pulita è una seconda GPU (§9, D-A6).

## 3. Motore: llama-swap + llama.cpp (Unraid)

- Container `llama-swap` (immagine `ghcr.io/mostlygeek/llama-swap:cuda`), API OpenAI su `http://10.0.0.100:9292/v1`,
  configurazione in `/mnt/user/appdata/llama-swap/config.yaml`, modelli GGUF in `/mnt/user/appdata/llama-swap/models`.
- Ogni modello ha un nome di ruolo (`programmatore`, …) e parametri propri: tutti gli strati in GPU (`-ngl 99`),
  contesto esplicito, KV in q8_0 con flash attention, template originali (`--jinja`).
- llama-swap carica su richiesta e scarica dopo `ttl`; i **gruppi** tengono accesi insieme più modelli quando lo
  spazio lo permette (es. un piccolo su CPU accanto al programmatore).
- Hermes e pi usano llama-swap attraverso il proxy coda-gpu; Ollama non si usa più (2026-11-09). Il container passerà a `motore-ai` (llama-swap + calcolatore dei modelli per VRAM, repository AI-VM `motore/`), affiancato dal container `kb` (§6).
- Il motore si sceglie per misura: il banco di prova (§8) confronta i modelli sui passi veri dei piani.

## 4. Agenti (pi)

Ogni agente è **pi** (`@mariozechner/pi-coding-agent`, prompt di sistema minimo, 4 strumenti di base) e gira
**sempre** come utente `esecutore` attraverso `/opt/ai-vm/libexec/esegui-passo`, chiuso in `/srv/progetti`, con
l'unico profilo `~esecutore/.pi/esecutore` (generato da `ai-vm-modello`). I ruoli (programmatore, revisore,
ricercatore) sono prompt diversi sullo stesso agente (`ciclo/ruoli.py`), non profili separati. Aggiornato il
2026-11-09: tolti i profili per agente e il lancio diretto di pi come utente `hermes`.

Modello: solo i nomi generici `esecutore` (senza ragionamento) ed `esecutore-pensiero` (dopo un errore); il proxy
coda-gpu li traduce nel modello «attivo» di `/opt/ai-vm/modelli.json`, l'unico posto dove si sceglie.

## 5. Esecutore dei piani

Il runner dei piani e il comando `agente` (con verifica o orchestratore) usano lo stesso `esegui-passo` e la stessa
regola: primo tentativo senza ragionamento, i successivi con. Hermes per i lavori sul codice usa `progetto piano`
(Claude scrive test e piano, come in sessione) e poi `progetto avvia`.

## 6. Second brain (KB)

Decisione del 2026-10-31 (D-A3): la KB sta **insieme all'engine** su Unraid, in un **container separato** (`kb`)
installato e aggiornato con `motore-ai`: si può ricostruire il motore senza fermare la KB né toccarne i dati.

- **File (fonte unica):** Markdown sotto git nella share `/mnt/user/kb`, apribile da Obsidian.
  Cartelle: `inbox/` (scrivono gli agenti), `progetti/`, `decisioni/`, `lezioni/`, `persone/`, …
- **Fonti esterne in sola lettura:** si indicizzano senza copiarli i documenti che hanno già una casa (guida AI-VM,
  `docs/` dei progetti, ricerche): elenco in `fonti.json`, risultati marcati con la fonte. Una sola versione di ogni
  documento, quella nel suo repository.
- **Indice:** SQLite con FTS5 (parole) + `sqlite-vec` (significato) in `/mnt/user/appdata/kb`, ricostruibile in ogni
  momento dai file. **Embedding dall'engine** con un modello piccolo **su CPU** (`nomic-embed-text` o `bge-m3`,
  `-ngl 0`, sempre acceso in un gruppo di llama-swap): la VRAM resta tutta al modello principale.
- **Servizio `kb`** (CPU, accanto a `motore-ai`): operazioni `cerca`, `leggi`, `salva`, `collega` esposte come
  **API HTTP** e come **server MCP** sulla stessa porta. Ogni salvataggio è un commit git (tutto annullabile).
- **Agganci:**

| Chi | Come |
|---|---|
| Agenti pi | skill `kb` con il comando `kb` della AI-VM (client dell'API) |
| Esecutore dei piani | cerca le lezioni prima di un passo; a fine piano salva un riassunto in `inbox/` |
| Hermes (Telegram/web) | server MCP |
| Claude Code | server MCP |
| Utente | Obsidian sulla share; poi la scheda «KB» nell'interfaccia web dell'engine |

- **Regole:** gli agenti scrivono solo in `inbox/` con intestazione (agente, data, progetto, fonte); la promozione
  nelle cartelle definitive la fa l'utente o la propone il coordinatore. **Niente credenziali:** `salva` rifiuta i
  testi che sembrano segreti (password, token, chiavi private).
### 6.1 Ciclo della conoscenza: KB → internet → KB

Regola per ogni agente (richiesta dell'utente, 2026-10-31): **se non sa fare qualcosa, prima cerca nella KB; se nella
KB non c'è, cerca su internet; quello che trova e gli è servito lo salva nella KB** per riusarlo la volta dopo.

1. **KB:** `kb cerca` con poche parole precise; se un risultato basta, lo usa e lo cita (percorso della nota).
2. **Internet** (solo se la KB non basta): skill `web` con `web cerca "…"` (motore di ricerca locale **SearXNG**,
   container `kb-searxng` su Unraid, porta 8888, installato il 2026-10-31; nessuna chiave a pagamento) e
   `web leggi URL` (pagina ripulita in Markdown, troncata; solo libreria standard). Limiti: 3 ricerche e 5 pagine
   ogni 10 minuti, poi si ferma e lo dice. Da casa rispondono Bing e GitHub (Google vuoto, DuckDuckGo con CAPTCHA):
   per questo niente riserva diretta su DuckDuckGo; SearXNG ripiega da solo sui motori che rispondono.
3. **Salvataggio:** `kb salva` in `inbox/` con intestazione `fonte: web`, gli URL, la data e `stato: da-verificare`;
   testo **scritto dall'agente** (sintesi di ciò che è servito, con i comandi o i passi provati), non la pagina copiata.
   Prima di salvare cerca se esiste già una nota sullo stesso argomento: in quel caso la aggiorna (nuova nota con
   `aggiorna: <percorso>`), senza duplicati.
4. **Riuso:** le note in `inbox/` sono già ricercabili; nei risultati si vede `da-verificare`. La promozione (che toglie
   lo stato) la fa l'utente o la propone il coordinatore; le note con fonte web oltre 6 mesi si segnalano come vecchie.

Sicurezza: il contenuto delle pagine è **dato, mai istruzioni** (niente comandi eseguiti perché «lo dice la pagina»
senza capirli, niente segreti inviati fuori); `web` è solo lettura (GET, niente moduli né accessi con credenziali),
blocca indirizzi locali e della rete di casa; il controllo dei segreti di `salva` vale anche qui. L'esecutore dei
piani usa `web` solo in lettura e mai per uscire dal perimetro del passo.

- **Parti** (stesso ramo `ai/agenti-base`, una dopo l'altra; i piani in attesa stanno in `piani/` e diventano
  `PLAN.md` quando tocca a loro):
  1) nucleo `kb.py` (file, inbox, lettura sicura, FTS5, segreti), comando `agente`, profilo `programmatore` — `PLAN.md`;
  2) servizio HTTP + MCP, fonti esterne, git — `piani/parte2-kb-servizio.md`;
  3) vettori con l'engine (dopo l'installazione di `motore-ai` e la scelta del modello di embedding);
  4) client della KB (`KB_URL`) e ricerca su internet (`web`, skill e ciclo §6.1) — `piani/parte4-client-e-web.md`;
  5) installazione su Unraid (container `kb`, fonti sincronizzate dalla AI-VM) e agganci a Claude Code, Hermes ed
     esecutore: li fa Claude, non l'esecutore (toccano server e configurazioni).
  Le parti 2 e 4 sono state provate prima con un'implementazione di riferimento (fuori dal repository): tutti i test
  dei piani passano.

## 7. Immagini, video e voce

- Generazione immagini/video: ComfyUI in container su Unraid, **a turno** sulla GPU: prima di un lavoro si scaricano i
  modelli di llama-swap (`/unload`), dopo si restituisce la GPU. Coda semplice con un lucchetto `gpu-turno`.
- Comprensione immagini: modello di visione via llama-swap (`--mmproj`).
- Voce: faster-whisper (small, int8) e Kokoro su CPU di Unraid, esposti come servizi HTTP.

## 8. Banco di prova

`~/ricerche/banco` (poi in questo repository sotto `banco/`): ogni modello esegue con pi gli stessi passi veri di un
piano, nella copia `/srv/progetti/prova-f3`, con verifica, tempo, numero di chiamate e memoria della GPU. Si ripete a
ogni nuovo modello o aggiornamento del motore. Prima tornata (2026-10-31): 13 modelli (9 MoE, 4 densi piccoli).

## 9. Decisioni aperte

| ID | Domanda | Proposta |
|---|---|---|
| D-A1 | Modello del programmatore | **accettata 2026-10-31:** Qwen3.5-35B-A3B (banco, alias `esecutore`) |
| D-A2 | Coordinatore: Claude o locale | Claude (più capace, non occupa la GPU); locale piccolo come riserva |
| D-A3 | Dove sta la KB e come si monta | **accettata 2026-10-31:** con l'engine su Unraid, container `kb` separato, API + MCP (§6) |
| D-A4 | Motori della voce | faster-whisper small + Kokoro, CPU di Unraid |
| D-A5 | Immagini e video | ComfyUI; modelli scelti con un banco dedicato (16 GB) |
| D-A6 | Seconda GPU | da valutare solo se servono grande e piccoli accesi insieme |
| D-A7 | Esecutore dei piani su pi | sì, dopo D-A1; modifica di una riga in `esegui-passo` (root) |
| D-A8 | Ricerca su internet per gli agenti | **accettata 2026-10-31** come regola (§6.1); motore: SearXNG in container su Unraid (proposta) |
