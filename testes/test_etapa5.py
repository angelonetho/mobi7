"""Etapa 5: horário de funcionamento e `evitar_ponta` (5.2, 5.3, 6.3.6)."""
import sys
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from kickoff import dados, medicao, motor, tempo, validar  # noqa: E402
from test_etapa2 import TEM_BANGKOK, carro, motor_vazio  # noqa: E402

SEG = tempo.DIA  # Seg 18/10 00:00


def rodar(m, ate):
    while m.heap and m.heap[0][0] <= ate:
        t, _, _, tipo, p = motor.heapq.heappop(m.heap)
        m.avancar(t)
        if tipo == "fim_recarga":
            m.on_fim_recarga(p[0], p[1], t)
        elif tipo == "ponta":
            m.on_ponta(p[0], t)
        elif tipo == "abertura":
            m.on_abertura(t)
    m.avancar(ate)


@unittest.skipUnless(TEM_BANGKOK, "dados/Bangkok ausentes")
class Ponta(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cen = dados.carregar(RAIZ / "dados", "Bangkok")

    def test_636_mg4_17h_22h(self):
        """MG4 plugado às 17:00 com evitar_ponta: carrega até 18:00, 0 kW na ponta (plugado), volta às 21:00."""
        m = motor_vazio(self.cen, {"ac_7": 1}, {"evitar_ponta": True})
        m.montado = True
        m.t = SEG + 17 * 60
        v = carro(m, "mg4", "MG4 Urban Comfort", 10.0)
        m.patio.pop("mg4")
        m.entrar_patio(v, m.t)
        m.agendar(SEG + 18 * 60, motor.PRIO_ABERTURA, "ponta", True)
        m.agendar(SEG + 21 * 60, motor.PRIO_ABERTURA, "ponta", False)
        rodar(m, SEG + 18 * 60)
        soc_18 = v.soc
        self.assertGreater(soc_18, 10.0)
        rodar(m, SEG + 21 * 60 - 1)
        self.assertTrue(v.plugado)
        self.assertEqual(v.potencia_kw, 0.0)
        self.assertAlmostEqual(v.soc, soc_18)
        rodar(m, SEG + 22 * 60)
        self.assertGreater(v.soc, soc_18)

    def test_fechada_segura_saida_ate_abrir(self):
        m = motor_vazio(self.cen, {"dc_30": 1})
        m.montado = True
        m.t = 0.0
        v = carro(m, "jac", "JAC E-JS1", 70.0)
        m.patio.pop("jac")
        m.entrar_patio(v, 0.0)
        m.on_fechamento(0.0)
        rodar(m, 600)
        self.assertAlmostEqual(v.soc, 80.0)
        self.assertTrue(v.plugado)
        m.on_abertura(600)
        self.assertFalse(v.plugado)

    def test_bangkok_sem_energia_na_ponta(self):
        sub = validar.normalizar({"agencia": "Bangkok", "carregadores": {"ac_7": 2, "dc_30": 1},
                                  "entrada": "b3_45", "politica": {"evitar_ponta": True}}, self.cen)
        res = motor.simular(self.cen, sub)
        ini, fim = tempo.JANELA_PUBLICA
        met = medicao.metricas(res.retiradas, res.nao_atendidos, res.bins, ini, fim)
        self.assertAlmostEqual(met["energia_ponta_kwh"], 0.0)
        self.assertGreater(met["energia_kwh"], 0.0)


if __name__ == "__main__":
    unittest.main()
