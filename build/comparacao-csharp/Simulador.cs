// =====================================================================================
// Simulador.cs
// Motor da simulação. Não conhece nenhuma tela: apenas recebe comandos (Step, StepBack,
// RunAll, modificações...) e mantém o estado, o histórico e os registros para o Gantt.
//
// MODELO DE TEMPO: o relógio global conta ticks. O estado "no tempo t" descreve o sistema
// ANTES de executar o intervalo [t, t+1). Step() faz, nesta ordem:
//   1. liberações (ativações periódicas que acontecem em t);
//   2. verificação de perda de prazo em t;
//   3. fim de quantum;
//   4. escalonamento (escolhe quem usa cada CPU; CPU sem tarefa fica DESLIGADA);
//   5. execução de 1 tick e avanço do relógio para t+1;
//   6. término de jobs (o evento de término ocorre exatamente em t+1).
//
// HISTÓRICO: History[t] é uma cópia do estado no tempo t. Retroceder = restaurar uma cópia.
// Avançar depois de retroceder reaproveita as cópias. Se o usuário MODIFICAR algo num
// estado passado, o "futuro" é descartado (ele deixaria de ser válido) e a simulação
// continua a partir dali.
// =====================================================================================
using System;
using System.Collections.Generic;
using System.Drawing;
using System.Text;

namespace SimuladorEscalonamento
{
    public class Simulator
    {
        public List<SimState> History = new List<SimState>(); // History[t] = estado no tempo t
        public List<TickRecord> Ticks = new List<TickRecord>(); // Ticks[t] = o que ocorreu em [t,t+1)
        public List<GEvent> Events = new List<GEvent>();        // todos os eventos, em ordem de ocorrência
        public SimState Cur;                                    // estado atual
        private SimState initial;                               // estado logo após carregar a configuração

        // Limite de segurança para a execução completa (cada tick guarda uma cópia do estado
        // na memória, então precisamos de um teto para não esgotar a RAM).
        public const int SafetyLimit = 500000;

        // ------------------------------------------------------------------ carga / reinício
        public void Load(SimState s)
        {
            initial = s.Clone();
            Reset();
        }

        /// <summary>Volta ao estado original carregado (descarta histórico e modificações).</summary>
        public void Reset()
        {
            Cur = initial.Clone();
            Cur.EventCount = 0;
            History.Clear();
            Ticks.Clear();
            Events.Clear();
            History.Add(Cur.Clone());
        }

        // ------------------------------------------------------------------ consultas
        public bool IsDone
        {
            get
            {
                foreach (Tcb k in Cur.Tasks) if (k.State != TaskState.Terminada) return false;
                return true;
            }
        }

        /// <summary>Bloqueada: restam tarefas, mas todas estão suspensas (nada pode progredir).</summary>
        public bool IsBlocked
        {
            get
            {
                if (IsDone) return false;
                foreach (Tcb k in Cur.Tasks)
                    if (k.State != TaskState.Terminada && k.State != TaskState.Suspensa) return false;
                return true;
            }
        }

        public bool CanStep { get { return !IsDone && !IsBlocked; } }
        public bool CanStepOrRedo { get { return Cur.Time + 1 < History.Count || CanStep; } }
        public bool HasFuture { get { return History.Count > Cur.Time + 1; } }

        public Tcb Find(int id)
        {
            foreach (Tcb k in Cur.Tasks) if (k.Id == id) return k;
            return null;
        }

        private void AddEvent(int time, int id, EventType type, int cpu, string text)
        {
            Events.Add(new GEvent(time, id, type, cpu, text));
        }

        /// <summary>Maior quantidade de CPUs já usada (pode ter mudado durante a simulação).</summary>
        public int MaxCpus()
        {
            int n = Cur.NumCpus;
            for (int t = 0; t < Cur.Time && t < Ticks.Count; t++)
                if (Ticks[t].CpuTask.Length > n) n = Ticks[t].CpuTask.Length;
            return n;
        }

        // ------------------------------------------------------------------ navegação
        public bool StepBack()
        {
            if (Cur.Time == 0) return false;
            Cur = History[Cur.Time - 1].Clone();
            return true;
        }

        /// <summary>Vai para o instante pedido (retrocedendo ou avançando).</summary>
        public void GoTo(int t)
        {
            if (t < 0) t = 0;
            while (Cur.Time > t) StepBack();
            while (Cur.Time < t) { if (!Step()) break; }
        }

