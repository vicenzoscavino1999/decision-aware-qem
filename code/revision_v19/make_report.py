from pathlib import Path
import argparse
import json
import shutil
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

HERE=Path(__file__).resolve().parent
parser=argparse.ArgumentParser()
parser.add_argument('--output',type=Path,default=HERE.parent)
OUT=parser.parse_args().output
df=pd.read_csv(HERE/'results/summary.csv').fillna('')
policies=['Raw','Accuracy-ZNE','Decision-ZNE','MSE-selector','GRI-selector']
labels=['Always Raw','Accuracy-ZNE','Decision-ZNE','MSE selector','GRI selector']
colors=['#255A78','#7E929F','#A1AEB6','#A95545','#207A66']
plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False,
                     'pdf.fonttype':42,'ps.fonttype':42})
fig,axes=plt.subplots(1,2,figsize=(10.4,3.8),sharey=True)
for ax,comparison,title in zip(axes,['evaluation','end_to_end'],
                             ['Equal evaluation shots','Equal full cost, including learning'],strict=True):
    sub=df[(df.base_t==512)&(df.comparison==comparison)&(df.kind=='failure_rate')].set_index('policy')
    for y,p in enumerate(policies):
        row=sub.loc[p]
        ax.errorbar(100*row.estimate,y,xerr=[[100*(row.estimate-row.ci_low)],
            [100*(row.ci_high-row.estimate)]],fmt='o',color=colors[y],capsize=3,markersize=6,lw=1.7)
        ax.annotate(f'{100*row.estimate:.2f}%',(100*row.estimate,y),xytext=(0,9),
                    textcoords='offset points',ha='center',fontsize=9,color=colors[y])
    ax.set_title(title,fontsize=11,pad=12)
    ax.set_xlabel('Test failure (%) - lower is better')
    ax.set_xlim(10,62)
    ax.set_yticks(range(len(policies)),labels)
    ax.grid(axis='x',alpha=.2)
axes[0].invert_yaxis()
fig.suptitle('Retrospective E1 audit | 48 instances | 10 fit / 10 select / 20 test',fontsize=12,y=1.01)
fig.tight_layout()
(OUT/'figures').mkdir(exist_ok=True)
fig.savefig(OUT/'figures/F7_e1_reanalysis.pdf',bbox_inches='tight')
fig.savefig(OUT/'figures/F7_e1_reanalysis.png',dpi=180,bbox_inches='tight')
repo_figure=HERE.parent/'figures/F7_e1_reanalysis.pdf'
if repo_figure.parent.exists() and repo_figure.resolve() != (OUT/'figures/F7_e1_reanalysis.pdf').resolve():
    shutil.copy2(OUT/'figures/F7_e1_reanalysis.pdf',repo_figure)
plt.close(fig)

diagnostics=json.loads((HERE/'results/diagnostics.json').read_text())
choices={}
for t in (512,1024):
    choices[t]={}
    for selector in ['GRI-selector','MSE-selector']:
        chosen=[d['choices'][selector] for d in diagnostics if d['base_t']==t]
        choices[t][selector]={p:chosen.count(p) for p in policies[:3]}

