"""Painel: avalia a solução de cada agência com o motor local, lado a lado.

  python3 painel.py [--porta 8766] [--dados DIR] [--solucoes DIR] [--eventos ARQ ...] [--sem-navegador]

Cada agência tem a sua solução em `solucoes/<Agencia>.json` (uma submissão). O painel roda o motor
em todas (em paralelo, um processo por agência), mostra nota, atendimento, custo e séries, e deixa
testar variações e salvar a melhor. Eventos: padrão `validacao/eventos_*.json`.
Abre http://localhost:8766. Só biblioteca padrão.
"""
import argparse
import json
import sys
import threading
import webbrowser
from concurrent.futures import ProcessPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))

from cliente import Estado  # noqa: E402
from kickoff import validar  # noqa: E402
from simular import avaliar, ler_eventos  # noqa: E402

PAGINA = AQUI / "painel.html"

_CENARIOS: dict = {}  # cache por processo: hash do catálogo -> {agência: Cenario}


def rodar(dados: str, sub: dict, cat, eventos: list) -> dict:
    """Roda num processo do pool: simula `sub` com séries e anexa o limite da agência."""
    cens = _CENARIOS.setdefault(json.dumps(cat, sort_keys=True), {})
    out = avaliar(sub, cens, Path(dados), cat, eventos, True)
    if out["valido"]:
        cen = cens[sub["agencia"]]
        out["limite_kw"] = validar.limite_kw(validar.normalizar(sub, cen), cen)
    return out


class Painel(Estado):
    def __init__(self, dados: Path, solucoes: Path, eventos: list):
        super().__init__(dados)
        self.solucoes = solucoes
        self.eventos = eventos
        self.pool = ProcessPoolExecutor()
        self.trava = threading.Lock()
        self.resultados: dict = {}  # (submissão, mtime do catálogo) -> Future

    def arquivo(self, ag: str) -> Path:
        if ag not in self.agencias():
            raise SystemExit(f"agência desconhecida: {ag!r}")
        return self.solucoes / f"{ag}.json"

    def solucao(self, ag: str):
        p = self.arquivo(ag)
        return json.loads(p.read_text(encoding="utf-8-sig")) if p.exists() else None

    def resumo(self) -> list:
        return [{"nome": ag, "tem_solucao": (self.solucoes / f"{ag}.json").exists(),
                 "eventos": self.resumo_eventos(ag)}
                for ag in self.agencias()]

    def resultado(self, sub: dict) -> dict:
        cat = self.catalogo()
        chave = (json.dumps(sub, sort_keys=True), self.cat_mtime)
        with self.trava:
            fut = self.resultados.get(chave)
            if fut is None:
                fut = self.resultados[chave] = self.pool.submit(rodar, str(self.dados), sub, cat, self.eventos)
        return fut.result()

    def avaliar(self, ag: str, sub=None) -> dict:
        sub = sub if sub is not None else self.solucao(ag)
        out = {"agencia": self.agencia(ag), "solucao": sub, "eventos": self.resumo_eventos(ag)}
        if sub is not None:
            if sub.get("agencia") != ag:
                raise SystemExit(f"a submissão é da agência {sub.get('agencia')!r}, não de {ag!r}")
            out["resultado"] = self.resultado(sub)
        return out

    def resumo_eventos(self, ag: str) -> list:
        return [e for e in self.eventos if len(e) > 1 and e[1] == ag]

    def salvar(self, sub: dict) -> dict:
        ag = sub.get("agencia")
        out = self.avaliar(ag, sub)
        if not out["resultado"]["valido"]:
            raise SystemExit("submissão inválida: " + "; ".join(out["resultado"]["erros"]))
        self.solucoes.mkdir(exist_ok=True)
        self.arquivo(ag).write_text(json.dumps(sub, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        return out


def handler(painel: Painel):
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
            nome = parse_qs(u.query).get("nome", [""])[0]
            if u.path == "/":
                body = PAGINA.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            elif u.path == "/api/agencias":
                self._tentar(painel.resumo)
            elif u.path == "/api/avaliar":
                self._tentar(lambda: painel.avaliar(nome))
            else:
                self._json({"erro": "não encontrado"}, 404)

        def do_POST(self):
            rota = urlparse(self.path).path
            if rota not in ("/api/avaliar", "/api/salvar"):
                return self._json({"erro": "não encontrado"}, 404)
            n = int(self.headers.get("Content-Length") or 0)
            try:
                sub = json.loads(self.rfile.read(n) or b"{}")
            except json.JSONDecodeError as e:
                return self._json({"erro": f"JSON inválido: {e}"}, 400)
            if not isinstance(sub, dict):
                return self._json({"erro": "a submissão deve ser um objeto JSON"}, 400)
            if rota == "/api/salvar":
                self._tentar(lambda: painel.salvar(sub))
            else:
                self._tentar(lambda: painel.avaliar(sub.get("agencia"), sub))

        def log_message(self, *args):
            pass

    return H


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(prog="python3 painel.py")
    ap.add_argument("--porta", type=int, default=8766)
    ap.add_argument("--dados", type=Path, default=AQUI / "dados")
    ap.add_argument("--solucoes", type=Path, default=AQUI / "solucoes")
    ap.add_argument("--eventos", nargs="*", type=Path, help="padrão: validacao/eventos_*.json")
    ap.add_argument("--sem-navegador", action="store_true")
    a = ap.parse_args(argv)
    arquivos = a.eventos if a.eventos is not None else sorted((AQUI / "validacao").glob("eventos_*.json"))
    eventos = [e for p in arquivos for e in ler_eventos(p)]
    srv = ThreadingHTTPServer(("127.0.0.1", a.porta), handler(Painel(a.dados, a.solucoes, eventos)))
    url = f"http://localhost:{a.porta}"
    print(f"Painel das agências em {url} (Ctrl+C para sair)")
    if not a.sem_navegador:
        webbrowser.open(url)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
