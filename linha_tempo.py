"""Intervalos do histórico, sem dependência de biblioteca gráfica."""
from models import EstadoTarefa


def coletar_intervalos(estados, eventos, fim):
    """Converte eventos em trechos e une vizinhos sem atravessar eventos da tarefa."""
    fronteiras = set()
    for evento in eventos:
        ids = evento.get('ordem', []) if evento['tipo'] == 'sorteio' else [evento['id_tarefa']]
        fronteiras.update((id_, evento['tick']) for id_ in ids)
    grupos = {}
    for anterior, posterior in zip(estados, estados[1:]):
        cores = {t.id: '#' + t.cor.lstrip('#') for t in anterior.tarefas}
        executadas = {e['id_tarefa'] for e in posterior.eventos if e['tipo'] == 'execucao'}
        ativadas = {e['id_tarefa'] for e in posterior.eventos
                    if e['tipo'] == 'ativacao' and e['tick'] == anterior.tick}
        trechos = []
        for tarefa in anterior.tarefas:
            if tarefa.estado_tarefa == EstadoTarefa.SUSPENSA:
                trechos.append(('suspensa', tarefa.id, None, '#151515', anterior.tick, posterior.tick))
            elif tarefa.id not in executadas and (
                    tarefa.estado_tarefa in (EstadoTarefa.PRONTA, EstadoTarefa.EXECUTANDO)
                    or tarefa.estado_tarefa == EstadoTarefa.AGUARDANDO and tarefa.id in ativadas):
                # A chegada pode ocorrer neste próprio intervalo. Usar só o
                # estado anterior esconderia a primeira espera por uma CPU.
                trechos.append(('pronta', tarefa.id, None, '', anterior.tick, posterior.tick))
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
