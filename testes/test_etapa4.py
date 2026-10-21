"""Etapa 4: limite da agência e `divisao` (5.3, 6.3.5, 6.3.7)."""
import sys
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from kickoff import dados, medicao, motor, tempo, validar  # noqa: E402
from test_etapa2 import TEM_BANGKOK, carro, motor_vazio  # noqa: E402


@unittest.skipUnless(TEM_BANGKOK, "dados/Bangkok ausentes")
class Exemplo635(unittest.TestCase):
    """2x DC-60; degraus DC: Kwid 40% (26.6), Geely 30% (71.5), JAC 75% (16.45), Dolphin GS 50% (47.75)."""

    @classmethod
    def setUpClass(cls):
        cls.cen = dados.carregar(RAIZ / "dados", "Bangkok")

    def _potencias(self, limite, divisao):
        m = motor_vazio(self.cen, {"dc_60x2": 2}, {"prioridade": "menor_soc", "divisao": divisao})
        m.limite_kw = limite
        p0, p1 = m.pontos
        m.plugar(carro(m, "geely", "Geely EX2 Pro", 30.0), p0)
        m.plugar(carro(m, "dolphin", "BYD Dolphin GS", 50.0), p0)
        m.plugar(carro(m, "kwid", "Renault Kwid E-Tech", 40.0), p1)
        m.plugar(carro(m, "jac", "JAC E-JS1", 75.0), p1)
        m.recalcular_potencias(0.0)
        return {v: m.veiculos[v].potencia_kw for v in ("kwid", "geely", "jac", "dolphin")}

    def _aprox(self, obtido, esperado):
        for k, x in esperado.items():
            self.assertAlmostEqual(obtido[k], x, places=4, msg=k)

    def test_igual_40_5(self):
        self._aprox(self._potencias(40.5, "igual"), dict.fromkeys(("kwid", "geely", "jac", "dolphin"), 10.125))

    def test_prioridade_40_5(self):
        self._aprox(self._potencias(40.5, "prioridade"), {"kwid": 26.6, "geely": 13.9, "jac": 0, "dolphin": 0})

    def test_igual_80(self):
        self._aprox(self._potencias(80, "igual"),
                    {"kwid": 21.183333, "geely": 21.183333, "jac": 16.45, "dolphin": 21.183333})

    def test_prioridade_80(self):
        self._aprox(self._potencias(80, "prioridade"), {"kwid": 26.6, "geely": 53.4, "jac": 0, "dolphin": 0})

    def test_bangkok_pico_no_limite(self):
        for divisao in ("igual", "prioridade"):
            sub = validar.normalizar({"agencia": "Bangkok", "carregadores": {"ac_7": 2, "dc_30": 1},
                                      "entrada": "b3_45", "politica": {"divisao": divisao}}, self.cen)
            res = motor.simular(self.cen, sub)
            ini, fim = tempo.JANELA_PUBLICA
            met = medicao.metricas(res.retiradas, res.nao_atendidos, res.bins, ini, fim)
            self.assertLessEqual(met["pico_kw"], 40.5 + 1e-6)


if __name__ == "__main__":
    unittest.main()
