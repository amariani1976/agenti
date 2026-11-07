"""Ruoli: il revisore non scrive nulla e risponde in JSON; il programmatore usa il ciclo."""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'ciclo'))
import ruoli  # noqa: E402


def git(d, *a):
    subprocess.run(['git', '-C', d] + list(a), check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


class Ruoli(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp(prefix='ruoli-')
        self.addCleanup(shutil.rmtree, self.d, True)
        git(self.d, 'init', '-q')
        git(self.d, 'config', 'user.email', 'p@esempio.invalid')
        git(self.d, 'config', 'user.name', 'p')
        with open(os.path.join(self.d, 'a.py'), 'w') as f:
            f.write('x = 1\n')
        git(self.d, 'add', '.')
        git(self.d, 'commit', '-qm', 'i')

    def test_revisore_in_sola_lettura(self):
        def lancia(prompt, cartella):
            with open(os.path.join(cartella, 'a.py'), 'w') as f:
                f.write('rotto\n')
            with open(os.path.join(cartella, 'nuovo.py'), 'w') as f:
                f.write('x\n')
            return 0, 'Esito:\n```json\n{"ok": false, "difetti": ["manca un test"]}\n```'
        r = ruoli.revisore({'agente': 'revisore', 'compito': 'rivedi'}, self.d, lancia=lancia)
        self.assertEqual(r, {'esito': 'fatto', 'ok': False, 'difetti': ['manca un test'], 'scritture_annullate': ['a.py', 'nuovo.py']})
        with open(os.path.join(self.d, 'a.py')) as f:
            self.assertEqual(f.read(), 'x = 1\n')
        self.assertFalse(os.path.exists(os.path.join(self.d, 'nuovo.py')))

    def test_revisore_vede_il_diff(self):
        with open(os.path.join(self.d, 'a.py'), 'w') as f:
            f.write('x = 2\n')
        visti = []
        ruoli.revisore({'agente': 'revisore', 'compito': 'rivedi'}, self.d, lancia=lambda p, c: (visti.append(p), (0, '{"ok": true, "difetti": []}'))[1])
        self.assertIn('+x = 2', visti[0])
        with open(os.path.join(self.d, 'a.py')) as f:
            self.assertEqual(f.read(), 'x = 2\n')

    def test_revisore_risposta_illeggibile(self):
        r = ruoli.revisore({'agente': 'revisore', 'compito': 'rivedi'}, self.d, lancia=lambda p, c: (0, 'non so'))
        self.assertEqual(r['esito'], 'non-fatto')

    def test_programmatore_usa_il_ciclo(self):
        chiamato = {}

        def ciclo_finto(compito, cartella, verifica, file, **k):
            chiamato.update(compito=compito, verifica=verifica, file=file)
            return {'esito': 'fatto', 'tentativi': [], 'file': file, 'diff': '+x'}
        r = ruoli.programmatore({'agente': 'programmatore', 'compito': 'scrivi', 'file': ['a.py'], 'verifica': 'v'}, self.d, esegui=ciclo_finto)
        self.assertEqual(r['esito'], 'fatto')
        self.assertEqual(chiamato, {'compito': 'scrivi', 'verifica': 'v', 'file': ['a.py']})


if __name__ == '__main__':
    unittest.main()