        /// <summary>Execução completa. Retorna false se parou pelo limite de segurança.</summary>
        public bool RunAll()
        {
            while (CanStepOrRedo)
            {
                if (Cur.Time >= SafetyLimit) return false;
                Step();
            }
            return true;
        }

        // ------------------------------------------------------------------ o passo da simulação
        /// <summary>Avança um tick. Retorna false se não é possível (terminou ou bloqueada).</summary>
        public bool Step()
        {
            // Se já existe futuro no histórico (retrocedemos antes), apenas reutiliza.
            if (Cur.Time + 1 < History.Count)
            {
                Cur = History[Cur.Time + 1].Clone();
                return true;
            }
            if (!CanStep) return false;

            SimState s = Cur;
            int t = s.Time;

            // (1) Liberações periódicas
            foreach (Tcb k in s.Tasks)
            {
                if (k.State == TaskState.Terminada) continue;
                if (k.Activations < Const.MaxJobs && t >= k.NextRelease)
                {
                    k.Activations++;
                    k.NextRelease = (k.Activations < Const.MaxJobs) ? k.NextRelease + k.Periodo : int.MaxValue;
                    AddEvent(t, k.Id, EventType.Arrival, -1,
                        k.Label + " ativada (execução " + k.Activations + " de " + Const.MaxJobs + ").");
                    if (!k.JobActive) StartJob(k, t, t);
                    else k.Pending.Add(t); // job anterior ainda não terminou: fica na fila de ativações pendentes
                }
            }

            // (2) Perda de prazo (a tarefa continua executando até terminar, conforme o enunciado)
            foreach (Tcb k in s.Tasks)
            {
                if (k.State == TaskState.Terminada) continue;
                foreach (int rel in k.Pending)
                {
                    if (rel + k.Prazo == t) // ativação pendente que estourou o prazo antes mesmo de começar
                    {
                        k.DeadlineMisses++;
                        AddEvent(t, k.Id, EventType.DeadlineMiss, -1, k.Label + " PERDEU O PRAZO (ativação do instante " + rel + ", ainda pendente).");
                    }
                }
                if (k.JobActive && !k.MissReported && t >= k.AbsDeadline)
                {
                    k.MissReported = true;
                    k.DeadlineMisses++;
                    AddEvent(t, k.Id, EventType.DeadlineMiss, k.Cpu,
                        k.Label + " PERDEU O PRAZO (prazo absoluto " + k.AbsDeadline + "; faltam " + k.Remaining + " ticks).");
                }
            }

            // (3) Fim de quantum: força nova decisão do escalonador. Se a tarefa continuar
            //     sendo a melhor, ela segue na mesma CPU (desempate 1), evitando troca inútil.
            foreach (Tcb k in s.Tasks)
            {
                if (k.State == TaskState.Executando && k.RunSlice >= s.Quantum)
                {
                    AddEvent(t, k.Id, EventType.QuantumEnd, k.Cpu, k.Label + ": quantum de " + s.Quantum + " ticks esgotado na CPU " + (k.Cpu + 1) + ".");
                    k.RunSlice = 0;
                }
            }

            // (4) Escalonamento. A fila de prontos é GLOBAL: todas as tarefas com job ativo e não suspensas.
            List<Tcb> ready = new List<Tcb>();
            foreach (Tcb k in s.Tasks)
                if (k.JobActive && k.State != TaskState.Suspensa && k.State != TaskState.Terminada) ready.Add(k);

            HashSet<int> wasRunning = new HashSet<int>();
            foreach (Tcb k in s.Tasks) if (k.State == TaskState.Executando) wasRunning.Add(k.Id);

            SelectResult sel = Scheduler.Select(ready, s.Algorithm, s.NumCpus, t, ref s.Rng);

            // Atribui CPUs: quem já executava mantém a CPU (evita migração); os demais pegam a primeira CPU livre.
            int[] newCpu = SimState.NewCpuArray(s.NumCpus);
            List<Tcb> toPlace = new List<Tcb>();
            foreach (Tcb k in sel.Chosen)
            {
                if (wasRunning.Contains(k.Id) && k.Cpu >= 0 && k.Cpu < s.NumCpus && newCpu[k.Cpu] < 0) newCpu[k.Cpu] = k.Id;
                else toPlace.Add(k);
            }
            foreach (Tcb k in toPlace)
            {
                int c = 0;
                while (newCpu[c] >= 0) c++;
                newCpu[c] = k.Id;
                k.Cpu = c;
            }
            foreach (Tcb k in ready)
            {
                if (sel.Chosen.Contains(k))
                {
                    if (!wasRunning.Contains(k.Id) && sel.Drawn.Contains(k.Id))
                        AddEvent(t, k.Id, EventType.Draw, k.Cpu, k.Label + " escolhida por SORTEIO (empate total) para a CPU " + (k.Cpu + 1) + ".");
                    k.State = TaskState.Executando;
                }
                else
                {
                    if (wasRunning.Contains(k.Id))
                        AddEvent(t, k.Id, EventType.Preempt, k.Cpu, k.Label + " PREEMPTADA (perdeu a CPU " + (k.Cpu + 1) + ").");
                    k.State = TaskState.Pronta;
                    k.Cpu = -1;
                }
            }

            // (5) Registro do tick (alimenta o Gantt) e execução de 1 tick
            TickRecord tr = new TickRecord();
            tr.Time = t;
            tr.CpuTask = (int[])newCpu.Clone();
            foreach (Tcb k in s.Tasks)
            {
                byte code = 0;
                if (k.State == TaskState.Executando) code = 2;
                else if (k.State == TaskState.Suspensa) code = 3;
                else if (k.JobActive && k.State == TaskState.Pronta) code = 1;
                tr.Codes[k.Id] = code;
            }
            Ticks.Add(tr);

            foreach (Tcb k in s.Tasks)
            {
                if (k.State == TaskState.Executando) { k.Remaining--; k.TotalExec++; k.RunSlice++; }
                else
                {
                    k.RunSlice = 0;
                    if (k.State == TaskState.Pronta) k.TotalWait++;
                }
            }
            s.Time = t + 1;

            // (6) Término de jobs (instante exato t+1)
            foreach (Tcb k in s.Tasks)
                if (k.State == TaskState.Executando && k.Remaining <= 0) CompleteJob(s, k, s.Time);

            RebuildCpu(s);
            s.EventCount = Events.Count;
            History.Add(s.Clone());
            return true;
        }

