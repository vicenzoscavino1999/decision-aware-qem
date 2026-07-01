# Pre-registro tier-chico FakeBackend v1

> **Documento de PRE-REGISTRO para revision y sello.** Este arm es aditivo y se debe sellar
> por hash + commit **ANTES** de correr. No modifica el freeze publicado del paquete
> (`sha256:2AF91BE1...`, 52 archivos), no modifica `src/daqem/*`, no modifica E1/E2/E3, y no
> modifica el de-risk FakeBackend ya sellado (`sha256:6210C6F1...`). Este documento define la
> fuente de verdad del tier-chico FakeBackend.
>
> **Fecha:** 2026-07-01. **Estado:** pre-registro no ejecutado. **Ejecucion:** prohibida hasta
> despues del sello.

---

## 0. Rationale ciego

El de-risk FakeBackend previo dio un **hint** en el piso de ruido: el primario fue 11 vs 10
pares discordantes (no significativo), pero direccionalmente consistente con la teoria: bajo
ruido de dispositivo, el selector DA a veces elige `Raw+REM`, y el diagnostico D1 observo 3/18
flips full-Sigma vs diagonal, frente a 0/72 en el regimen uniforme.

Este tier-chico prueba esa senial de forma propiamente potenciada y **ciega**. Para evitar
forking paths:

- no se usan las celdas `P001`, `P002`, `P004`;
- no se usan "los budgets que ganaron" en el de-risk;
- el endpoint primario no filtra por resultado ni por una banda definida bajo Kolkata;
- el pool es el conjunto completo `C001`-`C048`, ya pre-registrado, bajo un regimen de ruido
  nuevo.

El resultado se reportara tal como salga. Un null es informativo y fortalece el negativo bajo un
modelo calibrado de dispositivo.

---

## 1. Backend y ruido

```yaml
backend:
  name: FakeKolkataV2
  rationale: >
    Mismo backend que el de-risk, anclado a van den Berg 2023. Es un stress test calibrado
    de ruido de dispositivo, no evidencia de hardware.
  noise_model: "NoiseModel.from_backend(FakeKolkataV2())"
  framing: "calibrated device-noise stress test, NOT hardware evidence"

transpilation:
  rule: "noise-aware por instancia, ciega a resultados de decision"
  optimization_level: 1
  seed_transpiler: 260616
  target: "FakeKolkataV2.target"
  record_per_instance: [mapping, swap_count, depth, size]
  restriction: >
    La transpilacion se hace por instancia usando calibracion/topologia del dispositivo,
    no resultados de decision. El mapping no se elige por performance del selector.
```

Cada instancia `Cxxx` se transpila bajo la misma regla determinista. El mapping fisico y el
`swap_count` se registran para auditoria, pero no son criterios de inclusion/exclusion.

---

## 2. Instancias

```yaml
instances:
  pool: [C001-C048]
  count: 48
  excluded_from_design: [P001, P002, P004]
  use_all_instances: true
  no_cherry_pick: true
```

El pool confirmatorio completo `C001`-`C048` se reutiliza como set pre-registrado bajo un regimen
de ruido **nuevo**: FakeKolkataV2. Este arm es aditivo y no toca los experimentos E1/E2/E3, que
corresponden al regimen de ruido uniforme ya publicado.

No se descartan ni reordenan instancias por dificultad observada bajo Kolkata, por resultado, por
mapping, por saturacion, ni por budget favorable. Si una instancia es trivial o saturada, se
reporta como parte del pool completo.

---

## 3. Menu y selectores

```yaml
method_menu:
  - Raw
  - Raw+REM
  - Accuracy-ZNE
  - Decision-ZNE
  - CDR
excluded_methods:
  - PEC
  - CDR+REM

REM:
  implementation: "experiments/derisk_fakebackend/rem.py"
  convention: "matched_total"
  f_calib: 0.2
  C_eval: "B - 2*calib"
  C_calib: "2*calib"
  note: >
    La calibracion de REM se paga dentro del presupuesto nominal; REM no recibe shots extra.

CDR:
  role: "control afin"
  C_train: "reportado por separado"
  cost_claim: "no se reclama ventaja de costo por CDR"

selectors:
  DA: "argmin GRI"
  MSE: "argmin MSE"
  tie_break: "lexicografico"
```

