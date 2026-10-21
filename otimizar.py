"""Busca local da melhor solução de cada agência com o motor local (maximiza a nota).

  python3 otimizar.py AG [AG ...] [--salvar] [--iter N] [--eventos ARQ ...]

Parte de sementes simples (um tipo de carregador, entrada existente) e, a cada passo, avalia em
paralelo os vizinhos da melhor solução: +-1 carregador, troca de um tipo por outro, outra entrada,
outra demanda contratada e outra política. Para quando nenhum vizinho melhora. Com --salvar, grava
em solucoes/<AG>.json se for melhor que a solução já salva. Eventos: padrão validacao/eventos_*.json.
"""
import argparse
import json
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))

from kickoff import validar  # noqa: E402
from kickoff.dados import carregar  # noqa: E402
from simular import avaliar, ler_eventos  # noqa: E402

_CEN: dict = {}


def nota(dados: str, cat, eventos, sub: dict) -> float:
    """Nota da submissão; inválida ou com violação vale -inf."""
    out = avaliar(sub, _CEN, Path(dados), cat, eventos, False)
    if not out["valido"] or out.get("violacoes") or out.get("nota") is None:
        return float("-inf")
    return out["nota"]


def chave(sub: dict) -> str:
    return json.dumps(sub, sort_keys=True)


def montar(ag, car, entrada, demanda, pol) -> dict:
    sub = {"agencia": ag, "carregadores": {k: n for k, n in sorted(car.items()) if n > 0}, "entrada": entrada}
    if demanda is not None:
        sub["demanda_contratada_kw"] = demanda
    sub["politica"] = dict(pol)
    return sub


class Busca:
    def __init__(self, ag, dados, cat, eventos, pool):
        self.ag, self.dados, self.cat, self.eventos, self.pool = ag, dados, cat, eventos, pool
        self.cen = carregar(dados, ag, cat)
        ex = self.cen.entradas[self.cen.agencia.entrada_existente]
        self.entradas = [e for e in self.cen.entradas.values()
                         if e.id == ex.id or (e.kva >= validar.B3_KVA and e.kw_util >= ex.kw_util)]
        self.cache: dict = {}

    def saidas(self, car) -> int:
        return sum(n * self.cen.carregadores[k].saidas for k, n in car.items())

    def avaliar(self, subs) -> list:
        novos = [s for s in {chave(s): s for s in subs}.values() if chave(s) not in self.cache
                 and not validar.validar(s, self.cen)]
        for s, v in zip(novos, self.pool.map(nota, [str(self.dados)] * len(novos), [self.cat] * len(novos),
                                             [self.eventos] * len(novos), novos)):
            self.cache[chave(s)] = v
        return [(self.cache.get(chave(s), float("-inf")), s) for s in subs]

    def sementes(self) -> list:
        ex, vagas = self.cen.agencia.entrada_existente, self.cen.agencia.vagas
        dem = None
        subs = []
        for c in self.cen.carregadores.values():
            maxn = vagas // c.saidas
            for n in sorted({1, max(1, maxn // 2), maxn}):
                if n < 1:
                    continue
                for pol in ({"prioridade": "proxima_retirada", "divisao": "prioridade", "evitar_ponta": False},
                            {"prioridade": "proxima_retirada", "divisao": "prioridade", "evitar_ponta": True}):
                    subs.append(montar(self.ag, {c.id: n}, ex, dem, pol))
        return subs

    def vizinhos(self, sub) -> list:
        car, ent, pol = dict(sub["carregadores"]), sub["entrada"], sub["politica"]
        dem = sub.get("demanda_contratada_kw")
        tipos, vagas = list(self.cen.carregadores), self.cen.agencia.vagas
        out = []
        mudancas = [{k: +1} for k in tipos] + [{k: -1} for k in car]
        mudancas += [{a: -1, b: +1} for a in car for b in tipos if a != b]
        for m in mudancas:
            novo = dict(car)
            for k, d in m.items():
                novo[k] = novo.get(k, 0) + d
            if all(n >= 0 for n in novo.values()) and sum(novo.values()) > 0 and self.saidas(novo) <= vagas:
                out.append(montar(self.ag, novo, ent, dem, pol))
        for e in self.entradas:
            if e.id != ent:
                out.append(montar(self.ag, car, e.id, None, pol))
        e = self.cen.entradas[ent]
        if e.kva > validar.B3_KVA:
            teto = validar.teto_demanda(e)
            atual = dem if dem is not None else teto
            for d in (-50, -20, -10, 10, 20, 50):
                v = atual + d
                if validar.DEMANDA_MIN_KW <= v <= teto:
                    out.append(montar(self.ag, car, ent, None if v == teto else v, pol))
        for k, valores in validar.MENU.items():
            for v in valores:
                if pol.get(k) != v:
                    out.append(montar(self.ag, car, ent, dem, {**pol, k: v}))
        return out

    def rodar(self, inicio=None, max_iter=30, log=print):
        t0 = time.time()
        cands = self.sementes() + ([inicio] if inicio else [])
        melhor_v, melhor = max(self.avaliar(cands), key=lambda x: x[0])
        log(f"[{self.ag}] semente: {melhor_v:.1f} {chave(melhor)} ({time.time() - t0:.0f}s)")
        for i in range(max_iter):
            v, s = max(self.avaliar(self.vizinhos(melhor)), key=lambda x: x[0])
            if v <= melhor_v + 1e-9:
                break
            melhor_v, melhor = v, s
            log(f"[{self.ag}] passo {i + 1}: {melhor_v:.1f} {chave(melhor)} ({time.time() - t0:.0f}s)")
        log(f"[{self.ag}] fim: {melhor_v:.1f} após {len(self.cache)} simulações ({time.time() - t0:.0f}s)")
        return melhor_v, melhor


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(prog="python3 otimizar.py")
    ap.add_argument("agencias", nargs="+")
    ap.add_argument("--dados", type=Path, default=AQUI / "dados")
    ap.add_argument("--solucoes", type=Path, default=AQUI / "solucoes")
    ap.add_argument("--eventos", nargs="*", type=Path, help="padrão: validacao/eventos_*.json")
    ap.add_argument("--iter", type=int, default=30)
    ap.add_argument("--salvar", action="store_true")
    a = ap.parse_args(argv)
    cat = json.loads((a.dados / "catalogo.json").read_text(encoding="utf-8-sig"))
    arquivos = a.eventos if a.eventos is not None else sorted((AQUI / "validacao").glob("eventos_*.json"))
    eventos = [e for p in arquivos for e in ler_eventos(p)]
    log = lambda m: print(m, flush=True)  # noqa: E731
    with ProcessPoolExecutor() as pool:
        for ag in a.agencias:
            arq = a.solucoes / f"{ag}.json"
            atual = json.loads(arq.read_text(encoding="utf-8-sig")) if arq.exists() else None
            busca = Busca(ag, a.dados, cat, eventos, pool)
            atual_v = busca.avaliar([atual])[0][0] if atual else float("-inf")
            v, sub = busca.rodar(atual, a.iter, log)
            if a.salvar and v > atual_v:
                a.solucoes.mkdir(exist_ok=True)
                arq.write_text(json.dumps(sub, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
                log(f"[{ag}] salvo em {arq} ({atual_v:.1f} -> {v:.1f})")


if __name__ == "__main__":
    main()
