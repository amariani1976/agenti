"""Dall'orchestratore il programmatore usa anche il revisore: lo stesso ciclo del comando diretto."""
import os
import re
import unittest

AGENTE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'bin', 'agente')


class Revisione(unittest.TestCase):
    def test_il_programmatore_dell_orchestratore_ha_la_revisione(self):
        with open(AGENTE, encoding='utf-8') as f:
            testo = f.read()
        riga = re.search(r"'programmatore': lambda[^\n]*", testo).group(0)
        self.assertIn('revisione=', riga)
        self.assertIn('ruoli.revisore', riga)


if __name__ == '__main__':
    unittest.main()
