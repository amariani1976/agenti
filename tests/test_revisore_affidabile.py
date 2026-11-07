"""Revisore affidabile: richiesta per richiesta, e due letture che devono essere entrambe ok."""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'ciclo'))
import ruoli  # noqa: E402


class Affidabile(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp(prefix='aff-')
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
        return ruoli.revisore({'agente': 'revisore', 'compito': 'metti x a 2 e aggiungi y'}, self.d, lancia)

    def test_basta_una_lettura_con_difetti(self):
        r = self.rev('{"richieste": [], "ok": true, "difetti": []}', '{"richieste": [{"richiesta": "y", "fatta": false}], "ok": false, "difetti": ["manca y"]}', '{"richieste": [{"richiesta": "y", "fatta": false}], "ok": false, "difetti": ["manca y"]}')
        self.assertIs(r['ok'], False)
        self.assertEqual(r['difetti'], ['manca y'])
        self.assertEqual(len(self.prompt), 3)

    def test_due_letture_ok(self):
        r = self.rev('{"richieste": [{"richiesta": "x", "fatta": true}], "ok": true, "difetti": []}',
                     '{"richieste": [{"richiesta": "x", "fatta": true}], "ok": true, "difetti": []}',
                     '{"richieste": [{"richiesta": "x", "fatta": true}], "ok": true, "difetti": []}')
        self.assertIs(r['ok'], True)

    def test_una_richiesta_non_fatta_vale_come_difetto(self):
        r = self.rev('{"richieste": [{"richiesta": "aggiungi y", "fatta": false}], "ok": true, "difetti": []}',
                     '{"richieste": [{"richiesta": "aggiungi y", "fatta": false}], "ok": true, "difetti": []}',
                     '{"richieste": [{"richiesta": "aggiungi y", "fatta": false}], "ok": true, "difetti": []}')
        self.assertIs(r['ok'], False)
        self.assertIn('aggiungi y', ' '.join(r['difetti']))

    def test_il_prompt_chiede_le_richieste_una_per_una(self):
        self.rev('{"richieste": [], "ok": true, "difetti": []}', '{"richieste": [], "ok": true, "difetti": []}', '{"richieste": [], "ok": true, "difetti": []}')
        self.assertIn('"richieste"', self.prompt[0])
        self.assertIn('una per una', self.prompt[0])

    def test_una_lettura_illeggibile_conta_l_altra(self):
        r = self.rev('non so', '{"richieste": [], "ok": true, "difetti": []}', '{"richieste": [], "ok": true, "difetti": []}')
        self.assertIs(r['ok'], True)


if __name__ == '__main__':
    unittest.main()