        /// <summary>Inicia um job (uma execução) da tarefa.</summary>
        private void StartJob(Tcb k, int release, int now)
        {
            k.JobActive = true;
            k.JobRelease = release;
            k.AbsDeadline = release + k.Prazo;
            k.Remaining = k.Duracao;
            k.MissReported = now > k.AbsDeadline; // se já passou, a perda já foi registrada como "pendente"
            if (k.State != TaskState.Suspensa) k.State = TaskState.Pronta;
        }

        /// <summary>Encerra o job atual; decide se a tarefa termina, começa outro job ou espera o próximo período.</summary>
        private void CompleteJob(SimState s, Tcb k, int time)
        {
            k.JobsCompleted++;
            AddEvent(time, k.Id, EventType.Finish, k.Cpu,
                k.Label + " terminou a execução " + k.JobsCompleted + " de " + Const.MaxJobs + ".");
            k.JobActive = false;
            k.Remaining = 0;
            k.Cpu = -1;
            k.RunSlice = 0;
            if (k.JobsCompleted >= Const.MaxJobs)
            {
                k.State = TaskState.Terminada;
                k.Pending.Clear();
            }
            else if (k.Pending.Count > 0)
            {
                int rel = k.Pending[0];
                k.Pending.RemoveAt(0);
                StartJob(k, rel, time);
            }
            else if (k.State != TaskState.Suspensa) k.State = TaskState.Aguardando;
        }

        private void RebuildCpu(SimState s)
        {
            s.Cpu = SimState.NewCpuArray(s.NumCpus);
            foreach (Tcb k in s.Tasks)
                if (k.State == TaskState.Executando && k.Cpu >= 0 && k.Cpu < s.NumCpus) s.Cpu[k.Cpu] = k.Id;
        }

        // =================================================================================
        // MODIFICAÇÕES MANUAIS (req. 3.1 e 3.4)
        // Todas validam ANTES de alterar e devolvem null se deu certo, ou uma mensagem
        // explicando por que a modificação não pôde ser feita.
        // =================================================================================

