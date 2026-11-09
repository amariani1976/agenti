"""bin/agente: nessun percorso diretto. pi gira solo attraverso esegui-passo (agente con verifica o orchestratore),
come utente «esecutore» e con la stessa logica del runner dei piani."""
import os
import subprocess
import sys
import tempfile
import unittest

AGENTE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'bin', 'agente')


class SenzaPercorsoDiretto(unittest.TestCase):
    def lancia(self, *a):
        finto = os.path.join(tempfile.mkdtemp(), 'pi-finto')
        with open(finto, 'w') as f:
            f.write('#!/bin/sh\necho PI-LANCIATO\n')
        os.chmod(finto, 0o755)
        return subprocess.run([sys.executable, AGENTE] + list(a), env=dict(os.environ, AGENTE_PI=finto),
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, timeout=60)

    def test_rifiutato(self):
        r = self.lancia('programmatore', '--cartella', '/tmp', 'fai X')
        self.assertEqual(r.returncode, 2)
        self.assertIn('--verifica', r.stderr)
        self.assertNotIn('PI-LANCIATO', r.stdout, 'pi non parte fuori da esegui-passo')

    def test_nome_non_valido_con_verifica(self):
        r = self.lancia('../x', '--cartella', '/tmp', '--file', 'a.py', '--verifica', 'true', 'fai X')
        self.assertEqual(r.returncode, 2)
        self.assertIn('non valido', r.stderr)


if __name__ == '__main__':
    unittest.main()