El menu es cerrado. No se agrega PEC porque el tier-chico FakeBackend no incluye caracterizacion
cuasi-probabilistica del canal. No se agrega `CDR+REM` para evitar una rama nueva no testeada en
el de-risk y para mantener el menu minimo.

Los selectores son los mismos conceptos congelados del paquete: DA minimiza el riesgo GRI y MSE
minimiza el MSE. En empates exactos se aplica tie-break lexicografico.

---

## 4. Budgets, replicas y semillas

```yaml
budgets: [256, 512, 1024, 2048, 4096, 8192]
B_star: 512
paired_replicates_per_instance: 40
paired_observations_at_B_star: 1920  # 48 instancias x 40 replicas
rng:
  policy: "PAP section 18"
  root_seed: 260616
  derivation: "hash(instance_id, method, budget, replicate_id, stream)"
  rem_calibration_stream: "rem_calibration"
```

Las 40 replicas son pareadas por instancia, budget y replicate id. Las mismas semillas de replica
se usan entre metodos cuando corresponda para mantener CRN y comparacion pareada.

---

## 5. Endpoints pre-especificados

### 5.1 Primario

```yaml
primary_endpoint:
  estimand: "reduccion pareada de fallo de decision: DA-selector vs MSE-selector"
  budget: 512
  pool: "C001-C048 completo"
  filtering: "none"
  test: "McNemar one-sided"
  alpha: 0.05
  confidence_interval: "bootstrap paired CI for relative reduction"
  practical_threshold: 0.15
  report_small_significant_effects: true
```

El endpoint primario es un solo test: reduccion pareada de fallo de decision del selector DA
contra el selector MSE en `B*=512`, pooled sobre las 48 C-ids completas. No hay filtro in-band bajo
Kolkata, porque eso seria seleccion dependiente del resultado. Las celdas triviales donde
`DA == MSE` aportan `b=c=0`; no sesgan el test, solo reducen la informacion efectiva.

Se reporta:

- `paired_n`;
- `both_fail`;
- `b_DA_better`;
- `c_DA_worse`;
- `failure_rate_MSE`;
- `failure_rate_DA`;
- `observed_rel_reduction`;
- estadistico y p-value de McNemar una cola;
- IC bootstrap de la reduccion relativa;
- comparacion contra el umbral practico 0.15.

Un efecto pequeno pero significativo se reporta como informativo; no se infla a claim practico si
queda por debajo de 0.15.

### 5.2 Secundarios

Todos los secundarios son pre-especificados y no son headline. Se corrigen por multiplicidad con
Holm o BH-FDR; la eleccion del procedimiento se reporta antes de interpretar los secundarios y se
aplica a todos ellos como familia secundaria.

```yaml
secondary_endpoints:
  multiplicity: "Holm or BH-FDR over the secondary family"
  endpoints:
    in_band_uniform_frozen:
      definition: "estrato in-band definido por el estado uniforme congelado"
      blindness: "ciego a Kolkata"
    epsilon_opt_terciles:
      bins: [easy, medium, hard]
      counts: [16, 16, 16]
      definition: "terciles de margen ideal epsilon_opt, como en E1"
      blindness: "noise-free, ciego a resultados FakeKolkata"
    auc_failure:
      definition: "AUC/promedio del fallo sobre budgets [256,512,1024,2048,4096,8192]"
    D1_full_vs_diagonal:
      definition: "tasa de flips del selector full-Sigma vs diagonal"
    DA_selects_Raw_REM:
      definition: "frecuencia con que DA elige Raw+REM"
```

Ningun secundario puede reemplazar al primario. En particular, un estrato favorable no se usa como
headline si el primario pooled no confirma.