        /// <summary>Descarta o futuro do histórico (ele deixa de ser válido após uma alteração).</summary>
        private void BeginModify()
        {
            if (History.Count > Cur.Time + 1) History.RemoveRange(Cur.Time + 1, History.Count - Cur.Time - 1);
            if (Ticks.Count > Cur.Time) Ticks.RemoveRange(Cur.Time, Ticks.Count - Cur.Time);
            if (Events.Count > Cur.EventCount) Events.RemoveRange(Cur.EventCount, Events.Count - Cur.EventCount);
        }

        private void EndModify(string msg, int taskId)
        {
            AddEvent(Cur.Time, taskId, EventType.Info, -1, "[MODIFICAÇÃO MANUAL] " + msg);
            RebuildCpu(Cur);
            Cur.EventCount = Events.Count;
            History[Cur.Time] = Cur.Clone(); // o estado "atual" no histórico passa a ser o modificado
        }

        public string SetSystem(string alg, int quantum, int cpus)
        {
            if (!Scheduler.Exists(alg)) return "Algoritmo de escalonamento desconhecido.";
            if (quantum < 1) return "O quantum deve ser maior ou igual a 1 tick.";
            if (cpus < 1 || cpus > Const.MaxCpus) return "A quantidade de CPUs deve estar entre 1 e " + Const.MaxCpus + ".";
            alg = alg.ToUpperInvariant();
            if (alg == Cur.Algorithm && quantum == Cur.Quantum && cpus == Cur.NumCpus)
                return "Nenhuma alteração: os valores informados são iguais aos atuais.";

            BeginModify();
            Cur.Algorithm = alg;
            Cur.Quantum = quantum;
            if (cpus < Cur.NumCpus)
            {
                // Tarefas que estavam nas CPUs removidas voltam para a fila de prontos.
                foreach (Tcb k in Cur.Tasks)
                    if (k.State == TaskState.Executando && k.Cpu >= cpus) { k.State = TaskState.Pronta; k.Cpu = -1; k.RunSlice = 0; }
            }
            Cur.NumCpus = cpus;
            EndModify("sistema: algoritmo=" + alg + ", quantum=" + quantum + ", CPUs=" + cpus + " (vale a partir do tick " + Cur.Time + ").", -1);
            return null;
        }

        public string EditTask(int id, int ing, int dur, int per, int prz, Color cor)
        {
            Tcb k = Find(id);
            if (k == null) return "A tarefa informada não existe.";
            if (k.State == TaskState.Terminada)
                return k.Label + " já terminou todas as suas execuções; não há mais o que modificar nela.";
            if (dur < 1) return "A duração deve ser maior ou igual a 1 tick.";
            if (per < 1) return "O período deve ser maior que zero: tarefas aperiódicas (período 0) não são suportadas neste projeto, e valores negativos são inválidos.";
            if (prz < 1) return "O prazo deve ser maior ou igual a 1 tick.";
            if (ing != k.Ingresso)
            {
                if (k.Activations > 0)
                    return "O instante de ingresso não pode ser alterado: " + k.Label + " já foi ativada (a história passada não pode ser reescrita). " +
                           "Retroceda a simulação para antes do ingresso ou altere o período.";
                if (ing < Cur.Time)
                    return "O novo ingresso (" + ing + ") está no passado: o relógio já está em " + Cur.Time + ".";
            }

            BeginModify();
            StringBuilder sb = new StringBuilder(k.Label + " alterada:");
            if (ing != k.Ingresso) { k.Ingresso = ing; k.NextRelease = ing; sb.Append(" ingresso=" + ing); }
            if (dur != k.Duracao) { k.Duracao = dur; sb.Append(" duração=" + dur + " (vale para as próximas execuções; use \"tempo restante\" para a atual)"); }
            if (per != k.Periodo) { k.Periodo = per; sb.Append(" período=" + per + " (vale a partir da próxima ativação)"); }
            if (prz != k.Prazo)
            {
                k.Prazo = prz;
                sb.Append(" prazo=" + prz);
                if (k.JobActive)
                {
                    k.AbsDeadline = k.JobRelease + prz; // o job atual também passa a ter o novo prazo
                    if (k.AbsDeadline > Cur.Time) k.MissReported = false;
                }
            }
            if (cor.ToArgb() != k.Cor.ToArgb()) { k.Cor = cor; sb.Append(" cor"); }
            EndModify(sb.ToString(), id);
            return null;
        }

