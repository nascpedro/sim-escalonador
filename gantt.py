"""Um único desenho Matplotlib para a tela e para a exportação vetorial.

Não importa Qt/pyplot, não escolhe backend e nunca executa a simulação.
"""
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from matplotlib.ticker import MaxNLocator

from models import EstadoTarefa

# Marcador, nome, cor e pista vertical dentro da linha da tarefa.
EVENTOS = {
    'chegada': ('v', 'Chegada', '#215e99', .85),
    'ativacao': ('^', 'Ativação', '#42692e', 1.1),
    'conclusao': ('o', 'Conclusão', '#176d58', 1.35),
    'perda_prazo': ('X', 'Perda de prazo', '#a62626', 1.6),
    'fim_quantum': ('s', 'Fim de quantum', '#855215', 1.85),
    'sorteio': ('D', 'Sorteio', '#6e3f97', 0),
}


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
    ax = figura.add_subplot(111)
    figura.subplots_adjust(left=.15, right=.77, bottom=.14, top=.88)
    linhas = {id_: i * 2.3 for i, id_ in enumerate(ids)}
    eventos = [e for s in estados[1:] for e in s.eventos
               if e['tipo'] in EVENTOS and 0 <= e['tick'] <= fim]
    sorteios_por_tick = {}
    for evento in eventos:
        if evento['tipo'] == 'sorteio':
            tick = evento['tick']
            sorteios_por_tick[tick] = sorteios_por_tick.get(tick, 0) + 1
    base_sorteio = len(ids) * 2.3
    pistas_sorteio = max(sorteios_por_tick.values(), default=1)
    base = base_sorteio + pistas_sorteio * .4 + .6
    linhas_cpu = {cpu: base + i * .7 for i, cpu in enumerate(cpus)}
    intervalos = []
    for anterior, posterior in zip(estados, estados[1:]):
        cores = {t.id: '#' + t.cor.lstrip('#') for t in anterior.tarefas}
        for tarefa in anterior.tarefas:
            if tarefa.estado_tarefa == EstadoTarefa.SUSPENSA:
                intervalos.append(('suspensa', tarefa.id, None, '#151515',
                                   anterior.tick, posterior.tick))
        for evento in posterior.eventos:
            tipo, tick = evento['tipo'], evento['tick']
            if tipo == 'execucao' and 0 <= tick < fim:
                id_ = evento['id_tarefa']
                intervalos.append((tipo, id_, evento['id_cpu'], cores[id_], tick, tick + 1))
            elif tipo == 'cpu_desligada' and 0 <= tick < fim:
                intervalos.append((tipo, None, evento['id_cpu'], '#d9dde2', tick, tick + 1))

    # Une só vizinhos da mesma tarefa/CPU/cor, sem atravessar eventos.
    # Ativação e conclusão também separam ocorrências com a mesma cor.
    fronteiras = set()
    for evento in eventos:
        envolvidos = evento.get('ordem', []) if evento['tipo'] == 'sorteio' else [evento['id_tarefa']]
        fronteiras.update((id_, evento['tick']) for id_ in envolvidos)
    grupos = {}
    for tipo, id_, cpu, cor, a, b in intervalos:
        trechos = grupos.setdefault((tipo, id_, cpu, cor), [])
        if trechos and trechos[-1][1] == a and (id_, a) not in fronteiras:
            trechos[-1][1] = b
        else:
            trechos.append([a, b])
    intervalos = [(tipo, id_, cpu, cor, a, b)
                  for (tipo, id_, cpu, cor), trechos in grupos.items() for a, b in trechos]
    for indice, (tipo, id_, cpu, cor, a, b) in enumerate(intervalos):
        y = linhas_cpu[cpu] if tipo == 'cpu_desligada' else linhas[id_]
        suspensa = tipo == 'suspensa'
        bloco = ax.broken_barh([(a, b-a)], (y, .45), facecolors=cor,
                               edgecolors='#bcbcbc' if suspensa else '#526171',
                               linewidth=.5, hatch='///' if suspensa else None,
                               label=f'{tipo}: tarefa {id_}, CPU {cpu}, [{a}, {b})')
        bloco.set_gid(f'{tipo}-{indice}')
        if tipo == 'execucao':
            # Mantém a fonte legível ao usar zoom. O recorte evita que o
            # número invada o vizinho quando o gráfico inteiro está reduzido.
            texto = ax.text((a+b)/2, y+.225, str(cpu), ha='center', va='center',
                            fontsize=7, color='black', clip_on=True,
                            bbox=dict(facecolor='white', edgecolor='none', pad=.2))
            texto.set_clip_path(bloco.get_paths()[0], ax.transData)
            texto.get_bbox_patch().set_clip_path(bloco.get_paths()[0], ax.transData)

    usados = {}
    for indice, evento in enumerate(eventos):
        tipo, tick = evento['tipo'], evento['tick']
        marcador, nome, cor, deslocamento = EVENTOS[tipo]
        if tipo == 'sorteio':
            pista = usados.get(tick, 0)
            usados[tick] = pista + 1
            y = base_sorteio + pista * .4
        else:
            y = linhas[evento['id_tarefa']] + deslocamento
        artista = ax.scatter([tick], [y], marker=marcador, s=20, color=cor,
                             zorder=4, clip_on=False, label=f'{nome}: {evento}')
        artista.set_gid(f'evento-{tipo}-{tick}-{indice}')

    posicoes = list(linhas.values()) + list(linhas_cpu.values())
    rotulos = [f'Tarefa {id_}' for id_ in ids] + [f'CPU {cpu} ociosa' for cpu in cpus]
    posicoes.insert(len(ids), base_sorteio - .225)
    rotulos.insert(len(ids), 'Sorteios')
    ax.set_yticks([y+.225 for y in posicoes], rotulos)
    ax.set_ylim((posicoes[-1] + 1 if posicoes else 1), -.3)
    ax.set_xlim(0, max(1, fim))
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
    ax.legend(handles=legenda, loc='upper left', bbox_to_anchor=(1.02, 1),
              borderaxespad=0, fontsize=8, frameon=False)
    return ax
