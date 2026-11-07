"""Lettura del primo oggetto JSON da una risposta del modello."""
import json
import re


def primo_json(testo):
    """Estrae il primo oggetto JSON da una risposta.
    
    - Restituisce None se il testo è vuoto o None
    - Se c'è un blocco ```json ... ``` usa il suo contenuto
    - Poi prova json.JSONDecoder().raw_decode(testo, i) da ogni posizione i
      in cui c'è '{', in ordine
    - Restituisce il primo risultato che è un dict
    - Altrimenti None
    """
    if not testo:
        return None
    
    # Cerca prima un blocco ```json ... ```
    blocco = re.search(r'```json\s*(.*?)\s*```', testo, re.DOTALL)
    if blocco:
        testo = blocco.group(1)
    
    # Prova a decodificare da ogni posizione dove c'è '{'
    decoder = json.JSONDecoder()
    for i in range(len(testo)):
        if testo[i] == '{':
            try:
                risultato, _ = decoder.raw_decode(testo, i)
                if isinstance(risultato, dict):
                    return risultato
            except (ValueError, TypeError):
                continue
    
    return None
