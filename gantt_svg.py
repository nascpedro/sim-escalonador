"""O mesmo desenho em Canvas Tkinter e SVG drawsvg, sem Qt/Matplotlib.

Cada destino implementa quatro operações: retângulo, linha, texto e polígono.
O desenho do Gantt chama essas operações sem conhecer a janela.
"""
import math
from pathlib import Path

import drawsvg as draw

from linha_tempo import coletar_intervalos


# Nome, cor e faixa abaixo da barra. Cada evento possui uma forma distinta.
EVENTOS = {
    'chegada': ('Chegada', '#215e99', 31),
    'ativacao': ('Ativação', '#42692e', 42),
    'conclusao': ('Conclusão', '#176d58', 53),
    'perda_prazo': ('Perda de prazo', '#a62626', 64),
    'fim_quantum': ('Fim de quantum', '#855215', 75),
    'sorteio': ('Sorteio', '#6e3f97', 86),
}


class DesenhoCanvas:
    """Adaptador das quatro operações para o Canvas público do Tkinter."""
    def __init__(self, canvas):
        self.canvas = canvas

    def retangulo(self, x, y, largura, altura, cor, hachura=False):
        self.canvas.create_rectangle(x, y, x+largura, y+altura,
            fill=cor, outline='#526171', stipple='gray50' if hachura else '')

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

    def retangulo(self, x, y, largura, altura, cor, hachura=False):
        self.imagem.append(draw.Rectangle(x, y, largura, altura,
            fill=self.hachura if hachura else cor, stroke='#526171', stroke_width=.5))

    def linha(self, x1, y1, x2, y2, cor):
        self.imagem.append(draw.Line(x1, y1, x2, y2, stroke=cor, stroke_width=1))

    def texto(self, x, y, texto, cor='#243446', centro=False):
        self.imagem.append(draw.Text(str(texto), 13, x, y, fill=cor,
            text_anchor='middle' if centro else 'start', dominant_baseline='central',
            font_family='Segoe UI, sans-serif'))

    def poligono(self, pontos, cor):
        self.imagem.append(draw.Lines(*[v for ponto in pontos for v in ponto], close=True, fill=cor))


def preparar_gantt(simulacao):
    """Lê somente o prefixo selecionado e reutiliza a coleta da versão Qt."""
    estados = simulacao.historico[:simulacao.instante_atual + 1]
    fim = estados[-1].tick
    ids = sorted({t.id for s in estados for t in s.tarefas},
                 key=lambda id_: (isinstance(id_, str), id_), reverse=True)
    cpus = list(dict.fromkeys(c.id_cpu for s in estados for c in s.cpus))
    eventos = [e for s in estados[1:] for e in s.eventos
               if e['tipo'] in EVENTOS and 0 <= e['tick'] <= fim]
    return fim, ids, cpus, eventos, coletar_intervalos(estados, eventos, fim)


def tamanho_gantt(dados, escala=24):
    fim, ids, cpus, _, _ = dados
    margem = max(140, max((len(str(id_)) * 9 + 75 for id_ in ids), default=140))
    largura = max(900, margem + max(1, fim) * escala + 30)
    altura = 80 + len(ids) * 105 + len(cpus) * 36 + 150
    return largura, altura, margem


def marcador(destino, tipo, x, y, cor):
    """Formas pequenas com centro no tick real, compartilhadas pelos dois destinos."""
    if tipo == 'chegada':
        pontos = [(x-4, y-4), (x+4, y-4), (x, y+4)]
    elif tipo == 'ativacao':
        pontos = [(x-4, y+4), (x+4, y+4), (x, y-4)]
    elif tipo == 'sorteio':
        pontos = [(x, y-4), (x+4, y), (x, y+4), (x-4, y)]
    elif tipo == 'perda_prazo':
        destino.linha(x-4, y-4, x+4, y+4, cor)
        destino.linha(x-4, y+4, x+4, y-4, cor)
        return
    elif tipo == 'conclusao':
        pontos = [(x + 4*math.cos(i*math.pi/4), y + 4*math.sin(i*math.pi/4)) for i in range(8)]
    else:
        pontos = [(x-4, y-4), (x+4, y-4), (x+4, y+4), (x-4, y+4)]
    destino.poligono(pontos, cor)