        public string SetRemaining(int id, int rem)
        {
            Tcb k = Find(id);
            if (k == null) return "A tarefa informada não existe.";
            if (!k.JobActive) return k.Label + " não tem uma execução em andamento (estado: " + k.StateText() + "); não há tempo restante para alterar.";
            if (rem < 1) return "O tempo restante deve ser maior ou igual a 1. Para encerrar a execução atual use \"Forçar término\".";
            BeginModify();
            k.Remaining = rem;
            EndModify(k.Label + ": tempo restante da execução atual definido como " + rem + ".", id);
            return null;
        }

        public string ForceFinish(int id)
        {
            Tcb k = Find(id);
            if (k == null) return "A tarefa informada não existe.";
            if (!k.JobActive) return k.Label + " não tem uma execução em andamento; não há o que terminar.";
            BeginModify();
            CompleteJob(Cur, k, Cur.Time);
            Events.RemoveAt(Events.Count - 1); // troca o evento automático por um Info (término forçado não é "natural")
            AddEvent(Cur.Time, id, EventType.Finish, -1, k.Label + " teve a execução atual TERMINADA manualmente.");
            EndModify(k.Label + ": execução atual encerrada manualmente.", id);
            return null;
        }

        public string Suspend(int id)
        {
            Tcb k = Find(id);
            if (k == null) return "A tarefa informada não existe.";
            if (k.State == TaskState.Terminada) return k.Label + " já terminou; não pode ser suspensa.";
            if (k.State == TaskState.Suspensa) return k.Label + " já está suspensa.";
            if (k.State == TaskState.NaoChegou) return k.Label + " ainda não chegou ao sistema (ingresso em " + k.Ingresso + "); só é possível suspender tarefas já criadas.";
            BeginModify();
            k.State = TaskState.Suspensa;
            k.Cpu = -1;
            k.RunSlice = 0;
            EndModify(k.Label + " suspensa.", id);
            return null;
        }

        public string Resume(int id)
        {
            Tcb k = Find(id);
            if (k == null) return "A tarefa informada não existe.";
            if (k.State != TaskState.Suspensa) return k.Label + " não está suspensa (estado: " + k.StateText() + ").";
            BeginModify();
            k.State = k.JobActive ? TaskState.Pronta : (k.Activations == 0 ? TaskState.NaoChegou : TaskState.Aguardando);
            EndModify(k.Label + " retomada.", id);
            return null;
        }

        public string AddTask(int id, Color cor, int ing, int dur, int per, int prz)
        {
            if (id < 0) return "O id deve ser maior ou igual a zero.";
            if (Find(id) != null) return "Já existe uma tarefa com id " + id + ": o id precisa ser único.";
            if (dur < 1) return "A duração deve ser maior ou igual a 1 tick.";
            if (per < 1) return "O período deve ser maior que zero (tarefas aperiódicas não são suportadas neste projeto).";
            if (prz < 1) return "O prazo deve ser maior ou igual a 1 tick.";
            if (ing < Cur.Time) return "O ingresso (" + ing + ") está no passado: o relógio já está em " + Cur.Time + ".";
            BeginModify();
            Tcb k = new Tcb();
            k.Id = id; k.Cor = cor; k.Ingresso = ing; k.Duracao = dur; k.Periodo = per; k.Prazo = prz; k.NextRelease = ing;
            Cur.Tasks.Add(k);
            EndModify("nova tarefa " + k.Label + " criada (ingresso=" + ing + ", duração=" + dur + ", período=" + per + ", prazo=" + prz + ").", id);
            return null;
        }

        public string RemoveTask(int id)
        {
            Tcb k = Find(id);
            if (k == null) return "A tarefa informada não existe.";
            if (Cur.Time > 0)
                return "Tarefas só podem ser removidas no tick 0: depois que a simulação começa, a tarefa já aparece no histórico e no Gantt. " +
                       "Retroceda até o tick 0 ou use \"Suspender\".";
            BeginModify();
            Cur.Tasks.Remove(k);
            EndModify("tarefa " + k.Label + " removida.", -1);
            return null;
        }

        // =================================================================================
        // RELATÓRIOS (estado atual para depuração e resultado final)
        // =================================================================================

