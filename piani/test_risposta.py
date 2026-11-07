"""Lettura del primo oggetto JSON da una risposta del modello: una sola funzione per ruoli e orchestratore."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'ciclo'))
import risposta  # noqa: E402


class PrimoJson(unittest.TestCase):
    def test_testo_intorno(self):
        self.assertEqual(risposta.primo_json('Ecco il giudizio: {"ok": true, "difetti": []} fine.'), {'ok': True, 'difetti': []})

    def test_blocco_json(self):
        self.assertEqual(risposta.primo_json('Piano:\n```json\n{"compiti": [1]}\n```\nAltro {"x": 2}'), {'compiti': [1]})

    def test_primo_di_due(self):
        self.assertEqual(risposta.primo_json('{"a": 1}\n{"b": 2}'), {'a': 1})

    def test_graffe_prima_del_json(self):
        self.assertEqual(risposta.primo_json('uso {graffe} poi {"a": {"b": 1}}'), {'a': {'b': 1}})

    def test_illeggibile(self):
        for testo in ('', None, 'non so', '[1, 2]', '{rotto'):
            self.assertIsNone(risposta.primo_json(testo), testo)

    def test_ruoli_e_orchestratore_la_usano(self):
        qui = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'ciclo')
        for nome in ('ruoli.py', 'orchestratore.py'):
            with open(os.path.join(qui, nome)) as f:
                testo = f.read()
            self.assertIn('primo_json', testo, nome)
            self.assertNotIn('def _json_da_risposta', testo, nome)


if __name__ == '__main__':
    unittest.main()
