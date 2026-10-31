"""Um único desenho Matplotlib para a tela e para a exportação vetorial.

Não importa Qt/pyplot, não escolhe backend e nunca executa a simulação.
"""
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from matplotlib.path import Path
from matplotlib.ticker import MaxNLocator

from models import EstadoTarefa

# Marcador, nome, cor e pista vertical dentro da linha da tarefa.
EVENTOS = {
    'chegada': ('v', 'Chegada', '#215e99', .85),
    'ativacao': ('^', 'Ativação', '#42692e', 1.1),
    'conclusao': ('o', 'Conclusão', '#176d58', 1.35),
    'perda_prazo': ('X', 'Perda de prazo', '#a62626', 1.6),
    'fim_quantum': ('s', 'Fim de quantum', '#855215', 1.85),
    'sorteio': ('D', 'Sorteio', '#6e3f97', .6),
}


def coletar_intervalos(estados, eventos, fim):
    """Converte eventos em trechos e une vizinhos sem atravessar eventos da tarefa."""
    fronteiras = set()
    for evento in eventos:
        ids = evento.get('ordem', []) if evento['tipo'] == 'sorteio' else [evento['id_tarefa']]
        fronteiras.update((id_, evento['tick']) for id_ in ids)
    grupos = {}
    for anterior, posterior in zip(estados, estados[1:]):
        cores = {t.id: '#' + t.cor.lstrip('#') for t in anterior.tarefas}
        trechos = []
        for tarefa in anterior.tarefas:
            if tarefa.estado_tarefa == EstadoTarefa.SUSPENSA:
                trechos.append(('suspensa', tarefa.id, None, '#151515', anterior.tick, posterior.tick))
        for evento in posterior.eventos:
            tipo, tick = evento['tipo'], evento['tick']
            if not 0 <= tick < fim:
                continue
            if tipo == 'execucao':
                id_ = evento['id_tarefa']
                trechos.append((tipo, id_, evento['id_cpu'], cores[id_], tick, tick + 1))
            elif tipo == 'cpu_desligada':
                trechos.append((tipo, None, evento['id_cpu'], '#d9dde2', tick, tick + 1))
        for tipo, id_, cpu, cor, a, b in trechos:
            grupo = grupos.setdefault((tipo, id_, cpu, cor), [])
            if grupo and grupo[-1][1] == a and (id_, a) not in fronteiras:
                grupo[-1][1] = b
            else:
                grupo.append([a, b])
    return grupos


def _desenhar_intervalos(ax, grupos, linhas, linhas_cpu):
    # Uma coleção por tarefa/CPU/cor, em vez de uma por retângulo.
    textos_cpu = []
    for indice, ((tipo, id_, cpu, cor), trechos) in enumerate(grupos.items()):
        y = linhas_cpu[cpu] if tipo == 'cpu_desligada' else linhas[id_]
        suspensa = tipo == 'suspensa'
        bloco = ax.broken_barh([(a, b-a) for a, b in trechos], (y, .45), facecolors=cor,
            edgecolors='#bcbcbc' if suspensa else '#526171', linewidth=.5,
            hatch='///' if suspensa else None, label=f'{tipo}: tarefa {id_}, CPU {cpu}')
        bloco.set_gid(f'{tipo}-{indice}')
        if tipo != 'execucao':
            continue
        # A CPU não muda ao expirar o quantum: um rótulo por execução contínua
        # basta. Os retângulos e os marcadores mantêm todas as fronteiras reais.
        rotulos = []
        for a, b in trechos:
            if rotulos and rotulos[-1][1] == a:
                rotulos[-1][1] = b
            else:
                rotulos.append([a, b])
        for a, b in rotulos:
            texto = ax.text((a+b)/2, y+.225, str(cpu), ha='center', va='center',
                fontsize=7, color='black', clip_on=True,
                bbox=dict(facecolor='white', edgecolor='none', pad=.2))
            limite = Path([(a, y), (b, y), (b, y+.45), (a, y+.45), (a, y)])
            texto.set_clip_path(limite, ax.transData)
            texto.get_bbox_patch().set_clip_path(limite, ax.transData)
            textos_cpu.append((a, b, texto))

    def posicionar_cpus(eixo):
        # Mantém a identificação dentro do trecho visível também após zoom/pan.
        esquerda, direita = sorted(eixo.get_xlim())
        for a, b, texto in textos_cpu:
            inicio, fim = max(a, esquerda), min(b, direita)
            texto.set_visible(inicio < fim)
            texto.set_x((inicio + fim) / 2)

    ax.callbacks.connect('xlim_changed', posicionar_cpus)


