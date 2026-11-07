"""Ciclo dell'agente: il metodo del runner per un compito solo (verifica, tentativi, perimetro, lezioni)."""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'ciclo'))
import ciclo  # noqa: E402


def git(d, *a):
    subprocess.run(['git', '-C', d] + list(a), check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def leggi(d, nome):
    with open(os.path.join(d, nome)) as f:
        return f.read()


def scrivi(d, nome, testo):
    with open(os.path.join(d, nome), 'w') as f:
        f.write(testo)


def verifica_ok_se(contenuto, nome='a.py'):
    """Verifica finta: passa solo se il file ha il contenuto atteso."""
    def v(comando, cartella):
        t = leggi(cartella, nome) if os.path.exists(os.path.join(cartella, nome)) else ''
        return (0, 'OK') if t == contenuto else (1, 'atteso {!r}, trovato {!r}'.format(contenuto, t))
    return v


class Ciclo(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp(prefix='ciclo-')
        self.addCleanup(shutil.rmtree, self.d, True)
        git(self.d, 'init', '-q')
        git(self.d, 'config', 'user.email', 'prova@esempio.invalid')
        git(self.d, 'config', 'user.name', 'prova')
        scrivi(self.d, 'a.py', 'x = 1\n')
        scrivi(self.d, 'b.py', 'y = 1\n')
        git(self.d, 'add', '.')
        git(self.d, 'commit', '-qm', 'inizio')
        self.prompt = []

    def agente(self, *azioni):
        """Agente finto: al tentativo n esegue azioni[n] sulla cartella e registra il prompt."""
        def lancia(prompt, cartella):
            self.prompt.append(prompt)
            azioni[len(self.prompt) - 1](cartella)
            return 0, 'fatto'
        return lancia

    def test_riesce_al_primo(self):
        r = ciclo.esegui('cambia x', self.d, 'prova', ['a.py'], lancia=self.agente(lambda c: scrivi(c, 'a.py', 'x = 2\n')),
                         verifica_fn=verifica_ok_se('x = 2\n'))
        self.assertEqual(r['esito'], 'fatto')
        self.assertEqual(len(r['tentativi']), 1)
        self.assertEqual(r['file'], ['a.py'])
        self.assertIn('+x = 2', r['diff'])

    def test_il_secondo_tentativo_vede_l_errore(self):
        r = ciclo.esegui('cambia x', self.d, 'prova', ['a.py'],
                         lancia=self.agente(lambda c: scrivi(c, 'a.py', 'x = 9\n'), lambda c: scrivi(c, 'a.py', 'x = 2\n')),
                         verifica_fn=verifica_ok_se('x = 2\n'))
        self.assertEqual(r['esito'], 'fatto')
        self.assertEqual(len(r['tentativi']), 2)
        self.assertIn("trovato 'x = 9\\n'", self.prompt[1])

    def test_il_prompt_dice_file_verifica_e_lezioni(self):
        ciclo.esegui('cambia x', self.d, 'python3 -I prova.py', ['a.py'], lancia=self.agente(lambda c: scrivi(c, 'a.py', 'x = 2\n')),
                     verifica_fn=verifica_ok_se('x = 2\n'), lezioni=lambda compito: ['Regola: usa timeout'])
        p = self.prompt[0]
        for atteso in ('cambia x', 'a.py', 'python3 -I prova.py', 'Regola: usa timeout'):
            self.assertIn(atteso, p)

    def test_fuori_perimetro_si_annulla(self):
        def sconfina(c):
            scrivi(c, 'a.py', 'x = 2\n')
            scrivi(c, 'b.py', 'y = 99\n')
            scrivi(c, 'nuovo.py', 'z = 1\n')
        r = ciclo.esegui('cambia x', self.d, 'prova', ['a.py'], lancia=self.agente(sconfina, lambda c: scrivi(c, 'a.py', 'x = 2\n')),
                         verifica_fn=verifica_ok_se('x = 2\n'))
        self.assertEqual(sorted(r['tentativi'][0]['fuori_perimetro']), ['b.py', 'nuovo.py'])
        self.assertEqual(leggi(self.d, 'b.py'), 'y = 1\n')
        self.assertFalse(os.path.exists(os.path.join(self.d, 'nuovo.py')))
        self.assertEqual(r['esito'], 'fatto')
        self.assertEqual(len(r['tentativi']), 2)
        self.assertIn('b.py', self.prompt[1])

    def test_tutti_falliti_si_torna_all_inizio(self):
        r = ciclo.esegui('cambia x', self.d, 'prova', ['a.py'], tentativi=3,
                         lancia=self.agente(*[lambda c: scrivi(c, 'a.py', 'x = 9\n')] * 3), verifica_fn=verifica_ok_se('x = 2\n'))
        self.assertEqual(r['esito'], 'non-fatto')
        self.assertEqual(len(r['tentativi']), 3)
        self.assertEqual(leggi(self.d, 'a.py'), 'x = 1\n')
        self.assertEqual(r['diff'], '')

    def test_un_file_nuovo_nel_perimetro(self):
        r = ciclo.esegui('crea c', self.d, 'prova', ['c.py'], lancia=self.agente(lambda c: scrivi(c, 'c.py', 'z = 3\n')),
                         verifica_fn=verifica_ok_se('z = 3\n', 'c.py'))
        self.assertEqual(r['esito'], 'fatto')
        self.assertIn('+z = 3', r['diff'])

    def test_modifiche_gia_presenti_fuori_perimetro_restano(self):
        scrivi(self.d, 'b.py', 'y = 5\n')
        ciclo.esegui('cambia x', self.d, 'prova', ['a.py'], lancia=self.agente(lambda c: scrivi(c, 'a.py', 'x = 2\n')),
                     verifica_fn=verifica_ok_se('x = 2\n'))
        self.assertEqual(leggi(self.d, 'b.py'), 'y = 5\n')

    def test_errori_di_ingresso(self):
        with self.assertRaises(ValueError):
            ciclo.esegui('x', tempfile.gettempdir(), 'prova', ['a.py'], lancia=self.agente(), verifica_fn=verifica_ok_se(''))
        for file in ([], ['../fuori.py'], ['/etc/passwd']):
            with self.assertRaises(ValueError):
                ciclo.esegui('x', self.d, 'prova', file, lancia=self.agente(), verifica_fn=verifica_ok_se(''))
        with self.assertRaises(ValueError):
            ciclo.esegui('x', self.d, '', ['a.py'], lancia=self.agente(), verifica_fn=verifica_ok_se(''))

    def test_l_uscita_lunga_si_tronca(self):
        def lunga(comando, cartella):
            return 1, 'riga\n' * 5000
        r = ciclo.esegui('x', self.d, 'prova', ['a.py'], tentativi=1, lancia=self.agente(lambda c: None), verifica_fn=lunga)
        self.assertLessEqual(len(r['tentativi'][0]['uscita']), 3000)
        self.assertLessEqual(len(self.prompt[0]), 20000)


if __name__ == '__main__':
    unittest.main()
