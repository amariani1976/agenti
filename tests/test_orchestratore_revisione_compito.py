"""La revisione dell'orchestratore riceve il compito come testo (come in ciclo.esegui) e non lo indicizza."""
import os
import re
import types
import unittest

AGENTE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'bin', 'agente')


class RevisioneCompito(unittest.TestCase):
    def test_la_revisione_accetta_il_compito_come_testo(self):
        with open(AGENTE, encoding='utf-8') as f:
            testo = f.read()
        riga = re.search(r"'programmatore': lambda[^\n]*", testo).group(0)
        trovato = re.search(r"revisione=(lambda .*?, e\.lancia\))", riga)
        self.assertIsNotNone(trovato, riga)
        chiamate = []
        finto = types.SimpleNamespace(revisore=lambda c, d, l: chiamate.append((c, d, l)) or {'ok': True})
        revisione = eval(trovato.group(1), {'ruoli': finto, 'e': types.SimpleNamespace(lancia='LANCIA')})
        revisione('scrivi la funzione', '/tmp/cartella')
        self.assertEqual(chiamate, [({'agente': 'revisore', 'compito': 'scrivi la funzione'}, '/tmp/cartella', 'LANCIA')])


if __name__ == '__main__':
    unittest.main()
