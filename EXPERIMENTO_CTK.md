# Experimento CustomTkinter + drawsvg

Branch: `codex/customtkinter-drawsvg`, criada a partir de `94ace73`.
A referência da main foi preservada. Este experimento compara uma interface
escrita diretamente em Python com a versão Qt Designer/Matplotlib existente.

## Executar

O ambiente separado já foi preparado nesta máquina. Na raiz:

```powershell
.\.venv-ctk\Scripts\python.exe gui_ctk.py exemplos/configuracao.txt
```

Para reproduzir o ambiente, use o Python 3.11 já configurado para o projeto:

```powershell
uv venv --python .venv-windows/Scripts/python.exe .venv-ctk
uv pip install --python .venv-ctk/Scripts/python.exe -r requirements-ctk.txt
```

Exportação independente, sem abrir janela e sem importar Tkinter, Qt ou Matplotlib:

```powershell
.\.venv-ctk\Scripts\python.exe gantt_svg.py exemplos/configuracao.txt gantt.svg
```

O diretório de destino deve existir. A CLI executa até o fim; a exportação pela
janela salva somente o prefixo selecionado, independente do zoom.

## Como explicar o código

- `engine.py`, `models.py`, `scheduler.py` e `parser.py`: mesmos motor e dados da main.
- `linha_tempo.py`: coleta de intervalos extraída da versão existente, sem alteração
  de regra. Ambos os Gantts usam essa função, que não importa biblioteca gráfica.
- `gui_ctk.py`: monta os controles em Python, chama operações do motor e mostra os
  dados do snapshot. Execução em lotes com `after()` devolve controle à janela.
- `gantt_svg.py`: calcula o desenho e chama quatro operações: retângulo, linha,
  texto e polígono. `DesenhoCanvas` envia essas operações ao Canvas do Tkinter;
  `DesenhoSVG` envia ao drawsvg. Há uma única definição dos símbolos e da legenda.

CustomTkinter fornece controles e aparência; o Canvas público do Tkinter desenha
na tela; drawsvg serializa o desenho em SVG. O código do projeto posiciona os
intervalos e os eventos. Não usamos CTkCanvas interno nem escrevemos XML manualmente.

Fontes: [CustomTkinter](https://github.com/TomSchimansky/CustomTkinter),
[Canvas](https://www.tcl-lang.org/man/tcl8.6/TkCmd/canvas.htm),
[drawsvg](https://github.com/cduck/drawsvg).

## Fluxos disponíveis

- Abrir qualquer configuração e preservar a simulação anterior se o arquivo falhar.
- Avançar/retroceder, inspecionar tarefa e eventos do snapshot.
- Editar ingresso, duração, período, prazo, cor e estado pela API do motor.
- Alterar RM/EDF, quantum e CPUs pela mesma API transacional da versão Qt.
- Executar em lotes sem desenhar a cada tick; informar suspensão que impede terminar.
- Zoom horizontal e barras de rolagem do Canvas. Zoom não modifica a simulação.
- SVG vetorial completo do prefixo selecionado, preservando cores históricas,
  CPUs, suspensão, ordem dos IDs, eventos e sorteio nas trilhas das selecionadas.
- Imagem final automática ao concluir pela janela, com sufixo para preservar
  arquivos existentes e mensagem em caso de falha de escrita.

## Verificação e limites

**12 testes do experimento aprovados**, incluindo janelas reais Tk, edição rejeitada
e aceita, histórico/configuração, SVG, caracteres especiais, suspensão, encerramento,
25 tarefas com rolagem e controles na janela mínima. Os **106 testes anteriores**
passaram no ambiente Qt após a extração da coleta compartilhada. Executar:

```powershell
.\.venv-ctk\Scripts\python.exe -B -m unittest -v test.test_experimento_ctk
.\.venv-windows\Scripts\python.exe -B -m unittest discover -q
```

No ambiente Qt, os testes do experimento são ignorados quando suas dependências
não estão instaladas. No ambiente CTK, execute o módulo específico: os testes
antigos de Matplotlib exigem o ambiente Qt. O SVG foi renderizado e inspecionado;
a captura da janela pelo controle nativo não foi confiável nesta sessão.

Este é um protótipo comparável, ainda precisa de avaliação visual do autor. Não foi
gerado executável CustomTkinter nem migrado o script de distribuição Qt. O zoom
horizontal recalcula as coordenadas dos elementos, mantendo a fonte fixa; detalhes
muito estreitos precisam de aproximação. SVG conserva a escala padrão de 24 px/tick,
sem cortar a linha do tempo pelo viewport da janela.

Sugestões completas de valores padrão e inclusão/remoção de tarefas durante a
simulação continuam pendências do Projeto A. As regras do motor e os exemplos do
capítulo permanecem iguais. O modo de apresentação e a toolbar Matplotlib não fazem
parte desta interface experimental.
