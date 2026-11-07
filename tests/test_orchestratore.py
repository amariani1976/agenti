"""Orchestratore: il modello propone il piano, il programma lo convalida, richiama gli agenti in sequenza e avvisa."""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'ciclo'))
import orchestratore  # noqa: E402

CARTELLA = tempfile.gettempdir()


def piano(*compiti):
    return 'Ecco il piano:\n```json\n' + json.dumps({'compiti': list(compiti)}) + '\n```'


PROG = {'agente': 'programmatore', 'compito': 'scrivi f', 'file': ['a.py'], 'verifica': 'python3 -I t.py'}
REV = {'agente': 'revisore', 'compito': 'rivedi a.py'}
RIC = {'agente': 'ricercatore', 'compito': 'cerca come si usa select'}


class Prova(unittest.TestCase):
    def setUp(self):
        self.chiamate = []
        self.avvisi = []
        self.richieste = []
        self.esiti_revisore = [{'esito': 'fatto', 'ok': True, 'difetti': []}]

    def chiedi(self, *risposte):
        risposte = list(risposte)

        def f(prompt):
            self.richieste.append(prompt)
            return risposte.pop(0)
        return f

    def agenti(self, fallisce=None):
        def fa(nome):
            def a(compito, cartella):
                self.chiamate.append((nome, compito['compito']))
                if nome == 'revisore':
                    return self.esiti_revisore.pop(0)
                return {'esito': 'non-fatto' if nome == fallisce else 'fatto', 'diff': '+x'}
            return a
        return {n: fa(n) for n in ('programmatore', 'revisore', 'ricercatore')}

    def esegui(self, chiedi, **k):
        return orchestratore.esegui('fai la funzione f', CARTELLA, chiedi, k.pop('agenti', None) or self.agenti(),
                                    avvisa=lambda tipo, testo: self.avvisi.append((tipo, testo)), **k)

    def test_piano_eseguito_in_ordine(self):
        r = self.esegui(self.chiedi(piano(RIC, PROG, REV)))
        self.assertEqual(r['esito'], 'fatto')
        self.assertEqual([c[0] for c in self.chiamate], ['ricercatore', 'programmatore', 'revisore'])
        self.assertEqual(self.avvisi[-1][0], 'fatto')
        self.assertIn('fai la funzione f', self.avvisi[-1][1])

    def test_il_prompt_descrive_ruoli_e_forma(self):
        self.esegui(self.chiedi(piano(PROG)))
        p = self.richieste[0]
        for atteso in ('fai la funzione f', 'programmatore', 'revisore', 'ricercatore', 'verifica', '"compiti"'):
            self.assertIn(atteso, p)

    def test_json_sbagliato_si_richiede_una_volta(self):
        r = self.esegui(self.chiedi('non so', piano(PROG)))
        self.assertEqual(r['esito'], 'fatto')
        self.assertEqual(len(self.richieste), 2)
        self.assertIn('non valido', self.richieste[1])

    def test_due_piani_sbagliati_chiedono_aiuto(self):
        r = self.esegui(self.chiedi('non so', '{"compiti": []}'))
        self.assertEqual(r['esito'], 'aiuto')
        self.assertEqual(self.chiamate, [])
        self.assertEqual(self.avvisi[-1][0], 'aiuto')

    def test_piani_non_ammessi(self):
        sbagliati = [
            piano({'agente': 'cancellatore', 'compito': 'x'}),
            piano({'agente': 'programmatore', 'compito': 'x', 'file': ['a.py']}),
            piano({'agente': 'programmatore', 'compito': 'x', 'file': ['../fuori.py'], 'verifica': 'v'}),
            piano({'agente': 'programmatore', 'compito': 'x', 'file': ['/etc/passwd'], 'verifica': 'v'}),
            piano({'agente': 'programmatore', 'compito': '', 'file': ['a.py'], 'verifica': 'v'}),
            piano(*[RIC] * 7),
        ]
        for s in sbagliati:
            self.setUp()
            r = self.esegui(self.chiedi(s, s))
            self.assertEqual(r['esito'], 'aiuto', s)
            self.assertEqual(self.chiamate, [], s)

    def test_compito_non_fatto_ferma_e_chiede_aiuto(self):
        r = self.esegui(self.chiedi(piano(PROG, REV)), agenti=self.agenti(fallisce='programmatore'))
        self.assertEqual(r['esito'], 'aiuto')
        self.assertEqual([c[0] for c in self.chiamate], ['programmatore'])
        self.assertEqual(self.avvisi[-1][0], 'aiuto')
        self.assertIn('programmatore', self.avvisi[-1][1])

    def test_il_revisore_trova_difetti_un_giro_di_correzione(self):
        self.esiti_revisore = [{'esito': 'fatto', 'ok': False, 'difetti': ['manca il caso vuoto']},
                               {'esito': 'fatto', 'ok': True, 'difetti': []}]
        r = self.esegui(self.chiedi(piano(PROG, REV)))
        self.assertEqual(r['esito'], 'fatto')
        self.assertEqual([c[0] for c in self.chiamate], ['programmatore', 'revisore', 'programmatore', 'revisore'])
        self.assertIn('manca il caso vuoto', self.chiamate[2][1])

    def test_difetti_anche_dopo_la_correzione(self):
        self.esiti_revisore = [{'esito': 'fatto', 'ok': False, 'difetti': ['a']}, {'esito': 'fatto', 'ok': False, 'difetti': ['b']}]
        r = self.esegui(self.chiedi(piano(PROG, REV)))
        self.assertEqual(r['esito'], 'aiuto')
        self.assertEqual(len(self.chiamate), 4)
        self.assertIn('b', self.avvisi[-1][1])

    def test_risultati_nel_resoconto(self):
        r = self.esegui(self.chiedi(piano(PROG)))
        self.assertEqual(r['piano'][0]['agente'], 'programmatore')
        self.assertEqual(r['risultati'][0]['esito'], 'fatto')


if __name__ == '__main__':
    unittest.main()
