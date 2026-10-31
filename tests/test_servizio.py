"""Test di kb/servizio.py: API JSON con token, server MCP, git a ogni salvataggio, fonti esterne."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.parse
import urllib.request

QUI = os.path.dirname(os.path.abspath(__file__))
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.join(QUI, '..', 'kb'))
import servizio  # noqa: E402

TOKEN = 'token-di-prova-0123456789'


class Base(unittest.TestCase):
    def setUp(self):
        self.kb = tempfile.mkdtemp()
        self.fonti = tempfile.mkdtemp()
        self.db = os.path.join(tempfile.mkdtemp(), 'indice.db')
        with open(os.path.join(self.kb, 'neteye.md'), 'w') as f:
            f.write('# NetEye\n\nSola verifica sul server.\n')
        os.makedirs(os.path.join(self.fonti, 'aivm'))
        with open(os.path.join(self.fonti, 'aivm', 'GUIDA.md'), 'w') as f:
            f.write('# Guida\n\nSearXNG sulla porta 8888.\n')
        os.makedirs(os.path.join(self.fonti, '.nascosta'))
        subprocess.run(['git', 'init', '-q', self.kb], check=True)
        self.stato = servizio.Kb(self.kb, self.db, servizio.carica_fonti(self.fonti), TOKEN)
        self.srv = servizio.crea(self.stato, '127.0.0.1', 0)
        self.url = 'http://127.0.0.1:%d' % self.srv.server_address[1]
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()

    def tearDown(self):
        self.srv.shutdown()
        self.srv.server_close()
        for d in (self.kb, self.fonti, os.path.dirname(self.db)):
            shutil.rmtree(d, ignore_errors=True)

    def chiama(self, metodo, percorso, dati=None, token=TOKEN, query=None):
        u = self.url + percorso + ('?' + urllib.parse.urlencode(query) if query else '')
        h = {'Content-Type': 'application/json'}
        if token:
            h['Authorization'] = 'Bearer ' + token
        req = urllib.request.Request(u, data=json.dumps(dati).encode() if dati is not None else None,
                                     method=metodo, headers=h)
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                corpo = r.read().decode()
                return r.status, json.loads(corpo) if corpo else None
        except urllib.error.HTTPError as e:
            corpo = e.read().decode()
            return e.code, json.loads(corpo) if corpo else None


class ApiTest(Base):
    def test_carica_fonti(self):
        self.assertEqual(servizio.carica_fonti(self.fonti), {'aivm': os.path.join(self.fonti, 'aivm')})
        self.assertEqual(servizio.carica_fonti(os.path.join(self.fonti, 'manca')), {})

    def test_salute_senza_token(self):
        self.assertEqual(self.chiama('GET', '/salute', token=None), (200, {'ok': True}))

    def test_token_obbligatorio(self):
        self.assertEqual(self.chiama('GET', '/cerca', token=None, query={'q': 'x'})[0], 401)
        self.assertEqual(self.chiama('GET', '/cerca', token='sbagliato', query={'q': 'x'})[0], 401)
        self.assertEqual(self.chiama('POST', '/salva', {'agente': 'a', 'titolo': 't', 'testo': 'x'}, token=None)[0], 401)
        self.assertEqual(self.chiama('POST', '/mcp', {'jsonrpc': '2.0', 'id': 1, 'method': 'ping'}, token=None)[0], 401)

    def test_cerca_e_leggi(self):
        codice, d = self.chiama('GET', '/cerca', query={'q': 'SearXNG'})
        self.assertEqual(codice, 200)
        self.assertEqual(d['risultati'][0]['path'], '@aivm/GUIDA.md')
        codice, d = self.chiama('GET', '/leggi', query={'nota': 'neteye.md'})
        self.assertEqual((codice, 'Sola verifica' in d['testo']), (200, True))
        self.assertEqual(self.chiama('GET', '/leggi', query={'nota': '../x.md'})[0], 400)
        self.assertEqual(self.chiama('GET', '/niente')[0], 404)

    def test_salva_commit_e_indice(self):
        codice, d = self.chiama('POST', '/salva', {'agente': 'programmatore', 'titolo': 'Lezione', 'testo': 'Usare iterator.\n',
                                                   'progetto': 'icinga-ui', 'extra': {'stato': 'da-verificare'}})
        self.assertEqual(codice, 200)
        self.assertTrue(d['path'].startswith('inbox/'))
        log = subprocess.run(['git', '-C', self.kb, 'log', '--format=%an|%s'], capture_output=True, text=True).stdout
        self.assertEqual(log.strip(), 'programmatore|kb: %s (programmatore)' % d['path'])
        self.assertEqual(self.chiama('GET', '/cerca', query={'q': 'iterator'})[1]['risultati'][0]['path'], d['path'])

    def test_salva_errori(self):
        self.assertEqual(self.chiama('POST', '/salva', {'agente': 'a'})[0], 400)
        codice, d = self.chiama('POST', '/salva', {'agente': 'a', 'titolo': 't', 'testo': 'password: x'})
        self.assertEqual(codice, 400)
        self.assertIn('segreto', d['errore'])


class McpTest(Base):
    def rpc(self, metodo, params=None, mid=1):
        msg = {'jsonrpc': '2.0', 'id': mid, 'method': metodo}
        if params is not None:
            msg['params'] = params
        return self.chiama('POST', '/mcp', msg)

    def test_initialize(self):
        codice, d = self.rpc('initialize', {'protocolVersion': '2025-06-18', 'capabilities': {},
                                            'clientInfo': {'name': 'prova', 'version': '0'}})
        self.assertEqual(codice, 200)
        self.assertEqual(d['id'], 1)
        self.assertEqual(d['result']['serverInfo']['name'], 'kb')
        self.assertIn('tools', d['result']['capabilities'])

    def test_notifica(self):
        codice, d = self.chiama('POST', '/mcp', {'jsonrpc': '2.0', 'method': 'notifications/initialized'})
        self.assertEqual((codice, d), (202, None))

    def test_tools_list(self):
        nomi = [t['name'] for t in self.rpc('tools/list')[1]['result']['tools']]
        self.assertEqual(nomi, ['kb_cerca', 'kb_leggi', 'kb_salva'])

    def test_tools_call(self):
        r = self.rpc('tools/call', {'name': 'kb_cerca', 'arguments': {'query': 'verifica'}})[1]['result']
        self.assertFalse(r['isError'])
        self.assertEqual(json.loads(r['content'][0]['text'])[0]['path'], 'neteye.md')
        r = self.rpc('tools/call', {'name': 'kb_salva', 'arguments': {'agente': 'claude', 'titolo': 'Da MCP', 'testo': 'ok'}})[1]['result']
        self.assertTrue(r['content'][0]['text'].startswith('inbox/'))
        r = self.rpc('tools/call', {'name': 'kb_leggi', 'arguments': {'nota': '/etc/passwd'}})[1]['result']
        self.assertTrue(r['isError'])

    def test_errori_jsonrpc(self):
        self.assertEqual(self.rpc('sconosciuto')[1]['error']['code'], -32601)
        self.assertEqual(self.rpc('tools/call', {'name': 'kb_cancella', 'arguments': {}})[1]['error']['code'], -32602)


class AvvioTest(unittest.TestCase):
    def test_senza_token_non_parte(self):
        env = dict(os.environ, KB_TOKEN='corto', PYTHONDONTWRITEBYTECODE='1')
        r = subprocess.run([sys.executable, os.path.join(QUI, '..', 'kb', 'servizio.py')], env=env,
                           capture_output=True, text=True, timeout=20)
        self.assertEqual(r.returncode, 1)
        self.assertIn('KB_TOKEN', r.stderr)


if __name__ == '__main__':
    unittest.main()
