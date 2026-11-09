"""Esecuzione reale del ciclo: agente e verifica passano da esegui-passo."""
import os
import subprocess


# Prima senza ragionamento; con ragionamento solo quando il prompt riporta un errore o dei difetti del tentativo prima
# (utente, 2026-11-09). I nomi sono generici: il proxy li traduce nel modello attivo di modelli.json.
SENZA, CON = 'esecutore', 'esecutore-pensiero'
SEGNI_RITENTATIVO = ('Errore della verifica nel tentativo precedente', 'Difetti rilevati dalla revisione',
                     'Il tentativo precedente ha toccato file fuori dal perimetro')


def modello_per(prompt):
    return CON if any(s in prompt for s in SEGNI_RITENTATIVO) else SENZA


class Esecuzione(object):
    """Gestisce l'esecuzione di un agente e la verifica dei passi."""

    def __init__(self, radice, esegui, modello=None, tempo=1900):
        self.radice = radice
        self.esegui = esegui
        self.modello = modello
        self.tempo = tempo

    def progetto(self, cartella):
        """Restituisce il nome del progetto se realpath(cartella) == radice/nome."""
        rp = os.path.realpath(cartella)
        radice_rp = os.path.realpath(self.radice)
        # Verifica se cartella è sotto radice
        if rp == radice_rp:
            raise ValueError('la cartella non è un progetto')
        if not rp.startswith(radice_rp + os.sep):
            raise ValueError('non è sotto la radice')
        # Estrai il nome del progetto (prima componente dopo radice)
        nome = os.path.relpath(rp, radice_rp)
        # Deve essere esattamente radice/nome, senza sottodirettori
        if nome != os.path.basename(nome):
            raise ValueError('non è un progetto diretto')
        return nome

    def _lancia_sottoprocesso(self, args, input_text, cartella):
        """Esegue un subprocess con timeout e restituisce (codice, uscita)."""
        try:
            r = subprocess.run(
                args,
                input=input_text,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                cwd=cartella,
                timeout=self.tempo
            )
            codice = r.returncode
            uscita = r.stdout if r.stdout else ''
            return codice, uscita
        except subprocess.TimeoutExpired:
            return (124, 'tempo massimo superato')

    def lancia(self, prompt, cartella):
        """Esegue esegui + ['agente', nome, modello] con prompt su stdin."""
        nome = self.progetto(cartella)
        args = self.esegui + ['agente', nome, self.modello or modello_per(prompt)]
        return self._lancia_sottoprocesso(args, prompt, cartella)

    def verifica(self, comando, cartella):
        """Esegue esegui + ['verifica', nome] con comando su stdin."""
        nome = self.progetto(cartella)
        args = self.esegui + ['verifica', nome]
        return self._lancia_sottoprocesso(args, comando, cartella)

    def lezioni(self, compito):
        """Esegue kb cerca con le prime parole del compito, max 1500 caratteri."""
        # Estrai le prime parole del compito (massimo 10 parole)
        parole = compito.split()[:10]
        if not parole:
            return []
        query = ' '.join(parole)
        try:
            r = subprocess.run(
                ['kb', 'cerca', query],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                timeout=self.tempo
            )
            if r.returncode != 0:
                return []
            testo = r.stdout if r.stdout else ''
            return [] if not testo else [testo[:1500]]
        except (FileNotFoundError, OSError):
            return []
        except subprocess.TimeoutExpired:
            return []
