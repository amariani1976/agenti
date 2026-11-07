"""Il revisore controlla anche come è scritto il codice: librerie, riuso, niente duplicati."""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'ciclo'))
import ruoli  # noqa: E402


class Regole(unittest.TestCase):
    def test_il_prompt_contiene_le_regole_e_le_funzioni_esistenti(self):
        d = tempfile.mkdtemp(prefix='rev-')
        self.addCleanup(shutil.rmtree, d, True)
        for c in (['init', '-q'], ['config', 'user.email', 'p@esempio.invalid'], ['config', 'user.name', 'p']):
            subprocess.run(['git', '-C', d] + c, check=True)
        os.makedirs(os.path.join(d, 'lib'))
        with open(os.path.join(d, 'lib', 'utili.py'), 'w') as f:
            f.write('def somma(a, b):\n    return a + b\n')
        subprocess.run(['git', '-C', d, 'add', '.'], check=True)
        subprocess.run(['git', '-C', d, 'commit', '-qm', 'i'], check=True)
        with open(os.path.join(d, 'nuovo.py'), 'w') as f:
            f.write('def somma2(a, b):\n    return a + b\n')
        visti = []
        ruoli.revisore({'agente': 'revisore', 'compito': 'rivedi'}, d, lancia=lambda p, c: (visti.append(p), (0, '{"ok": true, "difetti": []}'))[1])
        p = visti[0]
        for atteso in ('librerie', 'riusa', 'duplica', 'def somma'):
            self.assertIn(atteso, p, atteso)


if __name__ == '__main__':
    unittest.main()
