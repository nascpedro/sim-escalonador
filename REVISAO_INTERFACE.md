# Revisão específica da interface — Projeto A

## Estado atual

A navegação da etapa 1 foi preservada, com os opcionais modo apresentação e acompanhamento automático removidos. A configuração global agora é transacional no motor e o algoritmo pertence ao snapshot. Os campos de quantum e CPUs usam texto validado, sem truncamento pelos antigos limites de 999/64.

O Gantt agrupa retângulos e marcadores em coleções; a identificação de CPU acompanha o trecho visível. O sorteio marca apenas as selecionadas nas próprias trilhas. O SVG final é gerado automaticamente ao concluir, sem sobrescrever arquivos existentes, tanto no último passo manual como na execução completa. Falhas de escrita preservam os resultados.

Validação atual: **106 testes aprovados**, incluindo o modelo FIFO, exemplos RM/EDF do capítulo, histórico/configuração, GUI, navegação e exportação automática. Capturas locais de tela completa e zoom estão em build/janela-final.png e build/janela-zoom.png (artefatos de desenvolvimento, não versionados). O build atual inclui o formulário .ui.

As seções abaixo guardam o diagnóstico e o plano originais; referências a controles removidos e contagens anteriores são históricas. Pendências atuais estão somente em PENDENCIAS.md. O ensaio do autor e a homologação do ZIP em máquina limpa continuam necessários.

## Diagnóstico reproduzido antes da etapa 1

Sonda nativa Windows, janela de 1280 × 800 unidades lógicas, exemplo `exemplos/configuracao.txt` executado até o tick 185:

| Observação | Evidência / causa no código |
|---|---|
| Não há deslocamento efetivo pelas barras de rolagem | Canvas e viewport: ambos 903 × 358 pixels lógicos. Alcance das duas barras: zero. `setWidgetResizable(True)` ajusta o canvas ao espaço, sem definir um conteúdo maior ou um controle temporal próprio. |
| Eventos invadem margens após aproximar | Após cinco chamadas `zoom(0.8)`, intervalo X aproximadamente 62,19–122,81. Há 55 marcadores fora desse intervalo com recorte desativado por `clip_on=False`. A captura confirma marcadores sobre a margem esquerda e próximos da legenda. |
| O enquadramento não se mantém | Depois do zoom, retroceder devolve os limites X a 0–184. O desenho limpa a Figure, cria Axes novamente e define sempre o intervalo inteiro; a barra de navegação também é reiniciada. |
| Legenda perde conteúdo | A legenda Matplotlib fica cortada à direita na captura nativa. Existe outra legenda estática no `.ui`, com representação que precisa ser confrontada com `gantt.EVENTOS`. |
| Aplicar sem mudanças descarta futuro | Avançar cinco vezes, retroceder uma e aplicar os mesmos valores reduz o histórico de 6 para 5 snapshots. O descarte é incondicional. |
| Configuração contorna a API do motor | `aplicar_configuracao_sistema()` altera algoritmo, quantum, CPUs e campos dos TCBs diretamente. A semântica da alteração de algoritmo ao retroceder não está definida por snapshot. |
| Limites dos controles precisam de revisão | `.ui`: quantum de 0 a 999, CPUs de 1 a 64. Conferir casos válidos fora desses limites antes de aplicar valores exibidos ao estado. |

A barra Matplotlib existente oferece ferramentas de navegação, mas sua presença não substitui uma interação evidente nem corrige o recorte, a legenda ou a perda do enquadramento. A origem dos problemas inclui o desenho compartilhado, não apenas o formulário novo.

As primeiras quatro observações da tabela foram tratadas na etapa 1. Os defeitos de configuração continuam abertos. Na inspeção nativa também foi corrigido o mínimo rígido do contêiner do `.ui`, que escondia barras ao reduzir a janela; o ajuste é feito em `gui.py`, preservando o formulário.

Evidências locais, descartáveis: `C:/Users/pedro/AppData/Local/hermes/cache/scratch/revisao_interface_probe.py` e `revisao-interface-zoom.png`. As dimensões acima descrevem uma execução, não todas as resoluções/DPI.

## Etapa 1 — Navegação e desenho do Gantt (implementada)

**Objetivo:** poder percorrer uma simulação extensa sem perder detalhes, como ao navegar conteúdo maior que a área disponível.

Solução implementada:

- Barra horizontal Qt explícita controlando o intervalo temporal visível do Axes. Ela desloca a janela de tempo, sem precisar criar uma imagem com largura proporcional a uma simulação potencialmente enorme.
- Zoom altera a quantidade de ticks visíveis. Incluir **Ajustar tudo** para mostrar o prefixo inteiro; não confundir zoom visual com avanço da simulação.
- Altura legível por tarefa/trilha e rolagem vertical real quando o conteúdo exceder a área. O redimensionamento não deve comprimir indefinidamente todas as linhas.
- Guardar o enquadramento na integração da GUI e restaurá-lo depois do redesenho. Ao retroceder, ajustar apenas o que ultrapassar o prefixo disponível. Não exibir dados futuros salvos.
- Definir acompanhamento do tick atual sem arrancar o usuário de um trecho que ele está examinando. Preferir comportamento explícito a reposicionamento automático inesperado.
- Recortar os artistas fora do Axes, preservando a identificação de eventos exatamente nas extremidades do intervalo.
- Garantir legenda completa dentro da área disponível e uma única definição dos símbolos. Evitar duas legendas divergentes; manter a legenda da exportação integral.
- Manter a mesma rotina de desenho e exportação vetorial. A navegação é da GUI; exportar continua recompondo todo o prefixo numa Figure separada.

**Aceite:**

