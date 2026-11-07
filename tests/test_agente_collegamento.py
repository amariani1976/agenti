"""bin/agente lanciato da un collegamento simbolico trova profili e moduli in ogni percorso (realpath in tutto il file)."""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

AGENTE = os.path.realpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'bin', 'agente'))


class Collegamento(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp(prefix='collegamento-')
        self.link = os.path.join(self.d, 'agente')
        os.symlink(AGENTE, self.link)
        self.pi = os.path.join(self.d, 'pi-finto')
        with open(self.pi, 'w') as f:
            f.write('#!/bin/sh\necho PI-FINTO "$@"\n')
        os.chmod(self.pi, 0o755)
        self.env = {k: v for k, v in os.environ.items() if k not in ('AGENTE_RADICE', 'AGENTE_ESEGUI', 'AGENTE_PROGETTI')}
        self.env['AGENTE_PI'] = self.pi

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)

    def lancia(self, *argomenti):
        return subprocess.run([sys.executable, self.link] + list(argomenti), env=self.env, cwd=self.d,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, timeout=60)

    def test_percorso_semplice_trova_il_profilo(self):
        r = self.lancia('programmatore', '--cartella', self.d, 'ciao')
        self.assertEqual(r.returncode, 0, r.stderr[-500:])
        self.assertIn('PI-FINTO', r.stdout)

    def test_orchestratore_trova_i_moduli(self):
        self.env['AGENTE_PROGETTI'] = self.d
        r = self.lancia('orchestratore', '--cartella', '/', 'fai qualcosa')
        self.assertNotIn('ModuleNotFoundError', r.stderr)
        self.assertNotIn('Traceback', r.stderr)
        self.assertEqual(r.returncode, 2, r.stderr[-500:])


if __name__ == '__main__':
    unittest.main()
