"""Coda di ammissione per la gestione della riserva di contesto condivisa.

Questa classe gestisce l'accesso alla GPU del motore di inferenza, permettendo a più
richieste di condividere lo stesso modello rispettando i limiti di capacità e slot.
Le richieste in attesa vengono organizzate per priorità e invecchiano nel tempo,
salendo di livello per evitare starvation.
"""

import itertools
import threading
import time


PRIORITA = {'alta': 0, 'normale': 1, 'bassa': 2}


class Pieno(Exception):
    """Eccezione sollevata quando una richiesta non può entrare in coda entro il tempo massimo."""
    pass


class Coda:
    """Coda di ammissione con priorità e invecchiamento.

    Attributi:
        capacita: capacità totale della riserva di contesto in token.
        slot_max: numero massimo di richieste simultanee (slot GPU).
        invecchiamento: secondi di attesa per salire di un livello di priorità.
        orologio: funzione che restituisce il tempo corrente (default: time.monotonic).
        cv: condizione per la sincronizzazione tra thread.
        attivi: dizionario biglietto → token (richieste in esecuzione).
        attesa: lista di voci (numero, bisogno, priorita, arrivo) in attesa.
        numeri: contatore per generare biglietti univoci.
    """

    def __init__(self, capacita, slot_max, invecchiamento=60.0, orologio=time.monotonic):
        self.capacita = capacita
        self.slot_max = slot_max
        self.invecchiamento = invecchiamento
        self.orologio = orologio
        self.cv = threading.Condition()
        self.attivi = {}
        self.attesa = []
        self.numeri = itertools.count(1)

    def _ordine(self, voce):
        """Calcola la priorità ordinata per una voce in coda.

        L'ordine tiene conto della priorità originale, dell'invecchiamento
        (che fa salire di livello la richiesta) e del numero di biglietto
        per rompere i pareggi in modo deterministico.

        Args:
            voce: tupla (numero, bisogno, priorita, arrivo).

        Returns:
            Tupla (priorita_effettiva, arrivo, numero) per il confronto.
        """
        numero, bisogno, priorita, arrivo = voce
        if self.invecchiamento:
            promozione = int((self.orologio() - arrivo) // self.invecchiamento)
        else:
            promozione = 0
        return (max(0, PRIORITA[priorita] - promozione), arrivo, numero)

    def _primo(self):
        """Restituisce la voce in testa alla coda, se presente.

        Restituisce la voce con priorità ordinata minima.

        Returns:
            La voce in testa, o None se la coda è vuota.
        """
        if not self.attesa:
            return None
        return min(self.attesa, key=self._ordine)

    def _entra_ora(self, bisogno):
        """Verifica se una richiesta può entrare in questo momento.

        Args:
            bisogno: numero di token richiesti.

        Returns:
            True se è possibile entrare, False altrimenti.
        """
        return (len(self.attivi) < self.slot_max and
                sum(self.attivi.values()) + bisogno <= self.capacita)

    def entra(self, bisogno, priorita='normale', attesa_max=None):
        """Richiede l'ingresso in coda per una nuova richiesta.

        La richiesta viene inserita in attesa e bloccata finché non è in testa
        e può entrare rispettando i vincoli di capacità e slot. Se la priorità
        è sconosciuta, solleva ValueError. Se il tempo massimo scade senza
        entrare, solleva Pieno.

        Args:
            bisogno: token necessari per la richiesta.
            priorita: 'alta', 'normale' o 'bassa'.
            attesa_max: secondi massimi da attendere (None = attendi sempre).

        Returns:
            Biglietto (int) per identificare la richiesta attiva.

        Raises:
            ValueError: se la priorità non è riconosciuta.
            Pieno: se il tempo massimo scade prima di entrare.
        """
        if priorita not in PRIORITA:
            raise ValueError("priorità sconosciuta: %s" % priorita)

        bisogno = min(int(bisogno), self.capacita)
        arrivo = self.orologio()
        numero = next(self.numeri)
        voce = (numero, bisogno, priorita, arrivo)

        with self.cv:
            self.attesa.append(voce)
            inizio_attesa = time.monotonic()

            while True:
                # Verifica se questa voce è in testa e può entrare
                if self._primo() == voce and self._entra_ora(bisogno):
                    break

                # Calcola tempo rimanente
                if attesa_max is not None:
                    tempo_trascorso = time.monotonic() - inizio_attesa
                    tempo_rimanente = attesa_max - tempo_trascorso
                    if tempo_rimanente <= 0:
                        # Scaduto: rimuovi la voce e notifica tutti
                        self.attesa.remove(voce)
                        self.cv.notify_all()
                        raise Pieno("tempo massimo di attesa superato")

                    # Attendi con timeout per riesaminare la situazione
                    self.cv.wait(timeout=min(tempo_rimanente, 1.0))
                else:
                    # Nessun limite: attendi a intervalli di 1 secondo
                    self.cv.wait(timeout=1.0)

            # Entrata consentita: rimuovi dalla coda e aggiungi agli attivi
            self.attesa.remove(voce)
            self.attivi[numero] = bisogno
            self.cv.notify_all()
            return numero

    def esci(self, biglietto):
        """Segnala la fine di una richiesta attiva.

        Args:
            biglietto: numero della richiesta da rimuovere.
        """
        with self.cv:
            if biglietto in self.attivi:
                del self.attivi[biglietto]
            self.cv.notify_all()

    def stato(self):
        """Restituisce lo stato attuale della coda.

        Returns:
            Dizionario con:
                - capacita: capacità totale in token.
                - slot_max: numero massimo di slot.
                - attivi: numero di richieste attive.
                - in_uso: somma dei token in uso.
                - in_attesa: numero di richieste in attesa.
        """
        return {
            'capacita': self.capacita,
            'slot_max': self.slot_max,
            'attivi': len(self.attivi),
            'in_uso': sum(self.attivi.values()),
            'in_attesa': len(self.attesa)
        }
