"""Atualiza as figuras e a explicação do Gantt no PDF de entrega existente."""
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape
from PIL import Image
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.utils import ImageReader
from reportlab.platypus import Paragraph, Table, TableStyle

RAIZ=Path.cwd()
PASTA=RAIZ/'build/gantt-compacto'
PDF=RAIZ/'output/pdf/Projeto-A-Telas-e-Origem-dos-Dados.pdf'
pdfmetrics.registerFont(TTFont('Segoe','C:/Windows/Fonts/segoeui.ttf'))
pdfmetrics.registerFont(TTFont('SegoeB','C:/Windows/Fonts/segoeuib.ttf'))
pdfmetrics.registerFontFamily('Segoe',normal='Segoe',bold='SegoeB')
W,H=841.8898,595.2756
M=36; L=W-2*M
AZUL=colors.HexColor('#12618B')
COR=colors.HexColor('#243446')
estilo=ParagraphStyle('texto',fontName='Segoe',fontSize=10.3,leading=14,textColor=COR)
celula=ParagraphStyle('celula',fontName='Segoe',fontSize=9.3,leading=12.2,textColor=COR)


def texto(c,s,x,y,w):
    p=Paragraph(s,estilo); _,h=p.wrap(w,H)
    assert y-h>36
    p.drawOn(c,x,y-h)
    return y-h


def tabela(c,linhas,y):
    dados=[[Paragraph('<b>'+a+'</b>',celula),Paragraph(escape(b),celula)] for a,b in linhas]
    t=Table(dados,colWidths=[174,L-174])
    t.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'),
        ('ROWBACKGROUNDS',(0,0),(-1,-1),[colors.HexColor('#EDF5FA'),colors.white]),
        ('LEFTPADDING',(0,0),(-1,-1),9),('RIGHTPADDING',(0,0),(-1,-1),9),
        ('TOPPADDING',(0,0),(-1,-1),8),('BOTTOMPADDING',(0,0),(-1,-1),8)]))
    _,h=t.wrap(L,H); assert y-h>38,(y,h)
    t.drawOn(c,M,y-h)
    return y-h


def nova_pagina(titulo,subtitulo,numero):
    b=BytesIO(); c=canvas.Canvas(b,pagesize=(W,H))
    c.setFillColor(AZUL); c.rect(0,H-10,W,10,fill=1,stroke=0)
    c.setFont('SegoeB',20); c.drawString(M,H-45,titulo)
    c.setFont('Segoe',8.5); c.setFillColor(colors.HexColor('#526171'))
    c.drawString(M,H-65,subtitulo)
    c.setStrokeColor(colors.HexColor('#D7E0E7')); c.line(M,29,W-M,29)
    c.setFont('Segoe',8); c.drawRightString(W-M,17,f'{numero:02d} / 14')
    return b,c,H-91


def imagem(c,corte,y):
    im=Image.open(PASTA/'principal.png').crop(corte)
    h=im.height*L/im.width
    c.drawImage(ImageReader(im),M,y-h,L,h)
    return y-h


r=PdfReader(PDF)
w=PdfWriter(); w.clone_document_from_reader(r)
figuras={0:('principal',None),1:('inicial',None),2:('principal',(8,30,1145,183)),12:('final',None)}
for indice,(nome,corte) in figuras.items():
    im=Image.open(PASTA/(nome+'.png'))
    if corte: im=im.crop(corte)
    w.pages[indice].images[0].replace(im,quality=100)

b,c,y=nova_pagina('03. Gráfico de Gantt','CPUs no topo; tarefas compactas, em ordem decrescente de ID',4)
y=imagem(c,(12,183,1141,432),y)-14
y=texto(c,'As duas visões compartilham o mesmo eixo X. A execução de cada recurso é obtida dos mesmos eventos históricos; '
    'os blocos das CPUs e das tarefas representam o mesmo trabalho.',M,y,L)-12
