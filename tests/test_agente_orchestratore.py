"""`agente orchestratore --cartella DIR "richiesta"`: da capo a fondo con un esegui-passo finto."""
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest

QUI = os.path.dirname(os.path.abspath(__file__))
AGENTE = os.path.join(QUI, '..', 'bin', 'agente')

# Finto esegui-passo: registra gli argomenti; alla richiesta del piano risponde con un piano di un solo
# revisore, al revisore risponde con un giudizio positivo e prova a scrivere un file (che va annullato).
FINTO = r'''#!/usr/bin/env python3
import os, sys
testo = sys.stdin.read()
with open(os.environ['REGISTRO'], 'a') as f:
    f.write(' '.join(sys.argv[1:]) + '\n')
if '"compiti"' in testo:
    print('```json\n{"compiti": [{"agente": "revisore", "compito": "rivedi a.py"}]}\n```')
else:
    open('scritto-dal-revisore.txt', 'w').write('x')
    print('{"ok": true, "difetti": []}')
'''


class Orchestratore(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp(prefix='orch-')
        self.addCleanup(shutil.rmtree, self.d, True)
        self.finto = os.path.join(self.d, 'esegui-passo')
        with open(self.finto, 'w') as f:
            f.write(FINTO)
        os.chmod(self.finto, stat.S_IRWXU)
        self.progetti = os.path.join(self.d, 'progetti')
        self.demo = os.path.join(self.progetti, 'demo')
        os.makedirs(self.demo)
        for a in (['init', '-q'], ['config', 'user.email', 'p@esempio.invalid'], ['config', 'user.name', 'p']):
            subprocess.run(['git', '-C', self.demo] + a, check=True)
        with open(os.path.join(self.demo, 'a.py'), 'w') as f:
            f.write('x = 1\n')
        subprocess.run(['git', '-C', self.demo, 'add', '.'], check=True)
        subprocess.run(['git', '-C', self.demo, 'commit', '-qm', 'i'], check=True)
        self.reg = os.path.join(self.d, 'reg')
        self.env = dict(os.environ, AGENTE_ESEGUI=self.finto, AGENTE_PROGETTI=self.progetti, REGISTRO=self.reg)

    def lancia(self, *argomenti):
        return subprocess.run([sys.executable, AGENTE] + list(argomenti), env=self.env, cwd=self.d,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, timeout=60)

    def test_da_capo_a_fondo(self):
        r = self.lancia('orchestratore', '--cartella', self.demo, '--json', 'rivedi il progetto')
        self.assertEqual(r.returncode, 0, r.stderr)
        esito = json.loads(r.stdout)
        self.assertEqual(esito['esito'], 'fatto')
        self.assertEqual(esito['piano'][0]['agente'], 'revisore')
        self.assertEqual(esito['risultati'][0]['scritture_annullate'], ['scritto-dal-revisore.txt'])
        self.assertFalse(os.path.exists(os.path.join(self.demo, 'scritto-dal-revisore.txt')))
        with open(self.reg) as f:
            righe = f.read().splitlines()
        self.assertEqual(righe, ['agente demo esecutore-pensiero'] * 3)  # piano + due letture del revisore

    def test_cartella_fuori_dai_progetti(self):
        r = self.lancia('orchestratore', '--cartella', self.d, 'rivedi')
        self.assertNotEqual(r.returncode, 0)
        self.assertNotIn('Traceback', r.stderr)

    def test_senza_richiesta(self):
        r = self.lancia('orchestratore', '--cartella', self.demo)
        self.assertNotEqual(r.returncode, 0)
        self.assertNotIn('Traceback', r.stderr)

    def test_esegui_passo_reale_predefinito(self):
        with open(AGENTE) as f:
            testo = f.read()
        self.assertIn('/opt/ai-vm/libexec/esegui-passo', testo)
        self.assertIn("'sudo', '-n', '-u', 'esecutore'", testo)


if __name__ == '__main__':
    unittest.main()
