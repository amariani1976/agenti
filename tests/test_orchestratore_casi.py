"""Orchestratore: richiesta ripetuta con il contesto, correzioni senza programmatore, piani con tipi sbagliati."""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'ciclo'))
import orchestratore  # noqa: E402

PROG = {'agente': 'programmatore', 'compito': 'scrivi f', 'file': ['a.py'], 'verifica': 'v'}
REV = {'agente': 'revisore', 'compito': 'rivedi a.py'}


def piano(*compiti):
    return json.dumps({'compiti': list(compiti)})


class Casi(unittest.TestCase):
    def setUp(self):
        self.richieste = []
        self.chiamate = []
        self.avvisi = []

    def chiedi(self, *risposte):
        risposte = list(risposte)

        def f(prompt):
            self.richieste.append(prompt)
            return risposte.pop(0)
        return f

    def agenti(self, revisore, programmatore=None):
        revisore = list(revisore)
        programmatore = list(programmatore or [])

        def fa(nome):
            def a(compito, cartella):
                self.chiamate.append((nome, dict(compito)))
                if nome == 'revisore':
                    return revisore.pop(0)
                if nome == 'programmatore' and programmatore:
                    return programmatore.pop(0)
                return {'esito': 'fatto'}
            return a
        return {n: fa(n) for n in ('programmatore', 'revisore', 'ricercatore')}

    def esegui(self, chiedi, agenti):
        return orchestratore.esegui('fai la funzione f', tempfile.gettempdir(), chiedi, agenti,
                                    avvisa=lambda t, x: self.avvisi.append((t, x)))

    def test_la_seconda_richiesta_ripete_richiesta_e_ruoli(self):
        r = self.esegui(self.chiedi('non so', piano(REV)), self.agenti([{'esito': 'fatto', 'ok': True, 'difetti': []}]))
        self.assertEqual(r['esito'], 'fatto')
        for atteso in ('piano non valido', 'fai la funzione f', 'programmatore', '"compiti"'):
            self.assertIn(atteso, self.richieste[1])

    def test_difetti_senza_programmatore_chiedono_aiuto(self):
        r = self.esegui(self.chiedi(piano(REV)), self.agenti([{'esito': 'fatto', 'ok': False, 'difetti': ['manca tutto']}]))
        self.assertEqual(r['esito'], 'aiuto')
        self.assertEqual(self.avvisi[-1][0], 'aiuto')
        self.assertIn('manca tutto', self.avvisi[-1][1])

    def test_correzione_non_fatta_chiede_aiuto(self):
        r = self.esegui(self.chiedi(piano(PROG, REV)),
                        self.agenti([{'esito': 'fatto', 'ok': False, 'difetti': ['d']}],
                                    programmatore=[{'esito': 'fatto'}, {'esito': 'non-fatto'}]))
        self.assertEqual(r['esito'], 'aiuto')
        self.assertEqual([c[0] for c in self.chiamate], ['programmatore', 'revisore', 'programmatore'])

    def test_il_revisore_ripassa_con_il_suo_compito(self):
        self.esegui(self.chiedi(piano(PROG, REV)),
                    self.agenti([{'esito': 'fatto', 'ok': False, 'difetti': ['d']}, {'esito': 'fatto', 'ok': True, 'difetti': []}]))
        self.assertEqual(self.chiamate[3], ('revisore', REV))

    def test_tipi_sbagliati_non_mandano_in_errore(self):
        sbagliati = [
            piano({'agente': 'ricercatore', 'compito': 5}),
            piano({'agente': 'programmatore', 'compito': 'x', 'file': ['a.py'], 'verifica': 3}),
            piano({'agente': 'programmatore', 'compito': 'x', 'file': 'a.py', 'verifica': 'v'}),
            piano({'agente': 'programmatore', 'compito': 'x', 'file': ['a/../../b.py'], 'verifica': 'v'}),
            json.dumps({'compiti': 'tutti'}),
            '[1, 2]',
        ]
        for s in sbagliati:
            self.setUp()
            r = self.esegui(self.chiedi(s, s), self.agenti([]))
            self.assertEqual(r['esito'], 'aiuto', s)
            self.assertEqual(self.chiamate, [], s)


if __name__ == '__main__':
    unittest.main()
