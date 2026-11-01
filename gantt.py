"""O mesmo desenho em Canvas Tkinter e SVG drawsvg, sem Qt/Matplotlib.

Cada destino implementa quatro operações: retângulo, linha, texto e polígono.
O desenho do Gantt chama essas operações sem conhecer a janela.
"""
import math
from pathlib import Path

import drawsvg as draw

from linha_tempo import coletar_intervalos


# Nome, cor e deslocamento a partir do topo da barra. Os eventos ficam junto
# da execução; conclusão e fim de quantum compartilham a base, pois são exclusivos.
EVENTOS = {
    'chegada': ('Chegada', '#215e99', -10),
    'ativacao': ('Ativação', '#42692e', -1),
    'conclusao': ('Conclusão', '#176d58', 29),
    'perda_prazo': ('Perda de prazo', '#a62626', 13),
    'fim_quantum': ('Fim de quantum', '#855215', 29),
    'sorteio': ('Sorteio', '#6e3f97', 6),
    'preempcao': ('Preempção', '#c026d3', 21),
    'inclusao': ('Inclusão manual', '#2563eb', 13),
    'remocao': ('Remoção manual', '#dc2626', 6),
}

ALTURA_BARRA = 20
PASSO_CPU = 30
PASSO_TAREFA = 44


class DesenhoCanvas:
    """Adaptador das quatro operações para o Canvas público do Tkinter."""
    def __init__(self, canvas):
        self.canvas = canvas

    def retangulo(self, x, y, largura, altura, cor, hachura=False):
        textura = ''
        if hachura == 'ociosa':
            textura = '@' + (Path(__file__).parent / 'assets/ociosa.xbm').as_posix()
        elif hachura:
            textura = 'gray50'
        self.canvas.create_rectangle(x, y, x+largura, y+altura,
            fill=cor, outline='#526171', stipple=textura)

    def linha(self, x1, y1, x2, y2, cor):
        self.canvas.create_line(x1, y1, x2, y2, fill=cor)

    def texto(self, x, y, texto, cor='#243446', centro=False):
        self.canvas.create_text(x, y, text=str(texto), fill=cor,
            anchor='center' if centro else 'w', font=('Segoe UI', 10))

    def poligono(self, pontos, cor):
        self.canvas.create_polygon(*[v for ponto in pontos for v in ponto], fill=cor)


class DesenhoSVG:
    """Adaptador das mesmas operações para drawsvg; não requer janela/Tcl/Tk."""
    def __init__(self, largura, altura):
        self.imagem = draw.Drawing(largura, altura)
        self.imagem.append(draw.Rectangle(0, 0, largura, altura, fill='white'))
        self.hachura = draw.Pattern(6, 6, patternUnits='userSpaceOnUse')
        self.hachura.append(draw.Rectangle(0, 0, 6, 6, fill='#151515'))
        self.hachura.append(draw.Line(0, 6, 6, 0, stroke='#bcbcbc', stroke_width=1))
        self.ociosa = draw.Pattern(8, 8, patternUnits='userSpaceOnUse')
        self.ociosa.append(draw.Rectangle(0, 0, 8, 8, fill='white'))
        self.ociosa.append(draw.Line(0, 0, 8, 8, stroke='#94a3b8', stroke_width=1))

    def retangulo(self, x, y, largura, altura, cor, hachura=False):
        if hachura == 'ociosa':
            preenchimento = self.ociosa
        elif hachura:
            preenchimento = self.hachura
        else:
            preenchimento = cor or 'none'
        self.imagem.append(draw.Rectangle(x, y, largura, altura,
            fill=preenchimento, stroke='#526171', stroke_width=.5))

    def linha(self, x1, y1, x2, y2, cor):
        self.imagem.append(draw.Line(x1, y1, x2, y2, stroke=cor, stroke_width=1))

    def texto(self, x, y, texto, cor='#243446', centro=False):
        self.imagem.append(draw.Text(str(texto), 13, x, y, fill=cor,
            text_anchor='middle' if centro else 'start', dominant_baseline='central',
            font_family='Segoe UI, sans-serif'))

    def poligono(self, pontos, cor):
        self.imagem.append(draw.Lines(*[v for ponto in pontos for v in ponto], close=True, fill=cor))


