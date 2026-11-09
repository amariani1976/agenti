"""Test del collaudo 1: riga di comando e ricerca di kb/kb.py."""
import importlib.machinery
import importlib.util
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

QUI = os.path.dirname(os.path.abspath(__file__))
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.join(QUI, '..', 'kb'))
import kb  # noqa: E402

AGENTE = os.path.join(QUI, '..', 'bin', 'agente')
KBPY = os.path.join(QUI, '..', 'kb', 'kb.py')


class KbCollaudoTest(unittest.TestCase):
    def setUp(self):
        self.kb = tempfile.mkdtemp()
        self.casa = tempfile.mkdtemp()
        lungo = 'parola ' * 60
        for nome, testo in (('a.md', '# A\n\n' + lungo + 'verifica uno\n'), ('b.md', '# B\n\nverifica due\n'),
                            ('c.md', '## Sezione\n\nverifica tre\n'),
                            ('d.md', '# D\n\n' + lungo + 'alfa ' + lungo + 'omega\n')):
            with open(os.path.join(self.kb, nome), 'w') as f:
                f.write(testo)

    def tearDown(self):
        shutil.rmtree(self.kb, ignore_errors=True)
        shutil.rmtree(self.casa, ignore_errors=True)

    def esegui(self, *argomenti, **k):
        env = dict(os.environ, KB_DIR=self.kb, HOME=self.casa, PYTHONDONTWRITEBYTECODE='1')
        env.pop('KB_DB', None)
        return subprocess.run([sys.executable, KBPY] + list(argomenti), env=env, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, universal_newlines=True, **k)

    def test_db_predefinito_in_cache(self):
        self.assertEqual(self.esegui('indicizza').returncode, 0)
        self.assertTrue(os.path.isfile(os.path.join(self.casa, '.cache', 'kb', 'indice.db')))

    def test_kb_dir_predefinita(self):
        with open(KBPY) as f:
            self.assertIn("'/srv/kb'", f.read())

    def test_cerca_con_n(self):
        self.esegui('indicizza')
        for argomenti in (('cerca', 'verifica', '-n', '1'), ('cerca', '-n', '1', 'verifica')):
            r = self.esegui(*argomenti)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(len(re.findall(r'(?m)^\S+\.md: ', r.stdout)), 1, r.stdout)

    def test_salva_segreto_messaggio_e_uscita_1(self):
        r = self.esegui('salva', '--agente', 'x', '--titolo', 'T', input='password: abc\n')
        self.assertEqual(r.returncode, 1)
        self.assertIn('segreto', r.stderr)
        self.assertNotIn('Traceback', r.stderr)
        self.assertFalse(os.path.exists(os.path.join(self.kb, 'inbox')))

    def test_salva_senza_titolo_errore(self):
        r = self.esegui('salva', '--agente', 'x', input='corpo\n')
        self.assertNotEqual(r.returncode, 0)
        self.assertFalse(os.path.exists(os.path.join(self.kb, 'inbox')))

    def test_titolo_solo_da_riga_h1(self):
        db = os.path.join(self.casa, 'i.db')
        kb.indicizza(self.kb, db)
        self.assertEqual(kb.cerca(db, 'tre')[0]['titolo'], 'c')

    def test_estratto_con_snippet(self):
        db = os.path.join(self.casa, 'i.db')
        kb.indicizza(self.kb, db)
        r = kb.cerca(db, 'alfa omega')
        self.assertEqual([x['path'] for x in r], ['d.md'])
        self.assertIn('alfa', r[0]['estratto'])
        self.assertLess(len(r[0]['estratto']), 200)


if __name__ == '__main__':
    unittest.main()