---

## 6. Criterio de decision

```yaml
decision_rule:
  confirmed: >
    Reduccion pooled a B*=512 significativa por McNemar una cola con alpha=0.05.
  null: >
    No significativa. Se reporta como negativo honesto: even under a calibrated real-device
    noise model, decision-aware selection shows no significant decision benefit in this
    menu/budget regime.
  practical_threshold: 0.15
  reporting: "report-what-comes"
```

Reglas de disciplina:

- prohibido tunear o reelegir instancias despues de ver datos;
- prohibido reelegir budgets despues de ver datos;
- prohibido redefinir in-band bajo Kolkata despues de ver datos;
- prohibido titular con un estrato favorable;
- prohibido cambiar menu, backend o criterios tras ver resultados.

Si el primario no es significativo, el resultado es null acotado al backend/menu/budget regime. Si
el efecto es significativo pero menor que 0.15, se reporta como significativo estadisticamente pero
por debajo del umbral practico.

---

## 7. Saturacion e inconclusion

El framing obligatorio es:

> calibrated device-noise stress test, NOT hardware evidence.

Si el regimen satura, por ejemplo `Raw` falla aproximadamente 100% en gran parte del pool, el
resultado se registra como inconcluso por regimen demasiado duro. No se retunea el mapping, el
backend, los budgets, las instancias ni el menu para rescatar senial.

El null permitido es acotado:

> no signal under this backend/menu/budget regime.

No se debe escribir que "QEM no ayuda" en general.

---

## 8. Reuso e implementacion prevista

```yaml
reuse:
  derisk_runner: "experiments/derisk_fakebackend/run.py"
  rem_module: "experiments/derisk_fakebackend/rem.py"
  frozen_science_imports:
    - "src/daqem/selectors.py"
    - "src/daqem/risk.py"
    - "src/daqem/candidates.py"
  no_duplicate_science: true

required_pre_result_gates:
  ordering_gate: "debe correr y pasar por cada C-id antes de producir resultados de decision"
  determinism: "segunda corrida de una celda/budget debe reproducir exactamente"
  budget_matching: "Raw/ZNE/REM/CDR accounting reportado por budget"

output_dir: "results/derisk_fakebackend_tier1/"
outputs:
  - "tier1_result.md"
  - "tier1_result.json"
  - "per_instance_budget_table.csv"
  - "mapping_manifest.csv"
```

El runner del de-risk ya contiene ordering-gate por instancia, determinismo, budget matching y REM.
El tier-chico debe extender esa maquinaria al pool `C001`-`C048`. No se debe duplicar ni tocar la
maquinaria congelada. El ordering-gate debe correr y pasar por cada C-id antes de cualquier resultado
de decision.

---

## 9. Costo estimado

El de-risk completo de tres celdas tomo aproximadamente 244 segundos. Como estimacion operativa:

```yaml
estimated_cost:
  cells: 48
  basis: "48 instancias x (244s / 3 celdas del de-risk)"
  wall_time: "aprox. 1 hora"
```

El costo real puede variar por profundidad transpilada y memoria de Aer, pero el orden de magnitud
esperado es cercano a una hora.

---

## 10. Sellado antes de correr

Antes de ejecutar el tier-chico se debe:

1. revisar este documento;
2. sellarlo por hash;
3. commitearlo;
4. solo entonces implementar/correr el runner tier-chico.

Hasta que esos pasos ocurran, este documento es la fuente de verdad de diseno y no se deben mirar
resultados de decision del tier-chico.

---

## 11. Estado

```yaml
status: "PRE-REGISTRO PARA REVISION"
executed: false
runner_created: false
results_inspected: false
freeze_52_target: "sha256:2AF91BE1..."
previous_derisk_sealed_hash: "sha256:6210C6F1..."
```

No se corrio el tier-chico, no se miraron resultados de decision del tier-chico, no se toco el freeze
publicado, no se toco `src/daqem/*`, y no se modifico el de-risk sellado.