def desenhar_gantt(dados, destino, algoritmo, escala=24):
    """Ticks viram X; tarefas viram linhas; ambos os destinos recebem o mesmo desenho."""
    fim, ids, cpus, eventos, grupos = dados
    largura, altura, margem = tamanho_gantt(dados, escala)
    linhas = {id_: 70 + i * 105 for i, id_ in enumerate(ids)}
    linhas_cpu = {cpu: 70 + len(ids)*105 + i*36 for i, cpu in enumerate(cpus)}
    destino.texto(15, 20, f'Gantt · {algoritmo} · 0 a {fim} ticks')
    # Marcas legíveis, sem criar um texto por tick em simulações extensas.
    minimo = max(1, 65 / escala, max(1, fim) / 200)
    potencia = 10 ** math.floor(math.log10(minimo))
    passo = next(m * potencia for m in (1, 2, 5, 10) if m * potencia >= minimo)
    eixo_x = altura - 150
    destino.linha(margem, eixo_x, margem + max(1, fim)*escala, eixo_x, '#526171')
    for tick in range(0, fim + 1, int(passo)):
        x = margem + tick * escala
        destino.linha(x, 55, x, altura-150, '#e2e8f0')
        destino.texto(x, eixo_x+17, tick, centro=True)
    for id_, y in linhas.items():
        destino.texto(12, y+10, f'Tarefa {id_}')
    for cpu, y in linhas_cpu.items():
        destino.texto(12, y+10, f'CPU {cpu} ociosa')
    for (tipo, id_, cpu, cor), trechos in grupos.items():
        y = linhas_cpu[cpu] if tipo == 'cpu_desligada' else linhas[id_]
        for a, b in trechos:
            x, comprimento = margem + a*escala, (b-a)*escala
            destino.retangulo(x, y, comprimento, 22, cor, tipo == 'suspensa')
            if tipo == 'execucao' and comprimento >= 18:
                destino.texto(x+comprimento/2, y+11, cpu, cor='#000000', centro=True)
    for evento in eventos:
        tipo = evento['tipo']
        _, cor, deslocamento = EVENTOS[tipo]
        escolhidas = evento.get('selecionadas', []) if tipo == 'sorteio' else [evento['id_tarefa']]
        for id_ in escolhidas:
            marcador(destino, tipo, margem+evento['tick']*escala, linhas[id_]+deslocamento, cor)
    # Legenda compacta, com as mesmas formas e cores usadas nos eventos.
    base = altura-105
    destino.retangulo(15, base-9, 24, 18, '#7faacb')
    destino.texto(48, base, 'Execução: número no bloco = CPU')
    destino.retangulo(390, base-9, 24, 18, '#151515', True)
    destino.texto(423, base, 'Suspensa · pronta/aguardando: sem cor')
    for i, (tipo, (nome, cor, _)) in enumerate(EVENTOS.items()):
        x, y = 22 + (i % 3)*280, base+35+(i//3)*28
        marcador(destino, tipo, x, y, cor)
        destino.texto(x+14, y, nome)
    return largura, altura


def exportar_svg(simulacao, caminho):
    dados = preparar_gantt(simulacao)
    largura, altura, _ = tamanho_gantt(dados)
    destino = DesenhoSVG(largura, altura)
    desenhar_gantt(dados, destino, simulacao.algoritmo)
    caminho = Path(caminho)
    destino.imagem.save_svg(str(caminho))
    return caminho


def main():
    import argparse
    import sys
    from engine import Simulacao
    from parser import carregar_configuracao
    argumentos = argparse.ArgumentParser(description='Gantt SVG do experimento CustomTkinter/drawsvg')
    argumentos.add_argument('configuracao')
    argumentos.add_argument('saida')
    args = argumentos.parse_args()
    try:
        estado, algoritmo, avisos = carregar_configuracao(args.configuracao)
        for aviso in avisos:
            print(f'Aviso: {aviso}', file=sys.stderr)
        sim = Simulacao(estado, algoritmo)
        sim.executar_completa()
        print(exportar_svg(sim, args.saida))
    except (OSError, ValueError, RuntimeError) as erro:
        print(f'Erro: {erro}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
