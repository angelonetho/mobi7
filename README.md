# mobi7: recarga de frota elétrica nas agências

Simulador da operação de recarga de carros elétricos em agências de aluguel, feito para o GameDay mobi7. Para cada agência, uma solução escolhe os carregadores, a entrada elétrica, a demanda contratada e a política da fila. O motor simula 28 dias de retiradas e devoluções e calcula a nota do regulamento.

Só Python 3.10+ e biblioteca padrão; nada para instalar.

## Como usar

```bash
python3 painel.py                  # dashboard em http://localhost:8766
python3 otimizar.py Hanoi --salvar # procura a melhor solução e grava em solucoes/
python3 simular.py solucoes/Hanoi.json
python3 -m unittest discover -s testes
```

O dashboard mostra todas as agências lado a lado (nota, atendimento, custo de obra, pico de potência) e, para a agência escolhida, as séries de 15 minutos, a composição da nota e um formulário para testar variações e salvar a melhor.

## Estrutura

| Caminho | O que é |
|---|---|
| `kickoff/motor.py` | Simulador de eventos discretos: retirada, fila, plug, divisão de potência, ponta e eventos |
| `kickoff/` (demais) | Leitura dos dados, validação, curva de carga, medição e nota |
| `solucoes/` | A solução atual de cada agência (uma submissão JSON por arquivo) |
| `painel.py`, `painel.html` | Dashboard web |
| `otimizar.py` | Busca local que maximiza a nota com o motor |
| `simular.py`, `comparar.py` | Simulação por linha de comando e comparação com a resposta do juiz |
| `dados/` | Kits das agências e `catalogo.json` com custos e pesos |
| `validacao/` | Submissões de Bangkok conferidas com o juiz e eventos ativos |
| `LEIAME.md` | Guia original do kit de kickoff |

## Soluções atuais

Notas do motor local na janela pública, com os eventos de `validacao/`. Em Bangkok o motor bate com o juiz; nas demais agências ainda não foi conferido.

| Agência | Nota | Atendimento | Solução |
|---|---:|---:|---|
| Bangkok | 3.100,0 | 100% | 3× ac_7, b3_45, sem carga na ponta |
| Hanoi | 6.211,0 | 99,91% | 5× ac_7 e 1× dc_30, b3_75 |
| Istanbul | 3.624,0 | 100% | 1× ac_7 e 3× dc_30, b3_75, divisão igual, sem carga na ponta |
| Lisbon | 12.026,1 | 99,94% | 7× ac_7 e 1× dc_30, a4_150 com 80 kW |
| Marrakech | 5.849,0 | 100% | 9× ac_7 e 1× dc_30, a4_150, sem carga na ponta |
| Vienna | 9.400,0 | 100% | 1× dc_30, a4_150 com 30 kW, sem carga na ponta |
| Zurich | 2.978,9 | 99,31% | 1× ac_7 e 1× dc_60x2, b3_75 |

Todas usam fila por `proxima_retirada` e, salvo indicação, divisão por `prioridade`.

## Conferir com o juiz

Com `GAMEDAY_URL` e `GAMEDAY_TOKEN` definidos (nunca no repositório):

```bash
python3 -m kickoff.api teste Bangkok solucoes/Bangkok.json --completo --salvar resp.json
python3 comparar.py solucoes/Bangkok.json resp.json
```

Bangkok é grátis; as outras agências gastam m7Coins.
