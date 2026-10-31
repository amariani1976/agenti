"""Test di kb/kb.py come client del servizio (variabili KB_URL e KB_TOKEN) e del campo --campo."""
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest

QUI = os.path.dirname(os.path.abspath(__file__))
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.join(QUI, '..', 'kb'))
import servizio  # noqa: E402

TOKEN = 'token-di-prova-0123456789'
PROG = os.path.join(QUI, '..', 'kb', 'kb.py')


class ClienteTest(unittest.TestCase):
    def setUp(self):
        self.kb = tempfile.mkdtemp()
        self.db = os.path.join(tempfile.mkdtemp(), 'indice.db')
        with open(os.path.join(self.kb, 'neteye.md'), 'w') as f:
            f.write('# NetEye\n\nSolo verifica sul server.\n')
        self.srv = servizio.crea(servizio.Kb(self.kb, self.db, {}, TOKEN), '127.0.0.1', 0)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.env = dict(os.environ, KB_URL='http://127.0.0.1:%d' % self.srv.server_address[1], KB_TOKEN=TOKEN,
                        KB_DIR='/inesistente', KB_DB='/inesistente/x.db', PYTHONDONTWRITEBYTECODE='1')

    def tearDown(self):
        self.srv.shutdown()
        self.srv.server_close()
        shutil.rmtree(self.kb, ignore_errors=True)
        shutil.rmtree(os.path.dirname(self.db), ignore_errors=True)

    def run_kb(self, *a, env=None, **k):
        return subprocess.run([sys.executable, PROG] + list(a), env=env or self.env, capture_output=True,
                              text=True, timeout=30, **k)

    def test_cerca_remota(self):
        r = self.run_kb('cerca', 'verifica')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('neteye.md: NetEye', r.stdout)

    def test_leggi_remota(self):
        r = self.run_kb('leggi', 'neteye.md')
        self.assertEqual((r.returncode, 'Solo verifica' in r.stdout), (0, True))
        r = self.run_kb('leggi', '../fuori.md')
        self.assertEqual(r.returncode, 1)
        self.assertIn('fuori', r.stderr)

    def test_salva_remota_con_campi(self):
        r = self.run_kb('salva', '--agente', 'web', '--titolo', 'Da internet', '--campo', 'fonte=web',
                        '--campo', 'url=https://example.org/x?a=1', input='sintesi\n')
        self.assertEqual(r.returncode, 0, r.stderr)
        rel = r.stdout.strip()
        testo = open(os.path.join(self.kb, rel)).read()
        self.assertIn('fonte: web\n', testo)
        self.assertIn('url: https://example.org/x?a=1\n', testo)

    def test_token_sbagliato(self):
        r = self.run_kb('cerca', 'x', env=dict(self.env, KB_TOKEN='sbagliato'))
        self.assertEqual(r.returncode, 1)
        self.assertIn('non autorizzato', r.stderr)

    def test_servizio_spento(self):
        r = self.run_kb('cerca', 'x', env=dict(self.env, KB_URL='http://127.0.0.1:9'))
        self.assertEqual(r.returncode, 1)
        self.assertTrue(r.stderr.startswith('kb: '))

    def test_locale_con_campi(self):
        env = dict(os.environ, KB_DIR=self.kb, KB_DB=self.db, PYTHONDONTWRITEBYTECODE='1')
        env.pop('KB_URL', None)
        r = self.run_kb('salva', '--agente', 'x', '--titolo', 'Locale', '--campo', 'stato=da-verificare',
                        env=env, input='t\n')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('stato: da-verificare\n', open(os.path.join(self.kb, r.stdout.strip())).read())


if __name__ == '__main__':
    unittest.main()
