// =====================================================================================
// Configuracao.cs
// Leitura do arquivo de configuração em texto simples (requisito 3.3):
//     algoritmo_escalonamento;quantum;qtde_cpus
//     id;cor;ingresso;duracao;periodo;prazo;lista_eventos
//
// Regras implementadas:
//  - maiúsculas/minúsculas não importam (3.3.2);
//  - ";" no final da linha é opcional (3.3.3);
//  - linhas em branco e espaços são ignorados (3.3.6);
//  - qualquer nome/caminho de arquivo é aceito (3.3.4): o caminho vem do diálogo "Abrir";
//  - TODOS os erros do arquivo são coletados (com número da linha e motivo) e mostrados
//    ao usuário; se houver erro nada é carregado (3.3.6);
//  - campos vazios recebem valores padrão (3.2);
//  - tarefas aperiódicas (periodo = 0) são ignoradas e isso é reportado (4.4);
//  - a lista de eventos é lida e guardada no TCB, mas ainda não é usada (projeto B).
// =====================================================================================
using System;
using System.Collections.Generic;
using System.Drawing;
using System.Globalization;
using System.IO;
using System.Text;

namespace SimuladorEscalonamento
{
    public class ParseResult
    {
        public bool Ok;
        public List<string> Errors = new List<string>();
        public List<string> Warnings = new List<string>();
        public SimState State;
    }

    public static class ConfigParser
    {
        // Cores padrão (todas diferentes) usadas quando o campo "cor" está vazio.
        private static readonly int[] Palette = {
            0xE6194B, 0x3CB44B, 0x4363D8, 0xF58231, 0x911EB4, 0x42D4F4,
            0xF032E6, 0xBFEF45, 0x469990, 0x9A6324, 0x808000, 0x000075 };

        public static ParseResult ParseFile(string path)
        {
            ParseResult r = new ParseResult();
            string[] lines;
            try { lines = File.ReadAllLines(path, Encoding.UTF8); }
            catch (Exception ex)
            {
                r.Errors.Add("Não foi possível ler o arquivo \"" + path + "\": " + ex.Message);
                return r;
            }
            return Parse(lines);
        }

        /// <summary>Remove ";" finais e espaços, e separa a linha em campos já sem espaços nas pontas.</summary>
        private static string[] Fields(string line)
        {
            string s = line.Trim();
            while (s.EndsWith(";")) s = s.Substring(0, s.Length - 1).TrimEnd();
            string[] f = s.Split(';');
            for (int i = 0; i < f.Length; i++) f[i] = f[i].Trim();
            return f;
        }

        private static bool ParseInt(string s, out int v)
        {
            return int.TryParse(s, NumberStyles.Integer, CultureInfo.InvariantCulture, out v);
        }

        private static string Err(int line, string msg)
        {
            return "Linha " + line + ": " + msg;
        }

        private static bool TryColor(string s, out Color c)
        {
            c = Color.Gray;
            if (s.StartsWith("#")) s = s.Substring(1);
            if (s.Length != 6) return false;
            foreach (char ch in s)
                if (Uri.IsHexDigit(ch) == false) return false;
            int rgb = Convert.ToInt32(s, 16);
            c = Color.FromArgb((rgb >> 16) & 255, (rgb >> 8) & 255, rgb & 255);
            return true;
        }

