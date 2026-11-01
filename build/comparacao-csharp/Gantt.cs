// =====================================================================================
// Gantt.cs
// Desenho do gráfico de Gantt, no estilo das figuras da seção 6.4 do livro do Prof. Maziero.
//
// DECISÃO: a MESMA função (GanttRenderer.Draw) desenha na tela (GanttPanel) e no arquivo
// PNG exportado. Assim a imagem final é garantida igual ao que se vê, mas gerada a partir
// dos DADOS (não é um "print" da janela) e cobre toda a simulação, sem limite de tempo.
//
// Layout (de cima para baixo): linhas das CPUs, linhas das tarefas (ID MENOR mais perto
// do eixo X, req. 2.5), eixo do tempo e legenda.
//   - Executando  : retângulo na COR da tarefa, com o número da CPU escrito dentro.
//   - Pronta      : retângulo apenas com contorno (ausência de cor).
//   - Suspensa    : retângulo PRETO com preenchimento pontilhado.
//   - CPU desligada: hachura cinza na linha da CPU.
//   - Eventos     : um símbolo diferente para cada tipo, no instante exato.
// =====================================================================================
using System;
using System.Collections.Generic;
using System.Drawing;
using System.Drawing.Drawing2D;
using System.Drawing.Imaging;
using System.Windows.Forms;

namespace SimuladorEscalonamento
{
    /// <summary>Tudo o que o desenho precisa (evita copiar listas a cada repintura).</summary>
    public class GanttModel
    {
        public List<Tcb> Tasks;
        public List<TickRecord> Ticks;
        public int TickCount;       // quantos ticks de Ticks são visíveis
        public List<GEvent> Events;
        public int EventCount;      // quantos eventos de Events são visíveis
        public int Time;
        public int NumCpus;
        public string Title;
    }

    public static class GanttRenderer
    {
        public const int LeftMargin = 80;
        private const int TopMargin = 22;
        private const int RowH = 24;
        private const int CpuH = 20;
        private const int Gap = 4;
        private const int LegendH = 100;
        private const int RightMargin = 30;
        private const int MinWidth = 800;

        // ---------------------------------------------------------------- geometria
        private static void Geometry(GanttModel m, out int cpuTop, out int taskTop, out int axisY, out int legendTop, out int height)
        {
            cpuTop = TopMargin;
            taskTop = cpuTop + m.NumCpus * (CpuH + Gap) + 12;
            axisY = taskTop + m.Tasks.Count * (RowH + Gap) + 2;
            legendTop = axisY + 34;
            height = legendTop + LegendH;
        }

        public static Size Measure(GanttModel m, float ppt)
        {
            int cpuTop, taskTop, axisY, legendTop, height;
            Geometry(m, out cpuTop, out taskTop, out axisY, out legendTop, out height);
            int w = LeftMargin + (int)Math.Ceiling(m.Time * ppt) + RightMargin;
            return new Size(Math.Max(MinWidth, w), height);
        }

        /// <summary>Tarefas em ordem DECRESCENTE de id: a de menor id fica na última linha (mais perto do eixo X).</summary>
        private static List<Tcb> SortedRows(GanttModel m)
        {
            List<Tcb> l = new List<Tcb>(m.Tasks);
            l.Sort(delegate(Tcb a, Tcb b) { return b.Id.CompareTo(a.Id); });
            return l;
        }

        // Distância entre marcas do eixo, escolhida para que os números não se sobreponham.
        private static int LabelStep(float ppt)
        {
            int[] steps = { 1, 2, 5, 10, 20, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000, 50000, 100000 };
            foreach (int s in steps) if (s * ppt >= 30f) return s;
            return 100000;
        }

        // Cor do texto (preto/branco) que contrasta com o fundo.
        private static Brush Contrast(Color c)
        {
            double lum = 0.299 * c.R + 0.587 * c.G + 0.114 * c.B;
            return lum > 140 ? Brushes.Black : Brushes.White;
        }

