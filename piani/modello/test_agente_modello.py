"""Il modello dell'agente si sceglie con AGENTE_MODELLO (prove di modelli diversi col banco degli agenti): vale per tutte
le chiamate, revisione compresa; di serie resta esecutore-pensiero; un nome non valido si rifiuta prima di lanciare."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_agente_catena import Catena  # noqa: E402


class Modello(Catena):
    def chiamate_agente(self):
        if not os.path.exists(self.reg):
            return []
        with open(self.reg) as f:
            return [r for r in f.read().splitlines() if r.startswith('agente ')]

    def lancia(self):
        return self.agente('programmatore', '--cartella', self.prog, '--file', 'a.py', '--verifica', 'grep -q "x = 2" a.py',
                           '--json', 'cambia x')

    def test_di_serie(self):
        self.env.pop('AGENTE_MODELLO', None)
        r = self.lancia()
        self.assertEqual(r.returncode, 0, r.stderr[-800:])
        chiamate = self.chiamate_agente()
        self.assertTrue(chiamate)
        self.assertEqual({c.split()[-1] for c in chiamate}, {'esecutore-pensiero'})

    def test_scelto_per_tutte_le_chiamate(self):
        self.env['AGENTE_MODELLO'] = 'ornith-9b-q8'
        r = self.lancia()
        self.assertEqual(r.returncode, 0, r.stderr[-800:])
        chiamate = self.chiamate_agente()
        self.assertGreaterEqual(len(chiamate), 2, 'programmatore e revisione')
        self.assertEqual({c.split()[-1] for c in chiamate}, {'ornith-9b-q8'})

    def test_nome_non_valido(self):
        for nome in ('a b', 'x;rm -rf /', '-p', ''):
            self.env['AGENTE_MODELLO'] = nome
            r = self.lancia()
            if nome == '':
                self.assertEqual(r.returncode, 0, 'vuoto vale come non impostato')
                continue
            self.assertEqual(r.returncode, 2, nome)
            self.assertIn('AGENTE_MODELLO', r.stderr)
            self.assertEqual(self.chiamate_agente(), [], nome)


# I test della catena si provano già nel loro file: qui non si ripetono.
for _n in [n for n in dir(Catena) if n.startswith('test_')]:
    setattr(Modello, _n, None)


if __name__ == '__main__':
    unittest.main()