        public static ParseResult Parse(string[] raw)
        {
            ParseResult r = new ParseResult();

            // Remove linhas em branco guardando o número original da linha (para as mensagens de erro).
            List<int> nums = new List<int>();
            List<string> txt = new List<string>();
            for (int i = 0; i < raw.Length; i++)
            {
                string l = raw[i].Trim();
                if (l.Length == 0) continue;
                nums.Add(i + 1);
                txt.Add(l);
            }
            if (txt.Count < 2)
            {
                r.Errors.Add("O arquivo precisa ter pelo menos duas linhas não vazias: a primeira com os parâmetros do sistema e " +
                             "da segunda em diante uma tarefa por linha.");
                return r;
            }

            SimState st = SimState.Defaults();

            // ---------------- Linha 1: parâmetros do sistema ----------------
            string[] f = Fields(txt[0]);
            if (f.Length > 3)
                r.Errors.Add(Err(nums[0], "a primeira linha deve ter no máximo 3 campos (algoritmo;quantum;qtde_cpus)."));
            if (f.Length > 0 && f[0].Length > 0)
            {
                string a = f[0].ToUpperInvariant();
                if (Scheduler.Exists(a)) st.Algorithm = a;
                else r.Errors.Add(Err(nums[0], "algoritmo de escalonamento \"" + f[0] + "\" não é suportado (disponíveis: " +
                                  string.Join(", ", Scheduler.Names()) + ")."));
            }
            if (f.Length > 1 && f[1].Length > 0)
            {
                int q;
                if (!ParseInt(f[1], out q) || q < 1)
                    r.Errors.Add(Err(nums[0], "quantum \"" + f[1] + "\" inválido: deve ser um inteiro maior ou igual a 1."));
                else st.Quantum = q;
            }
            if (f.Length > 2 && f[2].Length > 0)
            {
                int n;
                if (!ParseInt(f[2], out n) || n < 1 || n > Const.MaxCpus)
                    r.Errors.Add(Err(nums[0], "quantidade de CPUs \"" + f[2] + "\" inválida: deve ser um inteiro entre 1 e " + Const.MaxCpus + "."));
                else st.NumCpus = n;
            }
            st.Cpu = SimState.NewCpuArray(st.NumCpus);

            // ---------------- Demais linhas: tarefas ----------------
            HashSet<int> ids = new HashSet<int>();
            Dictionary<int, int> colorOwner = new Dictionary<int, int>();
            for (int li = 1; li < txt.Count; li++)
            {
                int ln = nums[li];
                string[] t = Fields(txt[li]);
                bool bad = false;
                int id = 0, ing = 0, dur = Const.DefaultDuration, per = Const.DefaultPeriod, prz = 0;
                Color cor = Color.FromArgb(Palette[(li - 1) % Palette.Length] | unchecked((int)0xFF000000));
                string ev = "";

                // id (obrigatório e único)
                if (t[0].Length == 0 || !ParseInt(t[0], out id) || id < 0)
                {
                    r.Errors.Add(Err(ln, "id \"" + t[0] + "\" inválido: deve ser um inteiro maior ou igual a zero."));
                    continue; // sem id não dá para continuar a análise desta linha
                }
                if (!ids.Add(id)) { r.Errors.Add(Err(ln, "id " + id + " repetido: cada tarefa precisa de um id único.")); bad = true; }

                if (t.Length > 1 && t[1].Length > 0)
                {
                    if (!TryColor(t[1], out cor))
                    { r.Errors.Add(Err(ln, "cor \"" + t[1] + "\" inválida: use 6 dígitos hexadecimais RGB, p.ex. F0E0D0.")); bad = true; }
                }
                if (t.Length > 2 && t[2].Length > 0)
                {
                    if (!ParseInt(t[2], out ing) || ing < 0)
                    { r.Errors.Add(Err(ln, "ingresso \"" + t[2] + "\" inválido: deve ser um inteiro maior ou igual a zero.")); bad = true; }
                }
                if (t.Length > 3 && t[3].Length > 0)
                {
                    if (!ParseInt(t[3], out dur) || dur < 1)
                    { r.Errors.Add(Err(ln, "duração \"" + t[3] + "\" inválida: deve ser um inteiro maior ou igual a 1.")); bad = true; }
                }
                if (t.Length > 4 && t[4].Length > 0)
                {
                    if (!ParseInt(t[4], out per))
                    { r.Errors.Add(Err(ln, "período \"" + t[4] + "\" inválido: deve ser um inteiro.")); bad = true; }
                    else if (per < 0)
                    { r.Errors.Add(Err(ln, "período " + per + " inválido: valores negativos representam erro no arquivo.")); bad = true; }
                }
                if (t.Length > 5 && t[5].Length > 0)
                {
                    if (!ParseInt(t[5], out prz) || prz < 0)
                    { r.Errors.Add(Err(ln, "prazo \"" + t[5] + "\" inválido: deve ser um inteiro maior que zero.")); bad = true; }
                }
                if (t.Length > 6)
                {
                    // A lista de eventos pode conter ";" internos: juntamos tudo que sobrou.
                    StringBuilder sb = new StringBuilder();
                    for (int k = 6; k < t.Length; k++) { if (k > 6) sb.Append(';'); sb.Append(t[k]); }
                    ev = sb.ToString();
                }
                if (bad) continue;

                if (per == 0)
                {
                    r.Warnings.Add("Linha " + ln + ": a tarefa " + id + " é aperiódica (período 0). Neste projeto só tarefas periódicas " +
                                   "são simuladas, portanto ela foi IGNORADA.");
                    continue;
                }
                if (prz == 0) prz = per; // prazo padrão = período (deadline implícito)
                if (ev.Length > 0)
                    r.Warnings.Add("Linha " + ln + ": a lista de eventos da tarefa " + id + " foi lida, mas é ignorada neste projeto (será tratada no projeto B).");

                int rgb = cor.ToArgb() & 0xFFFFFF;
                int other;
                if (colorOwner.TryGetValue(rgb, out other))
                    r.Warnings.Add("Linha " + ln + ": a tarefa " + id + " usa a mesma cor da tarefa " + other + "; as duas ficarão difíceis de distinguir no Gantt.");
                else colorOwner[rgb] = id;

                Tcb k2 = new Tcb();
                k2.Id = id; k2.Cor = cor; k2.Ingresso = ing; k2.Duracao = dur; k2.Periodo = per; k2.Prazo = prz;
                k2.Eventos = ev; k2.NextRelease = ing;
                st.Tasks.Add(k2);
            }

            if (r.Errors.Count > 0) return r;
            if (st.Tasks.Count == 0)
                r.Warnings.Add("Não há nenhuma tarefa periódica válida no arquivo: não há o que simular. " +
                               "Você pode adicionar tarefas pela aba \"Sistema e tarefas\".");
            r.State = st;
            r.Ok = true;
            return r;
        }
    }
}
