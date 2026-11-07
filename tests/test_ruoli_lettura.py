"""Revisore e ricercatore in sola lettura anche con sottocartelle, file nuovi di prima e perimetro nel compito."""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'ciclo'))
import ruoli  # noqa: E402


def git(d, *a):
    subprocess.run(['git', '-C', d] + list(a), check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def scrivi(d, nome, testo):
    p = os.path.join(d, nome)
    if not os.path.isdir(os.path.dirname(p)):
        os.makedirs(os.path.dirname(p))
    with open(p, 'w') as f:
        f.write(testo)


def leggi(d, nome):
    with open(os.path.join(d, nome)) as f:
        return f.read()


OK = '{"ok": true, "difetti": []}'


class SolaLettura(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp(prefix='lettura-')
        self.addCleanup(shutil.rmtree, self.d, True)
        git(self.d, 'init', '-q')
        git(self.d, 'config', 'user.email', 'p@esempio.invalid')
        git(self.d, 'config', 'user.name', 'p')
        scrivi(self.d, 'a.py', 'x = 1\n')
        scrivi(self.d, 'sub/b.py', 'y = 1\n')
        git(self.d, 'add', '.')
        git(self.d, 'commit', '-qm', 'i')

    def test_sottocartella_ripristinata(self):
        def lancia(prompt, cartella):
            scrivi(cartella, 'sub/b.py', 'rotto\n')
            scrivi(cartella, 'sub/nuovo.py', 'z\n')
            return 0, OK
        r = ruoli.revisore({'agente': 'revisore', 'compito': 'rivedi'}, self.d, lancia=lancia)
        self.assertEqual(r['scritture_annullate'], ['sub/b.py', 'sub/nuovo.py'])
        self.assertEqual(leggi(self.d, 'sub/b.py'), 'y = 1\n')
        self.assertFalse(os.path.exists(os.path.join(self.d, 'sub/nuovo.py')))

    def test_file_nuovi_di_prima_restano(self):
        scrivi(self.d, 'sub/fatto.py', 'def f(): pass\n')
        scrivi(self.d, 'altro/nuovo.py', 'n = 1\n')
        r = ruoli.revisore({'agente': 'revisore', 'compito': 'rivedi'}, self.d, lancia=lambda p, c: (0, OK))
        self.assertEqual(r['scritture_annullate'], [])
        self.assertEqual(leggi(self.d, 'sub/fatto.py'), 'def f(): pass\n')
        self.assertEqual(leggi(self.d, 'altro/nuovo.py'), 'n = 1\n')

    def test_file_nuovi_di_prima_cambiati_tornano_come_prima(self):
        scrivi(self.d, 'sub/fatto.py', 'def f(): pass\n')

        def lancia(prompt, cartella):
            scrivi(cartella, 'sub/fatto.py', 'rotto\n')
            return 0, OK
        r = ruoli.revisore({'agente': 'revisore', 'compito': 'rivedi'}, self.d, lancia=lancia)
        self.assertEqual(r['scritture_annullate'], ['sub/fatto.py'])
        self.assertEqual(leggi(self.d, 'sub/fatto.py'), 'def f(): pass\n')

    def test_il_perimetro_nel_compito_non_apre_scritture(self):
        def lancia(prompt, cartella):
            scrivi(cartella, 'a.py', 'rotto\n')
            return 0, OK
        r = ruoli.revisore({'agente': 'revisore', 'compito': 'rivedi', 'file': ['a.py']}, self.d, lancia=lancia)
        self.assertEqual(r['scritture_annullate'], ['a.py'])
        self.assertEqual(leggi(self.d, 'a.py'), 'x = 1\n')

    def test_il_diff_mostra_i_file_nuovi_in_sottocartella(self):
        scrivi(self.d, 'sub/fatto.py', 'def nuova(): pass\n')
        visti = []
        ruoli.revisore({'agente': 'revisore', 'compito': 'rivedi'}, self.d, lancia=lambda p, c: (visti.append(p), (0, OK))[1])
        self.assertIn('+def nuova(): pass', visti[0])
        self.assertNotIn('puoi modificare', visti[0])

    def test_json_con_testo_intorno(self):
        r = ruoli.revisore({'agente': 'revisore', 'compito': 'rivedi'}, self.d,
                           lancia=lambda p, c: (0, 'Giudizio: {"ok": false, "difetti": ["d"]} fine'))
        self.assertEqual((r['esito'], r['ok'], r['difetti']), ('fatto', False, ['d']))

    def test_ricercatore_una_chiamata_e_sola_lettura(self):
        prompt = []

        def lancia(p, cartella):
            prompt.append(p)
            scrivi(cartella, 'sub/b.py', 'rotto\n')
            return 0, 'sintesi'
        r = ruoli.ricercatore({'agente': 'ricercatore', 'compito': 'cerca select'}, self.d, lancia=lancia)
        self.assertEqual((r['esito'], r['testo']), ('fatto', 'sintesi'))
        self.assertEqual(len(prompt), 1)
        for atteso in ('cerca select', 'KB', 'web', 'salva'):
            self.assertIn(atteso, prompt[0])
        self.assertEqual(leggi(self.d, 'sub/b.py'), 'y = 1\n')

    def test_ricercatore_codice_non_zero(self):
        r = ruoli.ricercatore({'agente': 'ricercatore', 'compito': 'cerca'}, self.d, lancia=lambda p, c: (1, 'errore'))
        self.assertEqual(r['esito'], 'non-fatto')


if __name__ == '__main__':
    unittest.main()