        // Guarda objetos GDI para liberá-los todos no fim do desenho.
        private static T Keep<T>(List<IDisposable> l, T obj) where T : IDisposable
        {
            l.Add(obj);
            return obj;
        }

        // ---------------------------------------------------------------- desenho principal
        /// <param name="visFrom">borda esquerda visível (em pixels do desenho)</param>
        /// <param name="visTo">borda direita visível</param>
        /// <param name="cursor">desenha uma linha vermelha no instante atual (só na tela)</param>
        public static void Draw(Graphics g, GanttModel m, float ppt, float visFrom, float visTo, bool cursor)
        {
            int cpuTop, taskTop, axisY, legendTop, height;
            Geometry(m, out cpuTop, out taskTop, out axisY, out legendTop, out height);
            List<Tcb> rows = SortedRows(m);
            Dictionary<int, int> rowOf = new Dictionary<int, int>();
            Dictionary<int, SolidBrush> brushes = new Dictionary<int, SolidBrush>();
            Dictionary<int, Color> colors = new Dictionary<int, Color>();
            List<IDisposable> tmp = new List<IDisposable>();
            try
            {
                for (int i = 0; i < rows.Count; i++) rowOf[rows[i].Id] = i;
                foreach (Tcb k in m.Tasks)
                {
                    brushes[k.Id] = Keep(tmp, new SolidBrush(k.Cor));
                    colors[k.Id] = k.Cor;
                }

                g.SmoothingMode = SmoothingMode.AntiAlias;
                g.Clear(Color.White);
                Font font = Keep(tmp, new Font(FontFamily.GenericSansSerif, 8.5f));
                Font small = Keep(tmp, new Font(FontFamily.GenericSansSerif, 7.5f));
                Font bold = Keep(tmp, new Font(FontFamily.GenericSansSerif, 9f, FontStyle.Bold));
                StringFormat center = Keep(tmp, new StringFormat());
                center.Alignment = StringAlignment.Center;
                center.LineAlignment = StringAlignment.Center;
                Pen gridPen = Keep(tmp, new Pen(Color.FromArgb(225, 225, 225)));
                Pen borderPen = Keep(tmp, new Pen(Color.FromArgb(90, 90, 90)));
                Pen readyPen = Keep(tmp, new Pen(Color.FromArgb(150, 150, 150)));
                Pen axisPen = Keep(tmp, new Pen(Color.Black, 1.5f));
                Brush offBrush = Keep(tmp, new HatchBrush(HatchStyle.WideUpwardDiagonal, Color.Gray, Color.White));
                Brush suspBrush = Keep(tmp, new HatchBrush(HatchStyle.Percent50, Color.Black, Color.White));

                int first = (int)Math.Floor((visFrom - LeftMargin) / ppt) - 1;
                if (first < 0) first = 0;
                int last = (int)Math.Ceiling((visTo - LeftMargin) / ppt) + 1;
                if (last > m.TickCount - 1) last = m.TickCount - 1;
                int step = LabelStep(ppt);

                // Região de desenho dos dados: não invade a coluna fixa de rótulos.
                g.SetClip(new RectangleF(visFrom + LeftMargin - 6, 0, Math.Max(1f, visTo - visFrom - LeftMargin + 6), height));

                // Linhas verticais de grade
                int g0 = (first / step) * step;
                for (int tk = g0; tk <= last + 1; tk += step)
                {
                    float gx = LeftMargin + tk * ppt;
                    g.DrawLine(gridPen, gx, cpuTop, gx, axisY);
                }

                // Blocos (CPUs e tarefas)
                for (int t = first; t <= last; t++)
                {
                    TickRecord tr = m.Ticks[t];
                    float x = LeftMargin + t * ppt;

                    for (int c = 0; c < m.NumCpus && c < tr.CpuTask.Length; c++)
                    {
                        float y = cpuTop + c * (CpuH + Gap);
                        RectangleF rc = new RectangleF(x, y, ppt, CpuH);
                        int id = tr.CpuTask[c];
                        if (id < 0)
                        {
                            g.FillRectangle(offBrush, rc);               // CPU desligada
                        }
                        else
                        {
                            SolidBrush b;
                            if (!brushes.TryGetValue(id, out b)) b = (SolidBrush)Brushes.Gray;
                            g.FillRectangle(b, rc);
                            if (ppt >= 20f) g.DrawString("T" + id, small, colors.ContainsKey(id) ? Contrast(colors[id]) : Brushes.Black, rc, center);
                        }
                        if (ppt >= 3f) g.DrawRectangle(borderPen, x, y, ppt, CpuH);
                    }

                    for (int r = 0; r < rows.Count; r++)
                    {
                        Tcb k = rows[r];
                        byte code;
                        if (!tr.Codes.TryGetValue(k.Id, out code)) code = 0;
                        if (code == 0) continue;
                        float y = taskTop + r * (RowH + Gap);
                        RectangleF rc = new RectangleF(x, y, ppt, RowH);
                        if (code == 2)
                        {
                            g.FillRectangle(brushes[k.Id], rc);
                            g.DrawRectangle(borderPen, x, y, ppt, RowH);
                            if (ppt >= 20f)
                            {
                                int cpu = -1;
                                for (int c = 0; c < tr.CpuTask.Length; c++) if (tr.CpuTask[c] == k.Id) cpu = c;
                                g.DrawString("CPU" + (cpu + 1), small, Contrast(k.Cor), rc, center);
                            }
                        }
                        else if (code == 1)
                        {
                            g.DrawRectangle(readyPen, x, y, ppt, RowH);    // pronta: sem cor, só contorno
                        }
                        else
                        {
                            g.FillRectangle(suspBrush, rc);                // suspensa: preto pontilhado
                            g.DrawRectangle(Pens.Black, x, y, ppt, RowH);
                        }
                    }
                }

                // Eventos
                for (int i = 0; i < m.EventCount; i++)
                {
                    GEvent e = m.Events[i];
                    if (e.Type == EventType.Info || e.TaskId < 0) continue;
                    float ex = LeftMargin + e.Time * ppt;
                    if (ex < visFrom - 12 || ex > visTo + 12) continue;
                    int r;
                    if (!rowOf.TryGetValue(e.TaskId, out r)) continue;
                    DrawGlyph(g, e.Type, ex, taskTop + r * (RowH + Gap), RowH);
                }

                // Linha do instante atual
                if (cursor)
                {
                    float cx = LeftMargin + m.Time * ppt;
                    using (Pen p = new Pen(Color.Red, 1f))
                    {
                        p.DashStyle = DashStyle.Dash;
                        g.DrawLine(p, cx, cpuTop - 4, cx, axisY);
                    }
                }
                g.ResetClip();

                // Coluna fixa de rótulos (fica visível mesmo com rolagem horizontal)
                g.FillRectangle(Brushes.White, visFrom, 0, LeftMargin - 6, axisY);
                g.DrawString(m.Title == null ? "" : m.Title, bold, Brushes.Black, visFrom + 4, 2);
                for (int c = 0; c < m.NumCpus; c++)
                    g.DrawString("CPU " + (c + 1), font, Brushes.Black, visFrom + 4, cpuTop + c * (CpuH + Gap) + 3);
                for (int r = 0; r < rows.Count; r++)
                {
                    float y = taskTop + r * (RowH + Gap);
                    g.FillRectangle(brushes[rows[r].Id], visFrom + 4, y + 6, 12, 12);
                    g.DrawRectangle(Pens.Black, visFrom + 4, y + 6, 12, 12);
                    g.DrawString("T" + rows[r].Id, font, Brushes.Black, visFrom + 20, y + 4);
                }

                // Eixo do tempo
                float axisEnd = LeftMargin + m.Time * ppt + 10;
                g.DrawLine(axisPen, LeftMargin, axisY, axisEnd, axisY);
                int a0 = 0;
                for (int tk = a0; tk <= m.Time; tk += step)
                {
                    float ax = LeftMargin + tk * ppt;
                    if (ax < visFrom + LeftMargin - 4 || ax > visTo + 20) continue;
                    g.DrawLine(axisPen, ax, axisY, ax, axisY + 4);
                    g.DrawString(tk.ToString(), small, Brushes.Black, ax - 8, axisY + 5);
                }
                g.DrawString("tempo (ticks)", small, Brushes.Black, visFrom + 4, axisY + 5);

                DrawLegend(g, font, offBrush, suspBrush, readyPen, borderPen, visFrom + 10, legendTop);
            }
            finally
            {
                foreach (IDisposable d in tmp) d.Dispose();
            }
        }

