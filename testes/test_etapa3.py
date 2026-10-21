"""Etapa 3: fila, plug, curva e fim de recarga sem limite da agência (5.2, 5.3, 6.3.2-6.3.5)."""
import sys
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from kickoff import dados, medicao, motor, tempo, validar  # noqa: E402
from test_etapa2 import TEM_BANGKOK, carro, motor_vazio  # noqa: E402


def para_fila(m, v, t=0.0):
    m.patio.pop(v.id)
    m.entrar_patio(v, t)


@unittest.skipUnless(TEM_BANGKOK, "dados/Bangkok ausentes")
class Recarga(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cen = dados.carregar(RAIZ / "dados", "Bangkok")

    def _motor(self, carregadores, politica=None):
        m = motor_vazio(self.cen, carregadores, politica)
        m.limite_kw = 1e9  # etapa 3: sem limite da agência
        m.montado = True
        return m

    def test_632_dolphin_gs_20_80_dc60(self):
        m = self._motor({"dc_60x2": 1})
        m.t = 0.0
        v = carro(m, "gs", "BYD Dolphin GS", 20.0)
        para_fila(m, v)
        self.assertTrue(v.plugado)
        fim = None
        while m.heap:
            t, _, _, _, p = motor.heapq.heappop(m.heap)
            m.avancar(t)
            m.on_fim_recarga(p[0], p[1], t)
            if not v.plugado and fim is None:
                fim = t
        self.assertAlmostEqual(v.soc, 80.0)
        self.assertAlmostEqual(fim, 36.7, places=1)

    def test_634_escolhe_dc60(self):
        m = self._motor({"dc_60x2": 1, "ac_22x2": 1})
        m.t = 0.0
        geely = carro(m, "geely", "Geely EX2 Pro", 30.0)
        dc = next(p for p in m.pontos if p.modelo.id == "dc_60x2")
        m.plugar(geely, dc)
        gs = carro(m, "gs", "BYD Dolphin GS", 20.0)
        self.assertIs(m.escolher_ponto(gs), dc)

    def test_fila_nao_passa_das_saidas_e_ordem_menor_soc(self):
        m = self._motor({"ac_7": 1})
        m.t = 0.0
        a = carro(m, "a", "Renault Kwid E-Tech", 30.0)  # 55.5 km
        b = carro(m, "b", "JAC E-JS1", 20.0)  # 36.2 km
        m.patio.clear()
        m.aberta = False
        m.entrar_patio(a, 0.0)
        m.entrar_patio(b, 0.0)
        m.aberta = True
        m.plugar_fila(0.0)
        self.assertTrue(b.plugado)
        self.assertFalse(a.plugado)
        self.assertEqual(m.violacoes, [])

    def test_fila_chegada(self):
        m = self._motor({"ac_7": 1}, {"prioridade": "chegada"})
        a = carro(m, "a", "Renault Kwid E-Tech", 30.0)
        b = carro(m, "b", "JAC E-JS1", 20.0)
        m.patio.clear()
        m.aberta = False
        m.entrar_patio(a, 0.0)
        m.entrar_patio(b, 1.0)
        m.aberta = True
        m.plugar_fila(1.0)
        self.assertTrue(a.plugado)

    def test_bangkok_atendimento_sobe(self):
        sub = validar.normalizar({"agencia": "Bangkok", "carregadores": {"ac_7": 2, "dc_30": 1},
                                  "entrada": "b3_45"}, self.cen)
        res = motor.simular(self.cen, sub)
        ini, fim = tempo.JANELA_PUBLICA
        met = medicao.metricas(res.retiradas, res.nao_atendidos, res.bins, ini, fim)
        self.assertGreater(met["atendimento_pct"], 50)
        self.assertEqual(res.violacoes, [])
        for _, plugados, _ in res.trace:
            self.assertLessEqual(plugados, 3)


if __name__ == "__main__":
    unittest.main()
