"""Ciclo: verifica generale, revisore nel giro, tempo massimo del compito, prompt che chiede di cambiare solo il necessario."""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'ciclo'))
import ciclo  # noqa: E402


class Qualita(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp(prefix='qual-')
        self.addCleanup(shutil.rmtree, self.d, True)
        for c in (['init', '-q'], ['config', 'user.email', 'p@esempio.invalid'], ['config', 'user.name', 'p']):
            subprocess.run(['git', '-C', self.d] + c, check=True)
        with open(os.path.join(self.d, 'a.py'), 'w') as f:
            f.write('x = 1\n')
        subprocess.run(['git', '-C', self.d, 'add', '.'], check=True)
        subprocess.run(['git', '-C', self.d, 'commit', '-qm', 'i'], check=True)
        self.prompt = []

    def lancia(self, *valori):
        def f(prompt, cartella):
            self.prompt.append(prompt)
            with open(os.path.join(cartella, 'a.py'), 'w') as g:
                g.write(valori[min(len(self.prompt), len(valori)) - 1])
            return 0, 'ok'
        return f

    def ok(self, comando, cartella):
        return 0, 'OK'

    def test_la_verifica_generale_rotta_fa_ritentare(self):
        globali = iter([(1, 'FAIL: test_altro'), (0, 'OK')])
        r = ciclo.esegui('cambia x', self.d, 'prova', ['a.py'], lancia=self.lancia('x = 9\n', 'x = 2\n'),
                         verifica_fn=lambda c, d: next(globali) if c == 'globale' else (0, 'OK'), verifica_globale='globale')
        self.assertEqual(r['esito'], 'fatto')
        self.assertEqual(len(r['tentativi']), 2)
        self.assertIn('FAIL: test_altro', self.prompt[1])

    def test_il_revisore_fa_ritentare_con_i_difetti(self):
        esiti = iter([{'ok': False, 'difetti': ['manca il caso vuoto']}, {'ok': True, 'difetti': []}])
        visti = []
        r = ciclo.esegui('cambia x', self.d, 'prova', ['a.py'], lancia=self.lancia('x = 9\n', 'x = 2\n'), verifica_fn=self.ok,
                         revisione=lambda compito, cartella: (visti.append(compito), next(esiti))[1])
        self.assertEqual(r['esito'], 'fatto')
        self.assertEqual(len(r['tentativi']), 2)
        self.assertIn('manca il caso vuoto', self.prompt[1])
        self.assertEqual(visti[0], 'cambia x')

    def test_difetti_fino_all_ultimo_tentativo_non_si_consegna(self):
        r = ciclo.esegui('cambia x', self.d, 'prova', ['a.py'], tentativi=2, lancia=self.lancia('x = 9\n'), verifica_fn=self.ok,
                         revisione=lambda compito, cartella: {'ok': False, 'difetti': ['sbagliato']})
        self.assertEqual(r['esito'], 'non-fatto')
        self.assertIn('sbagliato', r['motivo'])
        with open(os.path.join(self.d, 'a.py')) as f:
            self.assertEqual(f.read(), 'x = 1\n')

    def test_revisione_senza_esito_non_ferma(self):
        r = ciclo.esegui('cambia x', self.d, 'prova', ['a.py'], lancia=self.lancia('x = 2\n'), verifica_fn=self.ok,
                         revisione=lambda compito, cartella: {'esito': 'non-fatto', 'motivo': 'risposta illeggibile'})
        self.assertEqual(r['esito'], 'fatto')
        self.assertIn('revisione', r)

    def test_tempo_massimo_del_compito(self):
        tempi = iter([0, 0, 5000, 5000, 5000, 5000, 5000, 5000])
        r = ciclo.esegui('cambia x', self.d, 'prova', ['a.py'], tentativi=3, lancia=self.lancia('x = 9\n'),
                         verifica_fn=lambda c, d: (1, 'no'), tempo_max=1800, orologio=lambda: next(tempi))
        self.assertEqual(r['esito'], 'non-fatto')
        self.assertEqual(len(r['tentativi']), 1)
        self.assertIn('tempo', r['motivo'])

    def test_il_prompt_chiede_solo_il_necessario(self):
        ciclo.esegui('cambia x', self.d, 'prova', ['a.py'], lancia=self.lancia('x = 2\n'), verifica_fn=self.ok)
        p = self.prompt[0]
        self.assertIn('solo quello che il compito chiede', p)
        self.assertIn('comando', p)


if __name__ == '__main__':
    unittest.main()