        // ---------------------------------------------------------------- símbolos dos eventos
        /// <summary>
        /// Um símbolo diferente por tipo de evento. (x, y) = instante exato e topo da linha; h = altura da linha.
        /// </summary>
        private static void DrawGlyph(Graphics g, EventType type, float x, float y, float h)
        {
            switch (type)
            {
                case EventType.Arrival: // seta para CIMA azul = ativação/ingresso
                    using (Pen p = new Pen(Color.Blue, 2f))
                    {
                        g.DrawLine(p, x, y + h, x, y + 5);
                        g.FillPolygon(Brushes.Blue, new PointF[] { new PointF(x, y - 1), new PointF(x - 4.5f, y + 7), new PointF(x + 4.5f, y + 7) });
                    }
                    break;
                case EventType.Finish: // seta para BAIXO verde = término
                    using (Pen p = new Pen(Color.DarkGreen, 2f))
                    {
                        g.DrawLine(p, x, y, x, y + h - 5);
                        g.FillPolygon(Brushes.DarkGreen, new PointF[] { new PointF(x, y + h + 1), new PointF(x - 4.5f, y + h - 7), new PointF(x + 4.5f, y + h - 7) });
                    }
                    break;
                case EventType.DeadlineMiss: // X vermelho = perda de prazo
                    using (Pen p = new Pen(Color.Red, 2.5f))
                    {
                        float cy = y + h * 0.5f;
                        g.DrawLine(p, x - 5, cy - 5, x + 5, cy + 5);
                        g.DrawLine(p, x - 5, cy + 5, x + 5, cy - 5);
                    }
                    break;
                case EventType.Draw: // losango laranja = tarefa escolhida por sorteio
                    {
                        float cy = y + h * 0.25f;
                        PointF[] d = { new PointF(x, cy - 5), new PointF(x + 5, cy), new PointF(x, cy + 5), new PointF(x - 5, cy) };
                        g.FillPolygon(Brushes.Orange, d);
                        g.DrawPolygon(Pens.Black, d);
                    }
                    break;
                case EventType.QuantumEnd: // círculo roxo = fim de quantum
                    g.FillEllipse(Brushes.Purple, x - 3.5f, y + h - 8, 7, 7);
                    break;
                case EventType.Preempt: // quadrado magenta = preempção
                    g.FillRectangle(Brushes.Magenta, x - 3.5f, y + h * 0.62f - 3.5f, 7, 7);
                    g.DrawRectangle(Pens.Black, x - 3.5f, y + h * 0.62f - 3.5f, 7, 7);
                    break;
            }
        }

