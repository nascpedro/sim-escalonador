using System;
using System.Collections.Generic;
using System.Drawing;
using SimuladorEscalonamento;

class Comparar {
    static Simulator Criar(string[] linhas) {
        var p = ConfigParser.Parse(linhas);
        if (!p.Ok) throw new Exception(string.Join(";",p.Errors.ToArray()));
        var s = new Simulator(); s.Load(p.State); return s;
    }
    static void Main() {
        var s = Criar(new[]{"RM;4;1", "1;FF0000;0;2;10;1;"});
        s.Step();
        Console.WriteLine("prazo apos primeiro tick: t="+s.Cur.Time+", perdas="+s.Find(1).DeadlineMisses);
        s.Step();
        Console.WriteLine("prazo apos segundo tick: t="+s.Cur.Time+", perdas="+s.Find(1).DeadlineMisses);

        var a=new Tcb{Id=1,Periodo=10,Prazo=2,AbsDeadline=12,Ingresso=10,Duracao=1,State=TaskState.Pronta};
        var b=new Tcb{Id=2,Periodo=10,Prazo=5,AbsDeadline=5,Ingresso=0,Duracao=1,State=TaskState.Pronta};
        uint rng=123;
        var sel=Scheduler.Select(new List<Tcb>{a,b},"RM",1,10,ref rng);
        Console.WriteLine("desempate RM: tarefa="+sel.Chosen[0].Id);

        s=Criar(new[]{"RM;4;1","1;FF0000;0;4;10;8;"}); s.Step();
        var modelo=new GanttModel {Tasks=s.Cur.Tasks,Ticks=s.Ticks,TickCount=s.Cur.Time,
            Events=s.Events,EventCount=s.Cur.EventCount,Time=s.Cur.Time,NumCpus=1,Title="RM"};
        Console.WriteLine("cor historica antes="+s.History[0].Tasks[0].Cor.Name);
        Console.WriteLine("edicao de cor="+(s.EditTask(1,0,4,10,8,Color.Blue)??"aceita"));
        Console.WriteLine("cor usada pelo desenho para todos os ticks="+modelo.Tasks[0].Cor.Name);

        s=Criar(new[]{"EDF;3;2","1;e6194b;0;3;7;7", "2;3cb44b;0;2;5;4;",
            "3;4363d8;2;2;10;10;", "5;f58231;0;1;0;0;"});
        s.RunAll();
        Console.WriteLine("exemplo EDF: tick="+s.Cur.Time+", concluidas="+s.Find(1).JobsCompleted+","+s.Find(2).JobsCompleted+","+s.Find(3).JobsCompleted);
        Console.WriteLine("remover no tick final="+s.RemoveTask(1));

        s=Criar(new[]{"RM;4;1","1;FF0000;0;5;3;2;"});
        s.RunAll();
        Console.WriteLine("sobreposicao: tick="+s.Cur.Time+", concluidas="+s.Find(1).JobsCompleted+", perdas="+s.Find(1).DeadlineMisses);
    }
}
