"""L'agente chiede i nomi generici: esecutore (senza ragionamento) e esecutore-pensiero solo nei tentativi dopo un
errore. Il modello vero si sceglie solo in /opt/ai-vm/modelli.json (lo traduce il proxy). Nessuna variabile lo cambia."""
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
        self.assertEqual({c.split()[-1] for c in chiamate}, {'esecutore'})

    def test_variabile_ignorata(self):
        self.env['AGENTE_MODELLO'] = 'ornith-9b-q8'
        r = self.lancia()
        self.assertEqual(r.returncode, 0, r.stderr[-800:])
        chiamate = self.chiamate_agente()
        self.assertGreaterEqual(len(chiamate), 2, 'programmatore e revisione')
        self.assertEqual({c.split()[-1] for c in chiamate}, {'esecutore'})


class ModelloPerPrompt(unittest.TestCase):
    def test_prima_senza_poi_con(self):
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'ciclo'))
        import esecuzione
        self.assertEqual(esecuzione.modello_per('Compito: fai x'), 'esecutore')
        self.assertEqual(esecuzione.modello_per('Compito: fai x\n\nErrore della verifica nel tentativo precedente:\nboom'), 'esecutore-pensiero')
        self.assertEqual(esecuzione.modello_per('Difetti rilevati dalla revisione:\n- a'), 'esecutore-pensiero')


# I test della catena si provano già nel loro file: qui non si ripetono.
for _n in [n for n in dir(Catena) if n.startswith('test_')]:
    setattr(Modello, _n, None)


if __name__ == '__main__':
    unittest.main()