        private static void DrawLegend(Graphics g, Font font, Brush offBrush, Brush suspBrush, Pen readyPen, Pen borderPen, float x0, float y0)
        {
            const float colW = 270f, lineH = 22f;
            string[] texts = {
                "Executando (cor da tarefa; nº = CPU)", "Pronta (sem cor, só contorno)", "Suspensa (preto pontilhado)",
                "CPU desligada (hachura cinza)", "Ativação / ingresso da tarefa", "Término da execução",
                "Perda de prazo (deadline)", "Escolha por sorteio (desempate)", "Fim de quantum", "Preempção" };
            for (int i = 0; i < texts.Length; i++)
            {
                float x = x0 + (i % 3) * colW;
                float y = y0 + (i / 3) * lineH;
                float sx = x + 12;   // centro do símbolo
                switch (i)
                {
                    case 0: using (SolidBrush b = new SolidBrush(Color.SteelBlue)) g.FillRectangle(b, sx - 11, y + 3, 22, 14);
                            g.DrawRectangle(borderPen, sx - 11, y + 3, 22, 14); break;
                    case 1: g.DrawRectangle(readyPen, sx - 11, y + 3, 22, 14); break;
                    case 2: g.FillRectangle(suspBrush, sx - 11, y + 3, 22, 14); g.DrawRectangle(Pens.Black, sx - 11, y + 3, 22, 14); break;
                    case 3: g.FillRectangle(offBrush, sx - 11, y + 3, 22, 14); g.DrawRectangle(borderPen, sx - 11, y + 3, 22, 14); break;
                    case 4: DrawGlyph(g, EventType.Arrival, sx, y, 20); break;
                    case 5: DrawGlyph(g, EventType.Finish, sx, y, 20); break;
                    case 6: DrawGlyph(g, EventType.DeadlineMiss, sx, y, 20); break;
                    case 7: DrawGlyph(g, EventType.Draw, sx, y + 5, 20); break;
                    case 8: DrawGlyph(g, EventType.QuantumEnd, sx, y, 20); break;
                    case 9: DrawGlyph(g, EventType.Preempt, sx, y, 20); break;
                }
                g.DrawString(texts[i], font, Brushes.Black, x + 28, y + 3);
            }
        }