report='''REVISION V19 - 22 DE OCTUBRE DE 2026

Estado: borrador revisado; reanalisis posterior, no confirmacion prospectiva.

CAMBIOS PRINCIPALES

1. E1: separacion de datos.
Se conservaron las 48 instancias y se dividieron por hash las 40 replicas de
cada una en 10 para ajustar coeficientes, 10 para elegir metodo y 20 para
evaluar. El ajuste y la seleccion no reciben los datos de evaluacion.
No se escogieron particiones ni presupuestos segun resultados favorables.
Los coeficientes y la seleccion todavia usan informacion ideal de simulacion:
este analisis no demuestra que el algoritmo se pueda desplegar sin ella.

2. Presupuesto.
El E1 antiguo comparaba B shots por candidato Y escala: Raw usaba B y ZNE 3B.
La revision reconstruye bloques exactos a partir de sumas acumuladas.
Con t=512, todos reciben 38 400 shots de evaluacion por decision en la
comparacion de evaluacion igualada. Los costos de ajuste y seleccion se
muestran aparte: no se confunden con un presupuesto total igualado.
En la comparacion completa, cada politica tiene 1 920 000 shots por instancia
para 20 decisiones, equivalentes a 96 000 por decision amortizada.
Los selectores pagan 384 000 de ajuste y 768 000 de seleccion por instancia;
quedan 768 000 para evaluar 20 decisiones. Raw usa todo en evaluacion.
Los registros compartidos entre metodos se contabilizan una sola vez.

RESULTADO PRINCIPAL (t=512; fallo menor es mejor)

Politica                Evaluacion igualada       Costo completo igualado
Raw                     31.25 %                   23.33 %
Accuracy-ZNE            47.19 %                   35.00 %
Decision-ZNE            47.92 %                   38.65 %
Selector MSE            47.19 %                   47.19 %
Selector GRI            30.83 %                   30.83 %

GRI menos Raw, evaluacion igualada: -0.42 puntos porcentuales;
intervalo descriptivo 95 %: [-1.98, +1.15]. No demuestra ventaja sobre Raw.
GRI menos Raw, costo completo: +7.50 puntos;
intervalo descriptivo 95 %: [+4.17, +10.94]. Raw presenta menos fallos.
GRI menos selector MSE: -16.35 puntos;
intervalo descriptivo 95 %: [-21.88, -11.15].
En t=1024 se mantiene la lectura cualitativa. Ambos presupuestos usan
registros que pueden solaparse: no son dos confirmaciones independientes.

Los intervalos usan 10 000 bootstrap de las 48 instancias completas,
manteniendo el emparejamiento entre politicas. Son descriptivos posteriores;
no se presentan p-valores confirmatorios ni se cambia el umbral original.

3. Corolarios 9.2 y 9.3.
Se sustituyo la afirmacion de matching minimax por el test gaussiano exacto.
Para N(mu,sigma^2/B) frente a N(0,sigma^2/B), el error minimax es
Phi(-sqrt(B)*mu/(2*sigma)), con exponente mu^2/(8*sigma^2).
El plug-in de umbral cero tiene exponente mu^2/(2*sigma^2) solo en la instancia
original, pero error 1/2 en la alternativa de frontera. No es minimax-optimo.
La cota KL se conserva como cota no ajustada y se corrigen las pruebas y
referencias que confundian informacion KL, error puntual y error del par.

CORRECCIONES ADICIONALES

- Se acoto la novedad: la propagacion de covarianza es estadistica estandar;
  una restriccion fisica estricta exige una clase admisible de mapas.
- Se corrigio el control CDR: el kernel escala por a^2; lo invariante son
  el ranking y el riesgo estandarizado, no el kernel sin normalizar.
- Se preciso el CLT: el error Berry-Esseen es frente a la gaussiana con
  covarianza de presupuesto finito. Usar la covarianza limite exige controlar
  tambien su velocidad de convergencia.
- Se actualizaron abstract, metodos, resultados, limitaciones y conclusion.
  Los resultados E1 antiguos quedan identificados como historicos.
- E2, FakeKolkata y hardware se conservan con sus limitaciones. Esta revision
  no ejecuta ni revalida completamente sus pipelines.

ALCANCE Y TRABAJO CIENTIFICO PENDIENTE

El nuevo analisis elimina la reutilizacion dentro de la particion elegida,
pero sigue siendo retrospectivo sobre datos cuyo resultado agregado se
conocia. La referencia ideal es un oraculo de simulacion y la amortizacion
asume 20 decisiones sobre el mismo paisaje. No se establece ventaja en una
unica decision ni escalabilidad ni ventaja practica del selector sobre Raw.
Para una nueva afirmacion confirmatoria se necesita un protocolo prospectivo,
nuevas instancias/datos, seleccion sin informacion ideal inaccesible y costos
completos fijados antes de evaluar. La v19 sigue siendo un borrador a revisar
por el autor antes de cualquier envio.

INTEGRIDAD Y REPRODUCCION

La v18 y el freeze de 52 archivos no se modificaron. Los archivos nuevos
están en revision_v19 y en decision_residual_fields_theory_v19.tex.
El paquete entregado incluye inputs .npz, protocolo, codigo, pruebas,
resultados completos, versiones de dependencias y hashes.
No se realizaron nuevos trabajos de hardware ni publicaciones remotas.

Desde la carpeta del paquete, con Python 3.12 y las dependencias instaladas:
  python -m pip install -r reanalysis/requirements-analysis.txt
  python -m pytest reanalysis/test_revision.py -q
  python reanalysis/e1_reanalysis.py --raw reanalysis/inputs --output work_reproduced

Compilacion del manuscrito: pdflatex main.tex (dos pasadas).
'''
report += '\nELECCIONES CONGELADAS ANTES DE EVALUAR\n'+json.dumps(choices,indent=2)+'\n'
(OUT/'LEEME_revision_v19.txt').write_text(report,encoding='utf-8')
print(json.dumps(choices,indent=2))
