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
| AI-VM 10.0.0.114 | 4 vCPU, pochi GB RAM | agenti pi (sono solo client HTTP), Hermes (Telegram, web), Claude Code, esecutore dei piani |

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
- Ollama resta finché serve a Hermes; non devono contendersi la GPU (una sola cosa grande alla volta).
- Il motore si sceglie per misura: il banco di prova (§8) confronta i modelli sui passi veri dei piani.

## 4. Agenti (pi)

Ogni agente è **pi** (`@mariozechner/pi-coding-agent`, prompt di sistema minimo, 4 strumenti di base) con una propria
cartella di configurazione (`PI_CODING_AGENT_DIR`), versionata in questo repository sotto `profili/<nome>/`:

```
profili/<nome>/
  models.json     fornitore e modello (llama-swap, o Anthropic per il coordinatore)
  settings.json   modello predefinito, ragionamento, opzioni
  AGENTS.md       istruzioni del ruolo (brevi)
  skills/         SOLO le skill di quel ruolo (standard Agent Skills, caricate su richiesta)
  strumenti       elenco per --tools (es. read,write,edit,bash oppure solo read,bash)
```

| Agente | Modello | Strumenti | Skill |
|---|---|---|---|
| `programmatore` | il vincitore del banco, in GPU, contesto 64k | read, write, edit, bash | kb, test del progetto, regole del repository |
| `coordinatore` | Claude (piano Max/API) o locale piccolo (D-A2) | read, bash | kb, `agente` (chiamare gli altri), stato dei progetti |
| `immagini` | modello di visione + ComfyUI per generare | read, bash | kb, comfyui |
| `voce` | Whisper (ascolto) + Kokoro/Piper (parlato), CPU di Unraid | bash | voce |

Comando unico sulla AI-VM: `agente <nome> [--cartella DIR] "<compito>"` → esegue `pi -p --no-session` con la cartella
del profilo, gli strumenti e il modello del ruolo; stampa il risultato. Usabile da Claude Code (Bash), da Hermes, dagli
altri agenti (il coordinatore lo ha come skill) e dall'esecutore dei piani.

## 5. Esecutore dei piani

Oggi `esegui-passo` (root, `/opt/ai-vm/libexec`) chiama Hermes dell'utente `esecutore`. Si sostituisce quella sola riga
con `agente programmatore --cartella <progetto>` (stesso utente, stessi limiti). Telegram, web e «avvia» restano a
Hermes dell'utente `hermes`. Le lezioni del 2026-10-30/31 restano valide: passi piccoli, comandi pronti per i file
grandi, verifiche che falliscono se il lavoro non c'è.

## 6. Second brain (KB)

- **Fonte unica:** cartella di Markdown sotto git, su share Unraid (`/mnt/user/kb`), aperta da te con Obsidian;
  montata sulla AI-VM in sola lettura per tutti tranne `inbox/` (D-A3).
- **Indice:** SQLite con FTS5 (parole) + vettori (`sqlite-vec`), ricostruibile in ogni momento dai file; embedding con
  un modello piccolo su CPU di Unraid (`bge-m3` o `nomic-embed-text`) servito da llama-swap.
- **Comando** `kb cerca|leggi|salva` e **skill `kb`** di pi. Gli agenti scrivono solo in `inbox/` con intestazione
  (agente, data, fonte, progetto); la promozione nelle cartelle definitive la fai tu o la propone il coordinatore.
- Niente credenziali nella KB.

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
| D-A1 | Modello del programmatore | il migliore del banco per riuscita e velocità |
| D-A2 | Coordinatore: Claude o locale | Claude (più capace, non occupa la GPU); locale piccolo come riserva |
| D-A3 | Dove sta la KB e come si monta | share Unraid `kb`, NFS sulla AI-VM (serve root sulla VM) |
| D-A4 | Motori della voce | faster-whisper small + Kokoro, CPU di Unraid |
| D-A5 | Immagini e video | ComfyUI; modelli scelti con un banco dedicato (16 GB) |
| D-A6 | Seconda GPU | da valutare solo se servono grande e piccoli accesi insieme |
| D-A7 | Esecutore dei piani su pi | sì, dopo D-A1; modifica di una riga in `esegui-passo` (root) |