def preparar_gantt(simulacao):
    """Lê somente o prefixo selecionado, sem executar ticks nem alterar estados."""
    estados = simulacao.historico[:simulacao.instante_atual + 1]
    fim = estados[-1].tick
    ids = {t.id for s in estados for t in s.tarefas}
    ids.update(e['id_tarefa'] for s in estados for e in s.eventos
               if e['tipo'] in ('inclusao', 'remocao'))
    ids = sorted(ids,
                 key=lambda id_: (isinstance(id_, str), id_), reverse=True)
    cpus = list(dict.fromkeys(c.id_cpu for s in estados for c in s.cpus))
    eventos = [e for s in estados for e in s.eventos
               if e['tipo'] in EVENTOS and 0 <= e['tick'] <= fim]
    return fim, ids, cpus, eventos, coletar_intervalos(estados, eventos, fim)


def geometria_gantt(dados):
    """CPUs no topo; tarefas compactas, em ordem decrescente, perto do eixo X."""
    _, ids, cpus, _, _ = dados
    linhas_cpu = {cpu: 50 + i * PASSO_CPU for i, cpu in enumerate(cpus)}
    topo_tarefas = 50 + len(cpus) * PASSO_CPU + 26
    linhas = {id_: topo_tarefas + i * PASSO_TAREFA for i, id_ in enumerate(ids)}
    eixo = topo_tarefas + len(ids) * PASSO_TAREFA + 8
    return linhas_cpu, linhas, eixo


def tamanho_gantt(dados, escala=24):
    fim, ids, _, _, _ = dados
    margem = max(120, max((len(str(id_)) * 9 + 75 for id_ in ids), default=120))
    largura = max(margem + 810, margem + max(1, fim) * escala + 30)
    _, _, eixo = geometria_gantt(dados)
    return largura, eixo + 190, margem


def cor_texto(cor):
    """Escolhe texto claro em fundos escuros e escuro em fundos claros."""
    r, g, b = (int(cor.lstrip('#')[i:i+2], 16) for i in (0, 2, 4))
    return '#000000' if .299*r + .587*g + .114*b > 140 else '#ffffff'


def desenhar_rotulos(dados, destino):
    """A GUI usa outro Canvas para manter esta coluna fixa durante a rolagem."""
    linhas_cpu, linhas, _ = geometria_gantt(dados)
    destino.texto(12, 20, 'Recurso')
    for cpu, y in linhas_cpu.items():
        destino.texto(12, y+10, f'CPU {cpu}')
    for id_, y in linhas.items():
        destino.texto(12, y+10, f'Tarefa {id_}')


def marcador(destino, tipo, x, y, cor):
    """Formas pequenas com centro no tick real, compartilhadas pelos dois destinos."""
    if tipo == 'chegada':
        pontos = [(x + 4*math.cos(i*math.pi/4), y + 4*math.sin(i*math.pi/4)) for i in range(8)]
    elif tipo == 'ativacao':
        pontos = [(x-4, y+4), (x+4, y+4), (x, y-4)]
    elif tipo == 'sorteio':
        pontos = [(x, y-4), (x+4, y), (x, y+4), (x-4, y)]
    elif tipo == 'inclusao':
        destino.linha(x-4, y, x+4, y, cor)
        destino.linha(x, y-4, x, y+4, cor)
        return
    elif tipo == 'remocao':
        destino.linha(x-4, y, x+4, y, cor)
        return
    elif tipo == 'preempcao':
        destino.poligono([(x-4, y-4), (x-2, y-4), (x-2, y+4), (x-4, y+4)], cor)
        destino.poligono([(x+2, y-4), (x+4, y-4), (x+4, y+4), (x+2, y+4)], cor)
        return
    elif tipo == 'perda_prazo':
        destino.linha(x-4, y-4, x+4, y+4, cor)
        destino.linha(x-4, y+4, x+4, y-4, cor)
        return
    elif tipo == 'conclusao':
        pontos = [(x-4, y-4), (x+4, y-4), (x, y+4)]
    else:
        pontos = [(x-4, y-4), (x+4, y-4), (x+4, y+4), (x-4, y+4)]
    destino.poligono(pontos, cor)


