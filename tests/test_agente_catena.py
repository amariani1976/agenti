"""Il comando agente con la catena vera: ciclo + Esecuzione + programma esegui-passo (qui finto), mai pi diretto."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

AGENTE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'bin', 'agente')
FINTO = r'''#!/usr/bin/python3
import os, subprocess, sys
modo, nome = sys.argv[1], sys.argv[2]
cwd = os.path.join(os.environ['AGENTE_PROGETTI'], nome)
testo = sys.stdin.read()
with open(os.environ['REGISTRO'], 'a') as f:
    f.write(modo + ' ' + ' '.join(sys.argv[2:]) + '\n')
if modo == 'agente':
    with open(os.path.join(cwd, 'a.py'), 'w') as f:
        f.write('x = 2\n' if 'cambia x' in testo else 'x = 9\n')
    print('fatto')
    sys.exit(0)
r = subprocess.run(['bash', '-c', testo], cwd=cwd)
sys.exit(r.returncode)
'''


class Catena(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp(prefix='catena-')
        self.addCleanup(shutil.rmtree, self.d, True)
        self.prog = os.path.join(self.d, 'progetti', 'demo')
        os.makedirs(self.prog)
        for c in (['init', '-q'], ['config', 'user.email', 'p@esempio.invalid'], ['config', 'user.name', 'p']):
            subprocess.run(['git', '-C', self.prog] + c, check=True)
        with open(os.path.join(self.prog, 'a.py'), 'w') as f:
            f.write('x = 1\n')
        subprocess.run(['git', '-C', self.prog, 'add', '.'], check=True)
        subprocess.run(['git', '-C', self.prog, 'commit', '-qm', 'i'], check=True)
        self.finto = os.path.join(self.d, 'esegui-passo')
        with open(self.finto, 'w') as f:
            f.write(FINTO)
        os.chmod(self.finto, 0o755)
        self.pi = os.path.join(self.d, 'pi')
        self.segno = os.path.join(self.d, 'pi-usato')
        with open(self.pi, 'w') as f:
            f.write('#!/bin/sh\ntouch ' + self.segno + '\n')
        os.chmod(self.pi, 0o755)
        self.reg = os.path.join(self.d, 'registro')
        self.env = dict(os.environ, AGENTE_ESEGUI=self.finto, AGENTE_PROGETTI=os.path.join(self.d, 'progetti'), AGENTE_PI=self.pi,
                        REGISTRO=self.reg, PATH='/usr/bin:/bin')

    def agente(self, *a):
        return subprocess.run([sys.executable, AGENTE] + list(a), env=self.env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              universal_newlines=True, timeout=120)

    def test_fatto_con_verifica_tra_virgolette(self):
        r = self.agente('programmatore', '--cartella', self.prog, '--file', 'a.py', '--verifica', 'grep -q "x = 2" a.py && test "$(wc -l < a.py)" -eq 1',
                        '--json', 'cambia x')
        self.assertEqual(r.returncode, 0, r.stderr[-800:])
        esito = json.loads(r.stdout[r.stdout.index('{'):])
        self.assertEqual(esito['esito'], 'fatto')
        with open(self.reg) as f:
            righe = f.read().splitlines()
        self.assertTrue(righe[0].startswith('agente demo '), righe)
        self.assertTrue(any(x.startswith('verifica demo') for x in righe), righe)
        self.assertFalse(os.path.exists(self.segno), 'pi lanciato direttamente: deve passare solo da esegui-passo')

    def test_non_fatto_esce_con_uno_e_ripristina(self):
        r = self.agente('programmatore', '--cartella', self.prog, '--file', 'a.py', '--verifica', 'grep -q "x = 2" a.py',
                        '--tentativi', '2', '--json', 'scrivi altro')
        self.assertEqual(r.returncode, 1, r.stderr[-800:])
        self.assertEqual(json.loads(r.stdout[r.stdout.index('{'):])['esito'], 'non-fatto')
        with open(os.path.join(self.prog, 'a.py')) as f:
            self.assertEqual(f.read(), 'x = 1\n')
        self.assertFalse(os.path.exists(self.segno))

    def test_errori_d_ingresso_escono_con_due(self):
        for a in (['--cartella', self.d, '--file', 'a.py'], ['--cartella', self.prog, '--file', '../fuori.py']):
            r = self.agente('programmatore', *a, '--verifica', 'true', 'x')
            self.assertEqual(r.returncode, 2, (a, r.stderr[-300:]))

    def test_da_un_collegamento_simbolico(self):
        link = os.path.join(self.d, 'agente-link')
        os.symlink(os.path.abspath(AGENTE), link)
        r = subprocess.run([sys.executable, link, 'programmatore', '--cartella', self.prog, '--file', 'a.py', '--verifica',
                            'grep -q "x = 2" a.py', '--json', 'cambia x'], env=self.env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                           universal_newlines=True, timeout=120)
        self.assertEqual(r.returncode, 0, r.stderr[-500:])


if __name__ == '__main__':
    unittest.main()
