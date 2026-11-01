// =====================================================================================
// Escalonador.cs
// Algoritmos de escalonamento (RM e EDF) e a seleção das próximas tarefas.
//
// DECISÃO (requisito 4.2): cada algoritmo é apenas UMA FUNÇÃO de prioridade
// (PriorityFunc) registrada em um dicionário por nome. Para criar um novo algoritmo
// basta chamar Scheduler.Register("NOME", funcao). O motor da simulação não precisa
// ser alterado. Menor valor retornado = tarefa mais prioritária.
//
// DECISÃO: os critérios de desempate (req. 4.3) são os mesmos para todos os algoritmos,
// por isso ficam centralizados aqui, e não dentro de cada função de prioridade.
// =====================================================================================
using System;
using System.Collections.Generic;

namespace SimuladorEscalonamento
{
    /// <summary>Função de prioridade: quanto MENOR o valor, MAIS prioritária a tarefa.</summary>
    public delegate double PriorityFunc(Tcb t, int now);

    /// <summary>Resultado de uma seleção: tarefas escolhidas e quais foram decididas por sorteio.</summary>
    public class SelectResult
    {
        public List<Tcb> Chosen = new List<Tcb>();
        public HashSet<int> Drawn = new HashSet<int>();
    }

    public static class Scheduler
    {
        private static Dictionary<string, PriorityFunc> algs = new Dictionary<string, PriorityFunc>();

        static Scheduler()
        {
            // Rate Monotonic: menor período = maior prioridade (prioridade fixa).
            Register("RM", delegate(Tcb t, int now) { return t.Periodo; });
            // Earliest Deadline First: prazo ABSOLUTO mais próximo = maior prioridade.
            Register("EDF", delegate(Tcb t, int now) { return t.AbsDeadline; });
        }

        /// <summary>Registra (ou substitui) um algoritmo. O nome é guardado em maiúsculas (req. 3.3.2).</summary>
        public static void Register(string name, PriorityFunc f)
        {
            algs[name.ToUpperInvariant()] = f;
        }

        public static bool Exists(string name)
        {
            return name != null && algs.ContainsKey(name.ToUpperInvariant());
        }

        public static string[] Names()
        {
            List<string> l = new List<string>(algs.Keys);
            l.Sort();
            return l.ToArray();
        }

        /// <summary>
        /// Compara duas tarefas: prioridade do algoritmo e depois os desempates do req. 4.3:
        /// (1) a que já estava executando, (2) menor prazo, (3) quem ingressou antes,
        /// (4) menor duração. Retornar 0 significa empate total (será resolvido por sorteio).
        /// </summary>
        private static int Cmp(Tcb a, Tcb b, PriorityFunc f, int now)
        {
            int c = f(a, now).CompareTo(f(b, now));
            if (c != 0) return c;
            int ra = a.State == TaskState.Executando ? 0 : 1;
            int rb = b.State == TaskState.Executando ? 0 : 1;
            c = ra.CompareTo(rb);
            if (c != 0) return c;
            c = a.AbsDeadline.CompareTo(b.AbsDeadline);
            if (c != 0) return c;
            c = a.Ingresso.CompareTo(b.Ingresso);
            if (c != 0) return c;
            return a.Duracao.CompareTo(b.Duracao);
        }

        /// <summary>Ordena tarefas da mais para a menos prioritária (usado também para exibir a fila de prontos).</summary>
        public static List<Tcb> Sort(List<Tcb> tasks, string alg, int now)
        {
            PriorityFunc f = algs[alg.ToUpperInvariant()];
            List<Tcb> l = new List<Tcb>(tasks);
            // O Id é só o último critério da ORDENAÇÃO (para ficar determinístico);
            // não é usado para detectar empates.
            l.Sort(delegate(Tcb a, Tcb b)
            {
                int c = Cmp(a, b, f, now);
                return c != 0 ? c : a.Id.CompareTo(b.Id);
            });
            return l;
        }

        /// <summary>
        /// Escolhe até ncpus tarefas da fila de prontos (GLOBAL). Se houver mais tarefas
        /// empatadas do que vagas, sorteia usando o gerador guardado no estado (rng).
        /// </summary>
        public static SelectResult Select(List<Tcb> ready, string alg, int ncpus, int now, ref uint rng)
        {
            PriorityFunc f = algs[alg.ToUpperInvariant()];
            List<Tcb> sorted = Sort(ready, alg, now);
            SelectResult res = new SelectResult();

            int i = 0;
            while (i < sorted.Count && res.Chosen.Count < ncpus)
            {
                // Grupo de tarefas totalmente empatadas com a tarefa i.
                int j = i + 1;
                while (j < sorted.Count && Cmp(sorted[i], sorted[j], f, now) == 0) j++;
                int size = j - i;
                int slots = ncpus - res.Chosen.Count;

                if (size <= slots)
                {
                    for (int k = i; k < j; k++) res.Chosen.Add(sorted[k]);
                }
                else
                {
                    // Há mais empatadas do que CPUs livres: sorteio (critério 5).
                    List<Tcb> group = sorted.GetRange(i, size);
                    for (int n = 0; n < slots; n++)
                    {
                        rng = rng * 1103515245u + 12345u;            // gerador congruencial linear simples
                        int idx = (int)((rng >> 16) % (uint)group.Count);
                        res.Chosen.Add(group[idx]);
                        res.Drawn.Add(group[idx].Id);
                        group.RemoveAt(idx);
                    }
                }
                i = j;
            }
            return res;
        }
    }
}