        // ---------------------------------------------------------------- exportação
        /// <summary>
        /// Salva TODO o gráfico em PNG. A escala é 20 px/tick; se a simulação for tão longa que a
        /// imagem passaria de 30000 px de largura (limite prático do GDI+), a escala é reduzida
        /// para que a simulação inteira continue cabendo em uma única imagem.
        /// </summary>
        public static void ExportPng(GanttModel m, string path)
        {
            float ppt = 20f;
            Size sz = Measure(m, ppt);
            if (sz.Width > 30000)
            {
                ppt = (30000f - LeftMargin - RightMargin) / Math.Max(1, m.Time);
                sz = Measure(m, ppt);
            }
            using (Bitmap bmp = new Bitmap(sz.Width, sz.Height))
            using (Graphics g = Graphics.FromImage(bmp))
            {
                Draw(g, m, ppt, 0f, sz.Width, false);
                bmp.Save(path, ImageFormat.Png);
            }
        }
    }

    /// <summary>Painel rolável que mostra o Gantt na tela.</summary>
    public class GanttPanel : Panel
    {
        public GanttModel Model;
        public float Ppt = 24f; // pixels por tick (zoom)

        public GanttPanel()
        {
            AutoScroll = true;
            DoubleBuffered = true;   // evita cintilação ao repintar
            ResizeRedraw = true;
            BackColor = Color.White;
        }

        public void UpdateView()
        {
            if (Model != null) AutoScrollMinSize = GanttRenderer.Measure(Model, Ppt);
            Invalidate();
        }

        /// <summary>Rola o gráfico para que o instante atual fique visível.</summary>
        public void ScrollToCurrent()
        {
            if (Model == null) return;
            float cx = GanttRenderer.LeftMargin + Model.Time * Ppt;
            float left = -AutoScrollPosition.X;
            float right = left + ClientSize.Width;
            if (cx > right - 30 || cx < left + GanttRenderer.LeftMargin)
                AutoScrollPosition = new Point(Math.Max(0, (int)(cx - ClientSize.Width + 100)), -AutoScrollPosition.Y);
        }

        protected override void OnScroll(ScrollEventArgs se)
        {
            base.OnScroll(se);
            Invalidate(); // a coluna fixa de rótulos precisa ser redesenhada ao rolar
        }

        protected override void OnPaint(PaintEventArgs e)
        {
            base.OnPaint(e);
            if (Model == null) return;
            e.Graphics.TranslateTransform(AutoScrollPosition.X, AutoScrollPosition.Y);
            float left = -AutoScrollPosition.X;
            GanttRenderer.Draw(e.Graphics, Model, Ppt, left, left + ClientSize.Width, true);
        }
    }
}