        /// <summary>Texto com o estado do sistema no tick atual (o "debugger" do modo passo a passo).</summary>
        public string DescribeState()
        {
            SimState s = Cur;
            StringBuilder sb = new StringBuilder();
            string nl = Environment.NewLine;
            sb.Append("Relógio global: tick " + s.Time + " (a próxima execução cobre o intervalo [" + s.Time + ", " + (s.Time + 1) + "))" + nl);
            sb.Append("Algoritmo: " + s.Algorithm + "   Quantum: " + s.Quantum + "   CPUs: " + s.NumCpus + nl);
            sb.Append("Situação: " + (IsDone ? "TERMINADA" : (IsBlocked ? "BLOQUEADA (todas as tarefas restantes estão suspensas)" : "em andamento")) + nl + nl);

            sb.Append("Processadores (quem executou no último tick):" + nl);
            for (int c = 0; c < s.NumCpus; c++)
            {
                Tcb k = null;
                if (s.Cpu[c] >= 0) k = Find(s.Cpu[c]);
                string d = k != null ? k.Label + " (restam " + k.Remaining + " ticks)" : (s.Time == 0 ? "sem tarefa (simulação não iniciada)" : "DESLIGADA (sem tarefa para executar)");
                sb.Append("  CPU " + (c + 1) + ": " + d + nl);
            }

            List<Tcb> ready = new List<Tcb>();
            foreach (Tcb k in s.Tasks)
                if (k.JobActive && k.State != TaskState.Suspensa && k.State != TaskState.Terminada) ready.Add(k);
            List<Tcb> ord = Scheduler.Sort(ready, s.Algorithm, s.Time);
            sb.Append(nl + "Fila de prontos global (da mais para a menos prioritária):" + nl + "  ");
            if (ord.Count == 0) sb.Append("(vazia)");
            for (int i = 0; i < ord.Count; i++)
            {
                if (i > 0) sb.Append(", ");
                sb.Append(ord[i].Label + (ord[i].State == TaskState.Executando ? "*" : "") + "[rest " + ord[i].Remaining + ", prazo " + ord[i].AbsDeadline + "]");
            }
            sb.Append(nl + "  (* = em execução)" + nl);

            sb.Append(nl + "Tarefas por estado:" + nl);
            foreach (Tcb k in s.Tasks)
                sb.Append("  " + k.Label + ": " + k.StateText() + (k.Pending.Count > 0 ? " (+" + k.Pending.Count + " ativação(ões) pendente(s))" : "") +
                          "  próxima ativação: " + (k.NextRelease == int.MaxValue ? "-" : k.NextRelease.ToString()) + nl);
            return sb.ToString();
        }

        /// <summary>Períodos em que cada CPU ficou desligada (req. 1.2).</summary>
        public string OffReport()
        {
            StringBuilder sb = new StringBuilder();
            int n = MaxCpus();
            for (int c = 0; c < n; c++)
            {
                int total = 0, start = -1;
                List<string> parts = new List<string>();
                for (int t = 0; t <= Cur.Time; t++)
                {
                    bool off = false;
                    if (t < Cur.Time && t < Ticks.Count) off = c < Ticks[t].CpuTask.Length && Ticks[t].CpuTask[c] < 0;
                    if (off && start < 0) start = t;
                    if (!off && start >= 0) { parts.Add("[" + start + "," + t + ")"); total += t - start; start = -1; }
                }
                sb.AppendLine("  CPU " + (c + 1) + ": " + (parts.Count == 0 ? "nunca ficou desligada" :
                    "desligada em " + string.Join(", ", parts.ToArray()) + " (total: " + total + " ticks)"));
            }
            return sb.ToString();
        }

        /// <summary>Resumo final da simulação.</summary>
        public string Summary()
        {
            StringBuilder sb = new StringBuilder();
            sb.AppendLine("=== RESULTADO DA SIMULAÇÃO ===");
            sb.AppendLine("Algoritmo: " + Cur.Algorithm + " | Quantum: " + Cur.Quantum + " | CPUs: " + Cur.NumCpus + " | Tempo simulado: " + Cur.Time + " ticks");
            sb.AppendLine();
            sb.AppendLine("Tarefa | execuções concluídas | perdas de prazo | ticks executados | ticks em espera");
            List<Tcb> l = new List<Tcb>(Cur.Tasks);
            l.Sort(delegate(Tcb a, Tcb b) { return a.Id.CompareTo(b.Id); });
            foreach (Tcb k in l)
                sb.AppendLine(k.Label + "     | " + k.JobsCompleted + " | " + k.DeadlineMisses + " | " + k.TotalExec + " | " + k.TotalWait);
            sb.AppendLine();
            sb.AppendLine("Períodos em que cada processador ficou desligado:");
            sb.Append(OffReport());
            return sb.ToString();
        }
    }
}
