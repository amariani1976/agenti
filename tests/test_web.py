"""Test di web/web.py: ricerca con SearXNG, lettura delle pagine, blocco degli indirizzi locali, limiti d'uso.
Nessun accesso alla rete: scaricamento e risoluzione dei nomi sono finti."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

QUI = os.path.dirname(os.path.abspath(__file__))
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.join(QUI, '..', 'web'))
import web  # noqa: E402

PAGINA = '''<html><head><title> Guida  di prova </title><style>.x{}</style></head><body>
<nav>Menu Home Contatti</nav><header>Testata</header>
<h1>Installare</h1><p>Primo   paragrafo
con a capo.</p><script>alert(1)</script>
<ul><li>uno</li><li>due</li></ul><h2>Note</h2><p>Fine &amp; saluti.</p>
<footer>Copyright</footer></body></html>'''


def risolvi_finto(tabella):
    def r(host, porta):
        if host not in tabella:
            raise web.socket.gaierror('sconosciuto')
        return [(2, 1, 6, '', (ip, 0)) for ip in tabella[host]]
    return r


PUBBLICO = risolvi_finto({'example.org': ['93.184.215.14'], 'altro.org': ['2606:4700::6810:84e5'],
                          'casa.lan': ['10.0.0.100'], 'misto.org': ['93.184.215.14', '127.0.0.1'],
                          'v6locale.org': ['fe80::1']})


class EstraiTest(unittest.TestCase):
    def test_estrai(self):
        titolo, testo = web.estrai(PAGINA)
        self.assertEqual(titolo, 'Guida di prova')
        self.assertEqual(testo, '# Installare\n\nPrimo paragrafo con a capo.\n\n- uno\n- due\n\n## Note\n\nFine & saluti.')

    def test_pre_mantiene_le_righe(self):
        _, testo = web.estrai('<p>Esempio:</p><pre>def f():\n    return 1\n</pre><p>fine</p>')
        self.assertEqual(testo, 'Esempio:\n\ndef f():\n    return 1\n\nfine')


class IndirizziTest(unittest.TestCase):
    def test_permessi(self):
        self.assertTrue(web.indirizzo_permesso('example.org', PUBBLICO))
        self.assertTrue(web.indirizzo_permesso('altro.org', PUBBLICO))

    def test_bloccati(self):
        for h in ('casa.lan', 'misto.org', 'v6locale.org', 'inesistente.org'):
            self.assertFalse(web.indirizzo_permesso(h, PUBBLICO), h)


class LeggiTest(unittest.TestCase):
    def test_leggi_html(self):
        visti = []
        def sc(url):
            visti.append(url)
            return 200, {'Content-Type': 'text/html; charset=utf-8'}, PAGINA.encode()
        r = web.leggi('https://example.org/guida', scarica=sc, risolvi=PUBBLICO)
        self.assertEqual(r['titolo'], 'Guida di prova')
        self.assertTrue(r['testo'].startswith('# Installare'))
        self.assertEqual(visti, ['https://example.org/guida'])

    def test_tronca(self):
        sc = lambda url: (200, {'Content-Type': 'text/plain'}, b'a' * 50)
        r = web.leggi('https://example.org/x.txt', max_car=10, scarica=sc, risolvi=PUBBLICO)
        self.assertEqual(r['testo'], 'a' * 10 + '\n\n[… troncato a 10 caratteri]')

    def test_redirect_controllato(self):
        def sc(url):
            if url == 'https://example.org/a':
                return 302, {'Location': '/b'}, b''
            if url == 'https://example.org/b':
                return 301, {'location': 'http://casa.lan/segreto'}, b''
            self.fail('non doveva scaricare ' + url)
        with self.assertRaises(ValueError) as e:
            web.leggi('https://example.org/a', scarica=sc, risolvi=PUBBLICO)
        self.assertIn('casa.lan', str(e.exception))

    def test_redirect_ok(self):
        def sc(url):
            if url == 'https://example.org/a':
                return 302, {'Location': 'https://altro.org/b'}, b''
            return 200, {'Content-Type': 'text/plain'}, b'arrivato'
        r = web.leggi('https://example.org/a', scarica=sc, risolvi=PUBBLICO)
        self.assertEqual((r['url'], r['testo']), ('https://altro.org/b', 'arrivato'))

    def test_rifiuti(self):
        sc = lambda url: self.fail('non doveva scaricare')
        for u in ('file:///etc/passwd', 'ftp://example.org/x', 'https://utente:pw@example.org/', 'http://casa.lan/'):
            with self.assertRaises(ValueError):
                web.leggi(u, scarica=sc, risolvi=PUBBLICO)

    def test_errori(self):
        with self.assertRaises(ValueError):
            web.leggi('https://example.org/', scarica=lambda u: (404, {}, b''), risolvi=PUBBLICO)
        with self.assertRaises(ValueError):
            web.leggi('https://example.org/x.zip', scarica=lambda u: (200, {'Content-Type': 'application/zip'}, b'PK'),
                      risolvi=PUBBLICO)


class CercaTest(unittest.TestCase):
    def test_cerca(self):
        visti = []
        risposta = {'results': [
            {'title': 'Uno', 'url': 'https://a.org/1', 'content': 'primo'},
            {'title': 'Doppio', 'url': 'https://a.org/1', 'content': 'stesso url'},
            {'title': 'Strano', 'url': 'javascript:alert(1)', 'content': ''},
            {'title': ' Due \n', 'url': 'https://b.org/2', 'content': 'x' * 500},
            {'title': 'Tre', 'url': 'https://c.org/3'}]}
        def sc(url):
            visti.append(url)
            return 200, {}, json.dumps(risposta).encode()
        r = web.cerca('llama cpp', n=2, base='http://motore:8888/', scarica=sc)
        self.assertEqual([x['url'] for x in r], ['https://a.org/1', 'https://b.org/2'])
        self.assertEqual(r[1]['titolo'], 'Due')
        self.assertEqual(len(r[1]['estratto']), 300)
        self.assertEqual(visti, ['http://motore:8888/search?q=llama+cpp&format=json&categories=general%2Cit'])

    def test_motore_spento(self):
        with self.assertRaises(ValueError):
            web.cerca('x', base='http://m', scarica=lambda u: (502, {}, b''))


class LimitiTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.file = os.path.join(self.dir, 'sotto', 'usi.json')

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_limite_e_finestra(self):
        for t in (0, 10, 20):
            web.conta('cerca', self.file, ora=1000 + t)
        with self.assertRaises(ValueError) as e:
            web.conta('cerca', self.file, ora=1100)
        self.assertIn('limite', str(e.exception))
        web.conta('leggi', self.file, ora=1100)
        web.conta('cerca', self.file, ora=1000 + web.FINESTRA + 1)

    def test_file_rovinato(self):
        os.makedirs(os.path.dirname(self.file))
        with open(self.file, 'w') as f:
            f.write('{rotto')
        web.conta('leggi', self.file, ora=5)


class RigaDiComandoTest(unittest.TestCase):
    def test_leggi_rifiutata(self):
        d = tempfile.mkdtemp()
        try:
            env = dict(os.environ, WEB_USI=os.path.join(d, 'usi.json'), PYTHONDONTWRITEBYTECODE='1')
            r = subprocess.run([sys.executable, os.path.join(QUI, '..', 'web', 'web.py'), 'leggi', 'http://127.0.0.1/'],
                               env=env, capture_output=True, text=True, timeout=20)
            self.assertEqual(r.returncode, 1)
            self.assertTrue(r.stderr.startswith('web: indirizzo non pubblico'))
        finally:
            shutil.rmtree(d, ignore_errors=True)


if __name__ == '__main__':
    unittest.main()
