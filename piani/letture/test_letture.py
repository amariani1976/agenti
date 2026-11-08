"""Le tre letture del revisore sono una costante pubblica della libreria (la usa anche il runner di AI-VM), e il revisore
le usa tutte, una per chiamata, nell'ordine."""
import json
import os
import subprocess
import sys
import tempfile
import shutil
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'ciclo'))
import ruoli  # noqa: E402


class Letture(unittest.TestCase):
    def test_costante(self):
        self.assertIsInstance(ruoli.LETTURE, tuple)
        self.assertEqual(len(ruoli.LETTURE), 3)
        for testo in ruoli.LETTURE:
            self.assertIsInstance(testo, str)
            self.assertGreater(len(testo), 40)
        self.assertIn('richieste', ruoli.LETTURE[0])
        self.assertIn('runtime', ' '.join(ruoli.LETTURE[1].split()).replace('quando il codice gira', 'runtime'))
        self.assertIn('oltre', ruoli.LETTURE[2])

    def test_il_revisore_le_usa_in_ordine(self):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)
        subprocess.run(['git', 'init', '-q', d], check=True)
        with open(os.path.join(d, 'a.py'), 'w') as f:
            f.write('x = 1\n')
        visti = []

        def lancia(prompt, cartella):
            visti.append(prompt)
            return 0, json.dumps({'richieste': [], 'ok': True, 'difetti': []})
        r = ruoli.revisore({'compito': 'crea a.py'}, d, lancia)
        self.assertEqual(r['esito'], 'fatto')
        self.assertEqual(len(visti), 3)
        for prompt, lettura in zip(visti, ruoli.LETTURE):
            self.assertIn(lettura, prompt)


if __name__ == '__main__':
    unittest.main()
