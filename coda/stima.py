"""Stima dei token che servono a una richiesta OpenAI: caratteri // 3 + risposta massima + margine."""

MAX_RISPOSTA = 8192


def testo(contenuto):
    """Testo di un campo `content`: stringa così com'è, lista di parti → concatenazione dei `text`, altro → ''."""
    if isinstance(contenuto, str):
        return contenuto
    if isinstance(contenuto, list):
        return ''.join(str(p.get('text') or '') for p in contenuto if isinstance(p, dict))
    return ''


def stima(corpo):
    """Token stimati per la richiesta `corpo` (dict già decodificato dal JSON)."""
    caratteri = sum(len(testo(m.get('content'))) for m in corpo.get('messages') or [] if isinstance(m, dict))
    caratteri += len(str(corpo.get('prompt') or ''))
    caratteri += len(str(corpo.get('tools') or ''))
    risposta = corpo.get('max_tokens') or corpo.get('max_completion_tokens') or MAX_RISPOSTA
    return caratteri // 3 + int(risposta) + 64
