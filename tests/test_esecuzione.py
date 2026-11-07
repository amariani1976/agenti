"""Esecuzione reale del ciclo: agente e verifica passano da esegui-passo (utente esecutore, rete chiusa)."""
import os
import shutil
import stat
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'ciclo'))
import esecuzione  # noqa: E402

FINTO = """#!/bin/sh
echo "$@" > "$REGISTRO"
cat >> "$REGISTRO"
echo uscita-finta
exit $CODICE
"""


class Esecuzione(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp(prefix='esec-')
        self.addCleanup(shutil.rmtree, self.d, True)
        self.finto = os.path.join(self.d, 'esegui-passo')
        with open(self.finto, 'w') as f:
            f.write(FINTO)
        os.chmod(self.finto, stat.S_IRWXU)
        self.reg = os.path.join(self.d, 'reg')
        os.environ.update({'REGISTRO': self.reg, 'CODICE': '0'})
        self.radice = os.path.join(self.d, 'progetti')
        os.makedirs(os.path.join(self.radice, 'demo'))

    def e(self):
        return esecuzione.Esecuzione(radice=self.radice, esegui=[self.finto], modello='esecutore-pensiero')

    def test_progetto_dalla_cartella(self):
        self.assertEqual(self.e().progetto(os.path.join(self.radice, 'demo')), 'demo')
        for fuori in (self.d, os.path.join(self.radice, 'demo', 'sotto'), '/etc'):
            with self.assertRaises(ValueError):
                self.e().progetto(fuori)

    def test_lancia_passa_dal_programma_col_modello(self):
        codice, uscita = self.e().lancia('il compito', os.path.join(self.radice, 'demo'))
        self.assertEqual((codice, uscita.strip()), (0, 'uscita-finta'))
        with open(self.reg) as f:
            righe = f.read().splitlines()
        self.assertEqual(righe[0], 'agente demo esecutore-pensiero')
        self.assertIn('il compito', righe[1:])

    def test_verifica_passa_dal_programma(self):
        os.environ['CODICE'] = '3'
        codice, _ = self.e().verifica('npm test', os.path.join(self.radice, 'demo'))
        self.assertEqual(codice, 3)
        with open(self.reg) as f:
            righe = f.read().splitlines()
        self.assertEqual(righe[0], 'verifica demo')
        self.assertEqual(righe[1], 'npm test')


if __name__ == '__main__':
    unittest.main()