- [x] Com o exemplo completo, aproximar e deslocar do primeiro ao último trecho usando uma barra visível, sem ticks adicionais.
- [x] Com 25 tarefas, acessar a primeira e a última por rolagem vertical, sem comprimir todas as linhas.
- [x] Após avançar/retroceder, preservar um enquadramento ainda válido; nunca mostrar futuro salvo.
- [x] Marcadores recortados pelo Axes; textos de execução recortados pelo bloco e pelo Axes.
- [x] Legenda do gráfico acessível e inteira na Figure, janela mínima e maximizada, Windows em escala 125%. Na janela pequena, a legenda pode exigir rolagem vertical; isso não é corte da Figure.
- [x] Zoom/deslocamento não alteram histórico, CPU, sorteios ou relógio.
- [x] SVG contém o prefixo inteiro e sua legenda mesmo quando a tela mostra apenas um trecho.

Verificação: falhas iniciais reproduzidas nos testes de navegação/rolagem e nos testes do desenho, seguidas de correção. Suíte integrada: 96 testes aprovados. Sonda nativa com o exemplo até 185 ticks e cenário de 25 tarefas: barra temporal com alcance positivo após zoom, rolagem vertical de 1710 unidades na janela mínima 920 × 620, legenda dentro da Figure, histórico preservado e SVG integral. Também foi testada a janela maximizada. Não se presume equivalência para todos os monitores/DPI.

Evidências no scratch: `verificar_etapa1_native.py`, `etapa1-fim.png`, `etapa1-inicio-legenda.png`, `etapa1-muitas-tarefas-minima.png`, `etapa1-muitas-tarefas-maximizada.png` e `etapa1-exportado.svg`. O diretório scratch é descartável, não parte da distribuição.

## Etapa 2 — Configuração segura e inspeção

**Objetivo:** aplicar mudanças válidas sem corromper histórico ou alterar dados sem intenção.

- Não descartar o futuro se nenhum parâmetro mudou.
- Definir a semântica da troca de algoritmo no passado antes de implementá-la. O algoritmo hoje pertence à `Simulacao`, não ao snapshot; não prometer restauração histórica que o modelo não oferece.
- Concentrar a alteração de sistema numa operação do motor, verificando primeiro e efetivando depois. A GUI coleta valores e apresenta o resultado.
- Ao reduzir CPUs, preservar alocações válidas, liberar as removidas e tratar corretamente estado e fatia das tarefas interrompidas.
- Rever os limites dos controles diante do parser; valores carregados não podem ser silenciosamente substituídos por limites visuais.
- Validar sincronização entre seletor, tabela, painel de detalhes e diálogo de edição, incluindo erros, troca de arquivo e retrocesso.

**Aceite:** operação sem mudanças preserva todo o histórico; rejeição não modifica nada; edição aceita descarta somente o futuro; snapshots anteriores permanecem intactos. Exercitar redução/aumento de CPUs, alteração de quantum, RM/EDF e arquivos com valores fora dos limites atuais dos controles.

## Etapa 3 — Fechamento visual e resultado final

- Verificar o marcador de sorteio associado às tarefas efetivamente despachadas (`selecionadas`), inclusive mais de uma CPU e sorteio sem vencedor daquele grupo naquele tick. Não marcar todos os participantes como vencedores.
- Preservar a ordem física de IDs já correta: no exemplo, 3 acima de 2 acima de 1. Acrescentar teste por posição renderizada, não apenas por valor numérico de Y.
- Validar mensagens de erro e estados dos controles durante execução completa. O modo apresentação foi retirado da interface.
- Rever o painel de inspeção, cujos rótulos ficam comprimidos na janela mínima, e a apresentação da toolbar Matplotlib. Não confundir esses pontos ainda abertos com a correção do viewport do gráfico.
- Definir destino/nome/consentimento para sobrescrita antes de gerar automaticamente a imagem final exigida pelo requisito 2.4. Tratar falha de escrita sem perder resultados. Cobrir conclusão automática e último avanço manual.
- Reexecutar a suíte e os fluxos nativos: abrir, avançar, retroceder, editar, configurar, executar, navegar, exportar e fechar. Pedir avaliação de Pedro com um cenário real.

**Aceite:** fluxo de apresentação compreensível, eventos vinculados corretamente, erros claros e resultado final exportável integralmente. Só depois reconstruir o executável com o `.ui` incluído e validar fora do repositório/máquina de desenvolvimento.

## Fora desta revisão

Fila de ocorrências sobrepostas, política de valores padrão e empacotamento final continuam pendências separadas. Não tratá-las como aprovadas ou implementá-las incidentalmente. O PDF citado pelo Antigravity não foi reauditado aqui; as correções desta lista se apoiam no código atual, no enunciado e nas sondas executadas.

Registro histórico: as etapas 2 e 3 não foram iniciadas junto com a etapa 1; foram executadas posteriormente na revisão autorizada, conforme estado atual acima.

## Referências técnicas consultadas para o plano

- Qt, QScrollArea: https://doc.qt.io/qt-6/qscrollarea.html — dimensionamento do conteúdo e tamanho mínimo; inserir um widget numa área de rolagem não garante que haja conteúdo maior que o viewport.
- Qt, QScrollBar: https://doc.qt.io/qt-6/qscrollbar.html — faixa de valores, passo e tamanho de página para representar uma janela sobre conteúdo maior.
- Matplotlib, recorte dos artistas: https://matplotlib.org/stable/api/_as_gen/matplotlib.artist.Artist.set_clip_on.html — desativar recorte permite desenhar fora do Axes.
- Matplotlib, navegação: https://matplotlib.org/stable/users/interactive.html — ferramentas existentes de pan/zoom; a revisão deve reutilizar a biblioteca, não criar outro renderizador.
