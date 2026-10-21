"""Etapa 2: retirada e devolução sem recarga (regulamento 4.1, 5.1, 6.3.1)."""
import dataclasses
import sys
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from kickoff import dados, medicao, motor, tempo, validar  # noqa: E402
from kickoff.modelo import Contrato  # noqa: E402

TEM_BANGKOK = (RAIZ / "dados" / "Bangkok").is_dir()


def motor_vazio(cen, carregadores=None, politica=None):
    """Motor com o cenário sem frota e sem contratos, para montar o pátio à mão."""
    vazio = dataclasses.replace(cen, veiculos=[], contratos=[])
    sub = validar.normalizar({"agencia": cen.agencia.nome, "carregadores": carregadores or {"ac_7": 1},
                              "entrada": cen.agencia.entrada_existente, "politica": politica}, vazio)
    m = motor.Motor(vazio, sub)
    m.aberta = True
    return m


def carro(m, vid, modelo, soc):
    mod = m.cen.modelos[modelo]
    v = motor.Veiculo(vid, mod, mod.rank, soc)
    m.veiculos[vid] = v
    m.patio[vid] = v
    return v


def contrato(cid, categoria, rank, km=None):
    return Contrato(cid, categoria, rank, 0, None, 0.0, km)


@unittest.skipUnless(TEM_BANGKOK, "dados/Bangkok ausentes")
class EscolhaDoCarro(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cen = dados.carregar(RAIZ / "dados", "Bangkok")

    def _patio(self, soc_geely):
        m = motor_vazio(self.cen)
        carro(m, "geely", "Geely EX2 Pro", soc_geely)
        mini = carro(m, "mini", "BYD Dolphin Mini GS", 95.0)
        mini.plugado = True
        carro(m, "mg4", "MG4 Urban Comfort", 90.0)
        carro(m, "jac", "JAC E-JS1", 100.0)
        return m

    def test_631_geely_sem_upgrade_menor_soc(self):
        m = self._patio(82.0)
        self.assertEqual(m.escolher_carro(contrato("c", "Prata", 2), 0).id, "geely")

    def test_631_geely_abaixo_de_80_sai_mini(self):
        m = self._patio(78.0)
        self.assertEqual(m.escolher_carro(contrato("c", "Prata", 2), 0).id, "mini")

    def test_631_sem_prata_apto_upgrade_mg4(self):
        m = self._patio(78.0)
        m.patio.pop("mini")
        self.assertEqual(m.escolher_carro(contrato("c", "Prata", 2), 0).id, "mg4")

    def test_nunca_downgrade_e_fechada_ninguem_retira(self):
        m = self._patio(82.0)
        self.assertIsNone(m.escolher_carro(contrato("c", "Diamante", 4), 0))
        m.aberta = False
        self.assertIsNone(m.escolher_carro(contrato("c", "Prata", 2), 0))

    def test_desempate_nao_plugado_depois_id(self):
        m = motor_vazio(self.cen)
        b = carro(m, "b", "JAC E-JS1", 85.0)
        a = carro(m, "a", "JAC E-JS1", 85.0)
        a.plugado = True
        self.assertIs(m.escolher_carro(contrato("c", "Bronze", 1), 0), b)
        b.plugado = True
        self.assertIs(m.escolher_carro(contrato("c", "Bronze", 1), 0), a)


@unittest.skipUnless(TEM_BANGKOK, "dados/Bangkok ausentes")
class Devolucao(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cen = dados.carregar(RAIZ / "dados", "Bangkok")

    def test_41_soc_pela_autonomia_com_teto(self):
        m = motor_vazio(self.cen)
        v = carro(m, "geely", "Geely EX2 Pro", 90.0)  # 289 km
        self.assertAlmostEqual(m.soc_devolucao(v, contrato("c", "Prata", 2, km=144.5)), 50.0)
        self.assertEqual(m.soc_devolucao(v, contrato("c", "Prata", 2, km=289)), 90.0)

    def test_abaixo_de_80_vai_para_fila(self):
        m = motor_vazio(self.cen)
        m.montado = True
        v = carro(m, "geely", "Geely EX2 Pro", 90.0)
        m.patio.clear()
        m.aberta = False  # fechada: fica na fila, sem plugar
        m.on_devolucao("geely", 50.0, 2000)
        self.assertTrue(v.na_fila)
        self.assertEqual(v.entrou_fila_t, 2000)

    def test_bangkok_toda_retirada_apta(self):
        sub = validar.normalizar({"agencia": "Bangkok", "carregadores": {"ac_7": 2}, "entrada": "b3_45"}, self.cen)
        res = motor.simular(self.cen, sub)
        self.assertTrue(res.retiradas)
        for r in res.retiradas:
            self.assertGreaterEqual(r.soc, 80.0 - 1e-9)
            self.assertGreaterEqual(r.rank_entregue, r.rank_pedido)
        ini, fim = tempo.JANELA_PUBLICA
        met = medicao.metricas(res.retiradas, res.nao_atendidos, res.bins, ini, fim)
        self.assertEqual(met["contratos"], len(self.cen.contratos))


if __name__ == "__main__":
    unittest.main()
