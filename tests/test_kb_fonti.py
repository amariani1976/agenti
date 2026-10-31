"""Test delle aggiunte a kb/kb.py per la parte 2: fonti esterne, campi extra, fonte nei risultati."""
import os
import shutil
import sys
import tempfile
import unittest

QUI = os.path.dirname(os.path.abspath(__file__))
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.join(QUI, '..', 'kb'))
import kb  # noqa: E402


class FontiTest(unittest.TestCase):
    def setUp(self):
        self.kb = tempfile.mkdtemp()
        self.fonte = tempfile.mkdtemp()
        self.db = os.path.join(tempfile.mkdtemp(), 'indice.db')
        with open(os.path.join(self.kb, 'nota.md'), 'w') as f:
            f.write('# Nota\n\nIl motore usa llama-swap.\n')
        os.makedirs(os.path.join(self.fonte, 'docs'))
        with open(os.path.join(self.fonte, 'docs', 'GUIDA.md'), 'w') as f:
            f.write('# Guida AI-VM\n\nSearXNG risponde sulla porta 8888.\n')

    def tearDown(self):
        for d in (self.kb, self.fonte, os.path.dirname(self.db)):
            shutil.rmtree(d, ignore_errors=True)

    def test_indicizza_con_fonti(self):
        self.assertEqual(kb.indicizza(self.kb, self.db, {'aivm': self.fonte}), 2)
        r = kb.cerca(self.db, 'SearXNG')
        self.assertEqual(r[0]['path'], '@aivm/docs/GUIDA.md')
        self.assertEqual(r[0]['fonte'], 'aivm')
        self.assertEqual(r[0]['titolo'], 'Guida AI-VM')
        self.assertEqual(kb.cerca(self.db, 'llama')[0]['fonte'], 'kb')

    def test_senza_fonti_come_prima(self):
        self.assertEqual(kb.indicizza(self.kb, self.db), 1)

    def test_leggi_da_fonte(self):
        self.assertIn('8888', kb.leggi(self.kb, '@aivm/docs/GUIDA.md', {'aivm': self.fonte}))

    def test_leggi_fonte_sicura(self):
        with self.assertRaises(ValueError):
            kb.leggi(self.kb, '@aivm/../../etc/passwd', {'aivm': self.fonte})
        with self.assertRaises(ValueError):
            kb.leggi(self.kb, '@manca/x.md', {'aivm': self.fonte})
        with self.assertRaises(ValueError):
            kb.leggi(self.kb, '@aivm/docs/GUIDA.md')

    def test_cerca_parole_strane(self):
        kb.indicizza(self.kb, self.db)
        self.assertEqual(kb.cerca(self.db, 'llama-swap "OR'), kb.cerca(self.db, 'llama swap OR'))
        self.assertEqual(kb.cerca(self.db, '   '), [])
        self.assertEqual(kb.cerca(os.path.join(self.kb, 'manca.db'), 'x'), [])

    def test_salva_extra(self):
        rel = kb.salva(self.kb, 'web', 'Da internet', 'sintesi\n', oggi='2026-10-31',
                       extra={'fonte': 'web', 'url': 'https://example.org/a', 'stato': 'da-verificare'})
        testo = open(os.path.join(self.kb, rel)).read()
        intestazione = testo.split('---\n')[1]
        self.assertIn('fonte: web\n', intestazione)
        self.assertIn('url: https://example.org/a\n', intestazione)
        self.assertIn('stato: da-verificare\n', intestazione)

    def test_salva_extra_non_valido(self):
        with self.assertRaises(ValueError):
            kb.salva(self.kb, 'x', 'T', 'y', extra={'url': 'a\nagente: falso'})
        with self.assertRaises(ValueError):
            kb.salva(self.kb, 'x', 'T', 'y', extra={'Chiave Strana': 'v'})

    def test_segreto_nel_titolo(self):
        with self.assertRaises(ValueError):
            kb.salva(self.kb, 'x', 'password: abc', 'y')


if __name__ == '__main__':
    unittest.main()