tabela(c,[
    ('Faixas de CPU','No topo, cada CPU mostra a tarefa executada. As áreas com hachura clara indicam que não havia tarefa alocada; CPU 0 e CPU 1 mantêm a numeração do motor.'),
    ('Faixas de tarefas','As tarefas aparecem em ordem decrescente de ID, com linhas de 44 pixels. O número dentro do bloco é a CPU. O texto usa branco ou preto conforme o fundo.'),
    ('Pronta e suspensa','Pronta usa retângulo apenas com contorno; suspensão usa pontilhado escuro. Aguardando ativação permanece sem bloco. Os eventos ficam junto à barra.'),
    ('Tempo, zoom e rolagem','O eixo X mostra ticks e os blocos usam intervalos [a,b). Zoom só altera coordenadas horizontais. Os rótulos estão em outro Canvas: fixos na horizontal e sincronizados na vertical.'),
    ('Origem','preparar_gantt lê o prefixo selecionado; coletar_intervalos agrupa execução, prontas, suspensão e ociosidade. desenhar_gantt usa os mesmos dados no Canvas e no SVG.'),
],y)
c.save(); nova=PdfReader(b).pages[0]; w.remove_page(3); w.insert_page(nova,3)

b,c,y=nova_pagina('04. Legenda e eventos do Gantt','Símbolos compactos, com o mesmo significado na tela e no SVG',5)
y=imagem(c,(112,431,1135,556),y)-12
tabela(c,[
    ('Execução / número','A cor vem do TCB no histórico. Na tarefa, o número identifica a CPU; na CPU, o rótulo identifica a tarefa. Em trechos muito estreitos, aproxime o zoom.'),
    ('Contorno / pontilhado / hachura','Só contorno indica pronta; pontilhado escuro indica suspensão; hachura clara indica CPU ociosa. Espera pela próxima ativação não recebe bloco.'),
    ('Chegada / ativação','Polígono circular azul: chegada no ingresso. Triângulo verde para cima: ativação periódica. Fontes: eventos chegada e ativacao em _ativar_tarefas.'),
    ('Triângulo verde / X vermelho','Triângulo para baixo: conclusão; X vermelho: perda de prazo. Fontes: _concluir_ocorrencia e _verificar_prazos. A ocorrência atrasada continua executando.'),
    ('Quadrado / losango','Quadrado marrom: fim de quantum. Losango roxo: tarefa selecionada por sorteio. O fim de quantum não implica interrupção automática.'),
    ('Duas barras magenta','Preempção: uma tarefa que executava deixa de ser selecionada e perde a CPU. Evento preempcao em _despachar. Migração e conclusão não geram esse marcador.'),
    ('Sinal + / traço','Inclusão manual / remoção manual. O instante é registrado pelo motor; os blocos passados da tarefa removida continuam visíveis.'),
],y)
c.save(); nova=PdfReader(b).pages[0]; w.remove_page(4); w.insert_page(nova,4)

# Atualiza o rodapé sem mexer nas explicações das telas que permaneceram iguais.
for pagina in w.pages:
    b=BytesIO(); c=canvas.Canvas(b,pagesize=(W,H))
    c.setFillColor(colors.white); c.rect(M,12,620,14,fill=1,stroke=0)
    c.setFont('Segoe',8); c.setFillColor(colors.HexColor('#526171'))
    c.drawString(M,17,'Projeto A | Documentação das telas | Gantt compacto (branch entrega)')
    c.save(); pagina.merge_page(PdfReader(b).pages[0])

w.add_metadata({'/Title':'Projeto A - Telas e origem das informações (Gantt compacto)'})
saida=PASTA/'Telas-atualizadas.pdf'
with saida.open('wb') as f: w.write(f)
assert len(PdfReader(saida).pages)==14
PDF.write_bytes(saida.read_bytes())
Image.open(PASTA/'principal.png').crop((12,183,1141,556)).save(PASTA/'previa.png')
print(PDF)
