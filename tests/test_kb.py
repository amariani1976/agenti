"""Test di kb/kb.py: salvataggio in inbox, lettura sicura, indice FTS5 e ricerca."""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

QUI = os.path.dirname(os.path.abspath(__file__))
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.join(QUI, '..', 'kb'))
import kb  # noqa: E402


class Base(unittest.TestCase):
    def setUp(self):
        self.kb = tempfile.mkdtemp()
        self.db = os.path.join(tempfile.mkdtemp(), 'indice.db')
        os.makedirs(os.path.join(self.kb, 'progetti'))
        with open(os.path.join(self.kb, 'progetti', 'neteye.md'), 'w') as f:
            f.write('# NetEye\n\nIl server NetEye 10.0.0.118 si usa solo in verifica.\n')
        with open(os.path.join(self.kb, 'ricetta.md'), 'w') as f:
            f.write('Pasta al pomodoro con basilico.\n')

    def tearDown(self):
        shutil.rmtree(self.kb, ignore_errors=True)
        shutil.rmtree(os.path.dirname(self.db), ignore_errors=True)


class SalvaTest(Base):
    def test_slug(self):
        self.assertEqual(kb.slug('Prova: Ollama e GPU!'), 'prova-ollama-e-gpu')
        self.assertEqual(kb.slug('   '), 'nota')

    def test_salva_in_inbox_con_intestazione(self):
        rel = kb.salva(self.kb, 'programmatore', 'Esito del banco', 'Testo.\n', progetto='agenti', oggi='2026-10-31')
        self.assertEqual(rel, 'inbox/2026-10-31-esito-del-banco.md')
        testo = open(os.path.join(self.kb, rel)).read()
        self.assertTrue(testo.startswith('---\n'))
        self.assertIn('agente: programmatore\n', testo)
        self.assertIn('progetto: agenti\n', testo)
        self.assertIn('data: 2026-10-31\n', testo)
        self.assertIn('# Esito del banco\n', testo)
        self.assertTrue(testo.endswith('Testo.\n'))

    def test_non_sovrascrive(self):
        a = kb.salva(self.kb, 'x', 'Doppia', 'uno', oggi='2026-10-31')
        b = kb.salva(self.kb, 'x', 'Doppia', 'due', oggi='2026-10-31')
        self.assertEqual(b, 'inbox/2026-10-31-doppia-2.md')
        self.assertIn('uno', open(os.path.join(self.kb, a)).read())

    def test_rifiuta_segreti(self):
        for t in ('password: abc123', 'TOKEN=ghp_' + 'a' * 36, '-----BEGIN OPENSSH PRIVATE KEY-----'):
            with self.assertRaises(ValueError):
                kb.salva(self.kb, 'x', 'Segreto', t, oggi='2026-10-31')
        self.assertFalse(os.path.exists(os.path.join(self.kb, 'inbox')))


class LeggiTest(Base):
    def test_leggi(self):
        self.assertIn('10.0.0.118', kb.leggi(self.kb, 'progetti/neteye.md'))

    def test_fuori_dalla_kb(self):
        with self.assertRaises(ValueError):
            kb.leggi(self.kb, '../../etc/passwd')
        with self.assertRaises(ValueError):
            kb.leggi(self.kb, '/etc/passwd')


class IndiceTest(Base):
    def test_indicizza_e_cerca(self):
        self.assertEqual(kb.indicizza(self.kb, self.db), 2)
        r = kb.cerca(self.db, 'verifica')
        self.assertEqual([x['path'] for x in r], ['progetti/neteye.md'])
        self.assertEqual(r[0]['titolo'], 'NetEye')
        self.assertIn('verifica', r[0]['estratto'])

    def test_titolo_dal_nome_del_file(self):
        kb.indicizza(self.kb, self.db)
        self.assertEqual(kb.cerca(self.db, 'basilico')[0]['titolo'], 'ricetta')

    def test_ricostruisce_da_zero(self):
        kb.indicizza(self.kb, self.db)
        os.remove(os.path.join(self.kb, 'ricetta.md'))
        self.assertEqual(kb.indicizza(self.kb, self.db), 1)
        self.assertEqual(kb.cerca(self.db, 'basilico'), [])

    def test_ignora_git(self):
        os.makedirs(os.path.join(self.kb, '.git'))
        with open(os.path.join(self.kb, '.git', 'x.md'), 'w') as f:
            f.write('segreto')
        self.assertEqual(kb.indicizza(self.kb, self.db), 2)


class RigaDiComandoTest(Base):
    def test_cli(self):
        env = dict(os.environ, KB_DIR=self.kb, KB_DB=self.db, PYTHONDONTWRITEBYTECODE='1')
        prog = os.path.join(QUI, '..', 'kb', 'kb.py')
        run = lambda *a, **k: subprocess.run([sys.executable, prog] + list(a), env=env, stdout=subprocess.PIPE,
                                             stderr=subprocess.STDOUT, universal_newlines=True, **k)
        self.assertEqual(run('indicizza').returncode, 0)
        r = run('cerca', 'verifica')
        self.assertEqual(r.returncode, 0)
        self.assertIn('progetti/neteye.md', r.stdout)
        r = run('salva', '--agente', 'prova', '--titolo', 'Da riga di comando', input='corpo\n')
        self.assertEqual(r.returncode, 0)
        self.assertTrue(r.stdout.strip().startswith('inbox/'))
        self.assertEqual(run('leggi', '../fuori.md').returncode, 1)


if __name__ == '__main__':
    unittest.main()
