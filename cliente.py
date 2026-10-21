"""Cliente local: monta submissões num formulário e roda o motor da equipe no navegador.

  python3 cliente.py [--porta 8765] [--dados DIR] [--sem-navegador]

Abre http://localhost:8765. Usa só a biblioteca padrão; o motor e as métricas são os de simular.py.
"""
import argparse
import json
import sys
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))

from kickoff import validar  # noqa: E402
from kickoff.dados import carregar  # noqa: E402
from simular import avaliar  # noqa: E402

PAGINA = AQUI / "cliente.html"


class Estado:
    def __init__(self, dados: Path):
        self.dados = dados
        self.cenarios: dict = {}
        self.cat_mtime = None

    def catalogo(self):
        p = self.dados / "catalogo.json"
        mtime = p.stat().st_mtime if p.exists() else None
        if mtime != self.cat_mtime:  # catálogo novo (pós-H4): recarrega os cenários com os custos
            self.cenarios.clear()
            self.cat_mtime = mtime
        return json.loads(p.read_text(encoding="utf-8-sig")) if mtime else None

    def cenario(self, ag: str):
        cat = self.catalogo()
        if ag not in self.cenarios:
            self.cenarios[ag] = carregar(self.dados, ag, cat)
        return self.cenarios[ag], cat

    def agencias(self) -> list:
        return sorted(p.name for p in self.dados.iterdir() if (p / "agencias.md").exists())

    def agencia(self, ag: str) -> dict:
        cen, cat = self.cenario(ag)
        a = cen.agencia
        ex = cen.entradas[a.entrada_existente]
        entradas = []
        for e in cen.entradas.values():
            ok = e.id == a.entrada_existente or (e.kva >= validar.B3_KVA and e.kw_util >= ex.kw_util)
            entradas.append({"id": e.id, "descricao": e.descricao, "kva": e.kva, "kw_util": e.kw_util,
                             "custo": e.custo, "permitida": ok, "a4": e.kva > validar.B3_KVA,
                             "teto_demanda": validar.teto_demanda(e) if e.kva > validar.B3_KVA else None})
        return {
            "nome": a.nome, "vagas": a.vagas, "frota": a.frota, "existente": a.entrada_existente,
            "horario": a.horario, "contratos": len(cen.contratos), "tem_catalogo": cat is not None,
            "carregadores": [{"id": c.id, "modelo": c.modelo, "tipo": c.tipo, "potencia_kw": c.potencia_kw,
                              "saidas": c.saidas, "custo": c.custo} for c in cen.carregadores.values()],
            "entradas": entradas,
            "menu": {k: list(v) for k, v in validar.MENU.items()},
            "demanda": {"min": validar.DEMANDA_MIN_KW, "passo": validar.DEMANDA_PASSO_KW},
        }

    def simular(self, sub: dict) -> dict:
        ag = sub.get("agencia")
        cen, cat = self.cenario(ag)
        out = avaliar(sub, self.cenarios, self.dados, cat, [], True)
        if out["valido"]:
            out["limite_kw"] = validar.limite_kw(validar.normalizar(sub, cen), cen)
        return out


def handler(estado: Estado):
    class H(BaseHTTPRequestHandler):
        def _json(self, obj, status=200):
            body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _tentar(self, fn):
            try:
                self._json(fn())
            except SystemExit as e:  # dados.carregar/avaliar avisam com SystemExit
                self._json({"erro": str(e)}, 400)
            except Exception as e:  # noqa: BLE001 (mostra o erro na página em vez de derrubar o servidor)
                self._json({"erro": f"{type(e).__name__}: {e}"}, 500)

        def do_GET(self):
            u = urlparse(self.path)
            if u.path == "/":
                body = PAGINA.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            elif u.path == "/api/agencias":
                self._tentar(estado.agencias)
            elif u.path == "/api/agencia":
                nome = parse_qs(u.query).get("nome", [""])[0]
                self._tentar(lambda: estado.agencia(nome))
            else:
                self._json({"erro": "não encontrado"}, 404)

        def do_POST(self):
            if urlparse(self.path).path != "/api/simular":
                return self._json({"erro": "não encontrado"}, 404)
            n = int(self.headers.get("Content-Length") or 0)
            try:
                sub = json.loads(self.rfile.read(n) or b"{}")
            except json.JSONDecodeError as e:
                return self._json({"erro": f"JSON inválido: {e}"}, 400)
            self._tentar(lambda: estado.simular(sub))

        def log_message(self, *args):
            pass

    return H


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(prog="python3 cliente.py")
    ap.add_argument("--porta", type=int, default=8765)
    ap.add_argument("--dados", type=Path, default=AQUI / "dados")
    ap.add_argument("--sem-navegador", action="store_true")
    a = ap.parse_args(argv)
    srv = ThreadingHTTPServer(("127.0.0.1", a.porta), handler(Estado(a.dados)))
    url = f"http://localhost:{a.porta}"
    print(f"Cliente do motor em {url} (Ctrl+C para sair)")
    if not a.sem_navegador:
        webbrowser.open(url)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
