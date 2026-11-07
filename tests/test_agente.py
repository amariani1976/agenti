"""Test di bin/agente: profilo, strumenti, cartella di lavoro e variabile PI_CODING_AGENT_DIR."""
import importlib.machinery
import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

QUI = os.path.dirname(os.path.abspath(__file__))
sys.dont_write_bytecode = True
_l = importlib.machinery.SourceFileLoader('agente', os.path.join(QUI, '..', 'bin', 'agente'))
A = importlib.util.module_from_spec(importlib.util.spec_from_loader('agente', _l))
_l.exec_module(A)


class AgenteTest(unittest.TestCase):
    def setUp(self):
        self.radice = tempfile.mkdtemp()
        p = os.path.join(self.radice, 'profili', 'prova')
        os.makedirs(p)
        with open(os.path.join(p, 'strumenti'), 'w') as f:
            f.write('read,bash\n')
        for s in ('kb', 'test'):
            os.makedirs(os.path.join(p, 'skills', s))
            open(os.path.join(p, 'skills', s, 'SKILL.md'), 'w').close()
        os.makedirs(os.path.join(p, 'skills', 'vuota'))

    def tearDown(self):
        shutil.rmtree(self.radice, ignore_errors=True)

    def test_comando(self):
        argv, env, cwd = A.comando('prova', 'fai X', '/tmp', self.radice, pi='/bin/pi')
        sk = os.path.join(self.radice, 'profili', 'prova', 'skills')
        self.assertEqual(argv, ['/bin/pi', '-p', '--no-session', '--no-skills',
                                '--skill', os.path.join(sk, 'kb'), '--skill', os.path.join(sk, 'test'),
                                '--tools', 'read,bash', 'fai X'])
        self.assertEqual(env, {'PI_CODING_AGENT_DIR': os.path.join(self.radice, 'profili', 'prova')})
        self.assertEqual(cwd, '/tmp')

    def test_profilo_inesistente(self):
        with self.assertRaises(ValueError):
            A.comando('manca', 'x', '/tmp', self.radice, pi='/bin/pi')

    def test_nome_non_valido(self):
        with self.assertRaises(ValueError):
            A.comando('../prova', 'x', '/tmp', self.radice, pi='/bin/pi')

    def test_esegue_pi_finto(self):
        finto = os.path.join(self.radice, 'pi-finto')
        with open(finto, 'w') as f:
            f.write('#!/bin/sh\necho "$PI_CODING_AGENT_DIR|$*|$(pwd)"\n')
        os.chmod(finto, 0o755)
        env = dict(os.environ, AGENTE_PI=finto, AGENTE_RADICE=self.radice)
        r = subprocess.run([sys.executable, os.path.join(QUI, '..', 'bin', 'agente'), 'prova', '--cartella', '/tmp', 'compito'],
                           env=env, stdout=subprocess.PIPE, universal_newlines=True)
        self.assertEqual(r.returncode, 0)
        self.assertEqual(r.stdout.strip(),
                         os.path.join(self.radice, 'profili', 'prova') + '|-p --no-session --no-skills --skill {0}/kb --skill {0}/test --tools read,bash compito|/tmp'.format(
                             os.path.join(self.radice, 'profili', 'prova', 'skills')))


if __name__ == '__main__':
    unittest.main()
