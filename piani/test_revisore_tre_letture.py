"""Revisore: tre letture con un compito diverso ciascuna (richieste, errori a runtime, cambi oltre il richiesto)."""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'ciclo'))
import ruoli  # noqa: E402

OK = '{"richieste": [], "ok": true, "difetti": []}'


class TreLetture(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp(prefix='tre-')
        self.addCleanup(shutil.rmtree, self.d, True)
        for c in (['init', '-q'], ['config', 'user.email', 'p@esempio.invalid'], ['config', 'user.name', 'p']):
            subprocess.run(['git', '-C', self.d] + c, check=True)
        with open(os.path.join(self.d, 'a.py'), 'w') as f:
            f.write('x = 1\n')
        subprocess.run(['git', '-C', self.d, 'add', '.'], check=True)
        subprocess.run(['git', '-C', self.d, 'commit', '-qm', 'i'], check=True)
        with open(os.path.join(self.d, 'a.py'), 'w') as f:
            f.write('x = 2\n')

    def rev(self, *risposte):
        risposte = list(risposte)
        self.prompt = []

        def lancia(p, c):
            self.prompt.append(p)
            return 0, risposte.pop(0)
        return ruoli.revisore({'agente': 'revisore', 'compito': 'metti x a 2'}, self.d, lancia)

    def test_tre_letture_con_tre_compiti(self):
        r = self.rev(OK, OK, OK)
        self.assertIs(r['ok'], True)
        self.assertEqual(len(self.prompt), 3)
        self.assertIn('una per una', self.prompt[0])
        self.assertIn('quando il codice gira', self.prompt[1])
        self.assertIn('oltre quello che il compito chiede', self.prompt[2])
        for p in self.prompt:
            self.assertIn('metti x a 2', p)
            self.assertIn('+x = 2', p)

    def test_basta_un_difetto_in_una_lettura(self):
        r = self.rev(OK, '{"richieste": [], "ok": false, "difetti": ["peek non esiste su GzipFile"]}', OK)
        self.assertIs(r['ok'], False)
        self.assertEqual(r['difetti'], ['peek non esiste su GzipFile'])

    def test_letture_illeggibili(self):
        self.assertIs(self.rev('no', OK, 'no')['ok'], True)
        self.assertEqual(self.rev('no', 'no', 'no')['esito'], 'non-fatto')


if __name__ == '__main__':
    unittest.main()
