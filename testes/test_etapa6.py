"""Etapa 6: as três `prioridade` da fila (6.3.3)."""
import dataclasses
import sys
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from kickoff import dados, medicao, motor, tempo, validar  # noqa: E402
from test_etapa2 import TEM_BANGKOK, carro, contrato, motor_vazio  # noqa: E402


@unittest.skipUnless(TEM_BANGKOK, "dados/Bangkok ausentes")
class Exemplo633(unittest.TestCase):
    """A(Bronze 30%, 55.5 km), B(Prata 20%, 56.0 km), C(Ouro 55%), D(Diamante 40%)."""

    @classmethod
    def setUpClass(cls):
        cls.cen = dados.carregar(RAIZ / "dados", "Bangkok")

    def _ordem(self, prioridade):
        m = motor_vazio(self.cen, politica={"prioridade": prioridade})
        m.cen = dataclasses.replace(m.cen, contratos=[
            dataclasses.replace(contrato("c1", "Ouro", 3), retirada_t=100),
            dataclasses.replace(contrato("c2", "Prata", 2), retirada_t=200),
            dataclasses.replace(contrato("c3", "Bronze", 1), retirada_t=300),
        ])
        m.aberta = False
        for i, (vid, modelo, soc) in enumerate((("A", "Renault Kwid E-Tech", 30.0),
                                                ("B", "BYD Dolphin Mini GS", 20.0),
                                                ("C", "BYD Dolphin GS", 55.0),
                                                ("D", "Leapmotor B10 BEV", 40.0))):
            v = carro(m, vid, modelo, soc)
            m.patio.pop(vid)
            m.entrar_patio(v, float(i))
        m.ordenar_fila(50.0)
        return [v.id for v in m.fila]

    def test_menor_soc(self):
        self.assertEqual(self._ordem("menor_soc"), list("ABDC"))

    def test_chegada(self):
        self.assertEqual(self._ordem("chegada"), list("ABCD"))

    def test_proxima_retirada(self):
        self.assertEqual(self._ordem("proxima_retirada"), list("CDBA"))

    def test_bangkok_proxima_retirada_prioridade(self):
        sub = validar.normalizar({"agencia": "Bangkok", "carregadores": {"ac_7": 6}, "entrada": "b3_45",
                                  "politica": {"prioridade": "proxima_retirada", "divisao": "prioridade"}}, self.cen)
        res = motor.simular(self.cen, sub)
        ini, fim = tempo.JANELA_PUBLICA
        met = medicao.metricas(res.retiradas, res.nao_atendidos, res.bins, ini, fim)
        self.assertEqual(res.violacoes, [])
        self.assertLessEqual(met["pico_kw"], 40.5 + 1e-6)


if __name__ == "__main__":
    unittest.main()
