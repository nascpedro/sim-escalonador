// =====================================================================================
// Modelo.cs
// Estruturas de dados do simulador: TCB (Task Control Block), estado completo da
// simulação (SimState), eventos do gráfico (GEvent) e registro de cada tick (TickRecord).
//
// DECISÃO: todas as informações de uma tarefa (antes, durante e depois da simulação)
// ficam em UMA única classe (Tcb), conforme requisito 1.3.
// DECISÃO: o código usa apenas recursos de C# 5 para que possa ser compilado com o
// csc.exe que já acompanha o Windows (.NET Framework 4.x), sem instalar nada extra.
// =====================================================================================
using System;
using System.Collections.Generic;
using System.Drawing;

namespace SimuladorEscalonamento
{
    /// <summary>Constantes gerais e valores padrão (requisito 3.2).</summary>
    public static class Const
    {
        public const int MaxJobs = 10;          // tarefa periódica "termina" após 10 execuções (req. 4.4)
        public const int MaxCpus = 128;         // o "N" máximo de processadores aceito
        public const string DefaultAlg = "RM";  // algoritmo padrão
        public const int DefaultQuantum = 4;    // quantum padrão (ticks)
        public const int DefaultCpus = 1;       // quantidade padrão de CPUs
        public const int DefaultPeriod = 10;    // período padrão se o campo vier vazio no arquivo
        public const int DefaultDuration = 1;   // duração padrão se o campo vier vazio no arquivo
    }

    /// <summary>Estados possíveis de uma tarefa.</summary>
    public enum TaskState
    {
        NaoChegou,   // ainda não chegou ao sistema (antes do ingresso)
        Aguardando,  // já executou algo e espera a próxima ativação periódica
        Pronta,      // está na fila de prontos (global) sem CPU
        Executando,  // está usando uma CPU
        Suspensa,    // suspensa (manualmente pelo usuário)
        Terminada    // concluiu todas as execuções
    }

    /// <summary>Tipos de evento que aparecem no gráfico de Gantt (um símbolo para cada).</summary>
    public enum EventType { Arrival, Finish, DeadlineMiss, Draw, QuantumEnd, Preempt, Info }

    /// <summary>
    /// Task Control Block: guarda TUDO sobre uma tarefa. Usamos campos públicos de propósito:
    /// a classe é só um "registro" e isto mantém o código simples.
    /// </summary>
    public class Tcb
    {
        // ---- Parâmetros lidos do arquivo de configuração ----
        public int Id;
        public Color Cor;
        public int Ingresso;      // instante da primeira ativação
        public int Duracao;       // tempo de CPU de cada execução (job)
        public int Periodo;       // período de ativação (> 0 neste projeto)
        public int Prazo;         // deadline relativo à ativação
        public string Eventos = ""; // lista de eventos (lida e guardada; será tratada no projeto B)

        // ---- Estado dinâmico ----
        public TaskState State = TaskState.NaoChegou;
        public bool JobActive;    // existe uma execução (job) em andamento/pronta?
        public int JobRelease;    // instante de ativação do job atual
        public int AbsDeadline;   // prazo absoluto do job atual (JobRelease + Prazo)
        public int Remaining;     // ticks de CPU que faltam para o job atual
        public bool MissReported; // o job atual já teve a perda de prazo registrada?
        public int NextRelease;   // instante da próxima ativação periódica
        public int Cpu = -1;      // CPU em uso (-1 = nenhuma)
        public int RunSlice;      // ticks seguidos executando (para o quantum)
        // Ativações que chegaram enquanto o job anterior ainda não tinha terminado
        // (acontece quando prazo/duração > período). Guarda o instante de cada ativação.
        public List<int> Pending = new List<int>();

        // ---- Estatísticas ----
        public int Activations;     // quantas ativações já ocorreram
        public int JobsCompleted;   // quantos jobs já terminaram
        public int DeadlineMisses;  // quantas perdas de prazo
        public int TotalExec;       // ticks executados
        public int TotalWait;       // ticks na fila de prontos sem executar

        public string Label { get { return "T" + Id; } }

        /// <summary>Cópia profunda (necessária para o histórico de estados).</summary>
        public Tcb Clone()
        {
            Tcb c = (Tcb)MemberwiseClone();
            c.Pending = new List<int>(Pending);
            return c;
        }

        public string StateText()
        {
            switch (State)
            {
                case TaskState.NaoChegou: return "Não chegou";
                case TaskState.Aguardando: return "Aguardando ativação";
                case TaskState.Pronta: return "Pronta";
                case TaskState.Executando: return "Executando";
                case TaskState.Suspensa: return "Suspensa";
                case TaskState.Terminada: return "Terminada";
            }
            return "";
        }
    }

    /// <summary>Evento a ser desenhado no Gantt (e listado no log).</summary>
    public class GEvent
    {
        public int Time;
        public int TaskId;      // -1 = evento geral (não desenhado em linha de tarefa)
        public EventType Type;
        public int Cpu;
        public string Text;
        public GEvent(int time, int taskId, EventType type, int cpu, string text)
        {
            Time = time; TaskId = taskId; Type = type; Cpu = cpu; Text = text;
        }
    }

    /// <summary>
    /// O que aconteceu no intervalo [Time, Time+1). É a base do Gantt.
    /// Codes: 0 = nada, 1 = pronta (sem cor), 2 = executando, 3 = suspensa.
    /// </summary>
    public class TickRecord
    {
        public int Time;
        public int[] CpuTask;  // id da tarefa em cada CPU; -1 = CPU desligada
        public Dictionary<int, byte> Codes = new Dictionary<int, byte>();
    }

    /// <summary>
    /// Estado completo do sistema simulado em um instante. Uma cópia é guardada a cada
    /// tick: é o "histórico" que permite retroceder/avançar (requisito 1.5.2).
    /// </summary>
    public class SimState
    {
        public int Time;                  // relógio global (em ticks)
        public List<Tcb> Tasks = new List<Tcb>();
        public int[] Cpu;                 // tarefa em cada CPU (-1 = desligada)
        public string Algorithm = Const.DefaultAlg;
        public int Quantum = Const.DefaultQuantum;
        public int NumCpus = Const.DefaultCpus;
        public uint Rng = 12345;          // semente do sorteio (guardada para ser reprodutível)
        public int EventCount;            // quantos eventos já são "visíveis" neste estado

        public static int[] NewCpuArray(int n)
        {
            int[] a = new int[n];
            for (int i = 0; i < n; i++) a[i] = -1;
            return a;
        }

        /// <summary>Estado inicial com todos os valores padrão e nenhuma tarefa.</summary>
        public static SimState Defaults()
        {
            SimState s = new SimState();
            s.Cpu = NewCpuArray(s.NumCpus);
            return s;
        }

        public SimState Clone()
        {
            SimState c = (SimState)MemberwiseClone();
            c.Tasks = new List<Tcb>();
            foreach (Tcb t in Tasks) c.Tasks.Add(t.Clone());
            c.Cpu = (int[])Cpu.Clone();
            return c;
        }
    }
}