def _desenhar_eventos(ax, eventos, linhas):
    # Um scatter recebe todos os pontos do tipo na mesma trilha.
    grupos = {}
    for evento in eventos:
        tipo = evento['tipo']
        if tipo == 'sorteio':
            ids = evento.get('selecionadas', evento.get('ordem', []))
        else:
            ids = [evento['id_tarefa']]
        for id_ in ids:
            grupos.setdefault((tipo, id_), []).append(evento['tick'])
    for indice, ((tipo, id_), ticks) in enumerate(grupos.items()):
        marcador, nome, cor, deslocamento = EVENTOS[tipo]
        y = linhas[id_] + deslocamento
        artista = ax.scatter(ticks, [y] * len(ticks), marker=marcador, s=20,
            color=cor, zorder=4, clip_on=True, label=f'{nome}: tarefa {id_}')
        artista.set_gid(f'evento-{tipo}-{indice}')


def desenhar_gantt(simulacao, figura):
    """Repopula a mesma Figure e retorna Axes, lendo somente o prefixo visível.

    Os eventos de execução dizem quem trabalhou mesmo quando a CPU já está
    livre no snapshot seguinte. A cor e a suspensão pertencem ao anterior.
    GIDs identificam artistas; labels descrevem intervalos em coordenadas reais.
    """
    estados = simulacao.historico[:simulacao.instante_atual + 1]
    fim = estados[-1].tick
    ids = sorted({t.id for s in estados for t in s.tarefas},
                 key=lambda id_: (isinstance(id_, str), id_), reverse=True)
    cpus = list(dict.fromkeys(c.id_cpu for s in estados for c in s.cpus))
    figura.clear()
    figura.set_facecolor('white')
    figura.set_layout_engine('constrained')
    ax = figura.add_subplot(111)
    linhas = {id_: i * 2.3 for i, id_ in enumerate(ids)}
    eventos = [e for s in estados[1:] for e in s.eventos
               if e['tipo'] in EVENTOS and 0 <= e['tick'] <= fim]
    base = len(ids) * 2.3 + .6
    linhas_cpu = {cpu: base + i * .7 for i, cpu in enumerate(cpus)}
    intervalos = coletar_intervalos(estados, eventos, fim)
    _desenhar_intervalos(ax, intervalos, linhas, linhas_cpu)
    _desenhar_eventos(ax, eventos, linhas)

    posicoes = list(linhas.values()) + list(linhas_cpu.values())
    rotulos = [f'Tarefa {id_}' for id_ in ids] + [f'CPU {cpu} ociosa' for cpu in cpus]
    ax.set_yticks([y+.225 for y in posicoes], rotulos)
    ax.set_ylim((posicoes[-1] + 1 if posicoes else 1), -.3)
    # Folga visual interna para os marcadores nas extremidades, sem mudar ticks.
    alcance = max(1, fim)
    margem = alcance * .02
    ax.set_xlim(-margem, alcance + margem)
    ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    ax.set_axisbelow(True)
    ax.grid(axis='x', color='#e5e9ef', linewidth=.6)
    ax.set_xlabel('Tempo (ticks)')
    ax.set_title(f'Gantt | {simulacao.algoritmo} — histórico: 0 a {fim} ticks')
    ax.spines[['top', 'right']].set_visible(False)
    legenda = [Patch(facecolor='#7faacb', label='Execução: número no bloco = CPU'),
               Patch(facecolor='#151515', edgecolor='#bcbcbc', hatch='///', label='Suspensa'),
               Patch(facecolor='#d9dde2', label='CPU ociosa'),
               Patch(facecolor='white', edgecolor='#d9dde2', label='Pronta / aguardando: sem cor')]
    legenda += [Line2D([], [], marker=m, color=c, linestyle='none', markersize=5, label=n)
                for m, n, c, _ in EVENTOS.values()]
    # O layout reserva espaço abaixo do Axes, ainda dentro da Figure.
    figura.legend(handles=legenda, loc='outside lower center', ncols=2,
                  fontsize=8, frameon=False)
    return ax