def desenhar_gantt(dados, destino, algoritmo, escala=24):
    """O mesmo desenho para tela e SVG; rótulos de CPU não alteram sua numeração."""
    fim, ids, cpus, eventos, grupos = dados
    largura, altura, margem = tamanho_gantt(dados, escala)
    linhas_cpu, linhas, eixo_x = geometria_gantt(dados)
    destino.texto(margem, 20, f'Gantt · {algoritmo} · 0 a {fim} ticks')
    minimo = max(1, 50 / escala, max(1, fim) / 200)
    potencia = 10 ** math.floor(math.log10(minimo))
    passo = next(m * potencia for m in (1, 2, 5, 10) if m * potencia >= minimo)
    destino.linha(margem, eixo_x, margem + max(1, fim)*escala, eixo_x, '#526171')
    for tick in range(0, fim + 1, int(passo)):
        x = margem + tick * escala
        destino.linha(x, 40, x, eixo_x, '#e2e8f0')
        destino.texto(x, eixo_x+17, tick, centro=True)
    desenhar_rotulos(dados, destino)

    for (tipo, id_, cpu, cor), trechos in grupos.items():
        y = linhas_cpu[cpu] if tipo == 'cpu_desligada' else linhas[id_]
        textura = 'ociosa' if tipo == 'cpu_desligada' else tipo == 'suspensa'
        for a, b in trechos:
            x, comprimento = margem + a*escala, (b-a)*escala
            destino.retangulo(x, y, comprimento, ALTURA_BARRA,
                              '#94a3b8' if tipo == 'cpu_desligada' else cor, textura)
            if tipo == 'execucao':
                # A faixa da tarefa mostra a CPU; a faixa da CPU mostra a tarefa.
                if comprimento >= 18:
                    destino.texto(x+comprimento/2, y+10, cpu, cor=cor_texto(cor), centro=True)
                destino.retangulo(x, linhas_cpu[cpu], comprimento, ALTURA_BARRA, cor)
                rotulo = f'T{id_}'
                if comprimento >= len(rotulo)*9+8:
                    destino.texto(x+comprimento/2, linhas_cpu[cpu]+10, rotulo,
                                  cor=cor_texto(cor), centro=True)
    for evento in eventos:
        tipo = evento['tipo']
        _, cor, deslocamento = EVENTOS[tipo]
        escolhidas = evento.get('selecionadas', []) if tipo == 'sorteio' else [evento['id_tarefa']]
        for id_ in escolhidas:
            marcador(destino, tipo, margem+evento['tick']*escala, linhas[id_]+deslocamento, cor)

    base = eixo_x+48
    destino.texto(margem, base, 'Blocos: CPU mostra tarefa; tarefa mostra o número da CPU.')
    estilos = [('Execução', '#7faacb', False), ('Pronta (só contorno)', '', False),
               ('Suspensa (pontilhado)', '#151515', True), ('CPU ociosa (hachura)', '#94a3b8', 'ociosa')]
    for i, (nome, cor, textura) in enumerate(estilos):
        x, y = margem+12+(i % 3)*260, base+26+(i//3)*24
        destino.retangulo(x-12, y-8, 23, 16, cor, textura)
        destino.texto(x+21, y, nome)
    for i, (tipo, (nome, cor, _)) in enumerate(EVENTOS.items()):
        x, y = margem+12+(i % 3)*260, base+78+(i//3)*24
        marcador(destino, tipo, x, y, cor)
        destino.texto(x+21, y, nome)
    return largura, altura


def exportar_svg(simulacao, caminho):
    dados = preparar_gantt(simulacao)
    largura, altura, _ = tamanho_gantt(dados)
    destino = DesenhoSVG(largura, altura)
    desenhar_gantt(dados, destino, simulacao.algoritmo)
    caminho = Path(caminho)
    try:
        destino.imagem.save_svg(str(caminho))
    except OSError as erro:
        raise OSError(erro.errno,
            f'Não foi possível exportar SVG para {caminho}: {erro.strerror or erro}', str(caminho)) from erro
    return caminho
