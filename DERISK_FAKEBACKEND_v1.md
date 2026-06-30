# De-risk pre-registrado — Stress test de ruido de dispositivo vía FakeBackend (arm nuevo, aditivo)

> **Documento de PRE-REGISTRO.** Se congela por hash **ANTES** de correr nada. Arm NUEVO,
> aditivo, **NO swap**: el freeze del paquete (`sha256:2AF91BE1…`, 52 archivos) y los claims
> E1/E2/E3 quedan intactos. Hermano de
> [PLAN_EXTENSION_PEC_CDR_v1.md](PLAN_EXTENSION_PEC_CDR_v1.md) §15 y de
> [DECISION_DIFERIDA_F1cB_canal_heterogeneo.md](DECISION_DIFERIDA_F1cB_canal_heterogeneo.md).
>
> **Fecha:** 2026-06-30 · **Estado:** PRE-REGISTRO (no ejecutado) · **Congelar antes de correr.**
> **Rev:** incorpora ajustes de revisión (criterio de señal robusto, REM en el menú, framing acotado).

---

## 0. Una línea

¿El ruido de un **dispositivo IBM real** (vía FakeBackend, calibración real, con errores **coherentes +
readout heterogéneo** que ningún de-risk previo modeló) **cambia la decisión** — i.e., hace que mitigar
ayude / que el DA-selector elija ≠Raw y le gane al MSE-selector? Gate barato para decidir si invertir en
un tier-chico, **con endpoints pre-especificados** y **reportando lo que salga**.

**Es un stress test de fake-backend calibrado, NO evidencia de hardware.**

---

## 1. Motivación y por qué es un arm NUEVO (rationale nuevo)

- **El trigger viejo NO se cumple.** La decisión-diferida (§4) condicionaba el path heterogéneo a
  (a) E2 fuerte **y** (b) empuje PRXQ. **E2 no salió fuerte; PRXQ está descartado** (venue = Quantum).
- **Rationale NUEVO, consciente:** credibilidad para Quantum ("no es sólo simulación") + testear el
  ingrediente que los de-risks previos NO modelaron (**coherentes + readout heterogéneo**). Dirección que
  la decisión-diferida señala (§3.2: el valor del sparse-PL es ruido de **dispositivo real**).
- **Expectativa honesta (pre-aceptada):** el plan es pesimista (§3.1) y el het-PEC lo confirmó (ρ<ρ_c).
  ~60–70% confirma el negativo (refuerza credibilidad); ~25–35% cuadro más rico vía coherentes/readout;
  ~10–15% headline. El de-risk lo decide con datos, gastando poco.

---

## 2. Anclaje al PAP (consistencia)

| Elemento | Ancla |
|---|---|
| Arm nuevo pre-registrado, aditivo, no swap | PLAN_EXTENSION §0,§7; firewall PAP |
| Pregunta = frontera de régimen "¿dónde gana DA?" (aquí EMPÍRICA, no predicha) | PAP §16.1.1 |
| Selectores DA/MSE, GRI, comparación pareada, terciles | PAP §9.4 (inalterados) |
| Budget matching (REM/ZNE/CDR cargan su costo) | PAP §4.4 ledger |
| Endpoints/umbrales Claim 1/2/3 | **NO se mueven** |
| Robustez/hardware fuera del primario | PAP §14 (R), §15 (H) — arm de robustez aditivo |
| RNG determinista | PAP §18 (PCG64DXSM, root_seed 260616) |

**Diferencia con het-PEC (§15):** aquel reusó A3 **analíticamente** con C_dev **conocido**. Acá el C_dev
del FakeBackend NO es sparse-PL/depolarizing limpio (coherentes + crosstalk) → **NO se usa el arm de
pullback**; se mide la decisión **directamente** (empírico). Consistente con el caveat ya en el paper.

---

## 3. SCOPE

**SÍ:** correr el menú a través del ruido FakeKolkataV2 y medir, por celda/budget: GRI por método, MSE por
método, fallo de decisión empírico, elección de cada selector (DA=argmin GRI, MSE=argmin MSE), y el
diagnóstico full-Σ vs diagonal.

**NO:** pullback (C_dev no conocido en dispositivo) · PEC (caracterización fuera de alcance) · reclamar
"corre en hardware" (FakeBackend = snapshot de calibración, **sigue siendo simulación**) · mover endpoints
o el freeze.

---

## 4. Diseño PRE-REGISTRADO (congelar todos estos campos antes de correr)

### 4.1 Backend
```yaml
backend_frozen: FakeKolkataV2          # 27q Falcon; confirmado disponible en el entorno
backend_confirmed_2026_06_30:
  num_qubits: 27
  basis_gates: [cx, delay, id, measure, reset, rz, sx, x]
  noise_model_from_backend: ok
selection_rationale: >
  Elegido por motivo EXTERNO al resultado: dispositivo usado por van den Berg 2023 (el paper de PEC
  sparse-PL que citamos), 27q Falcon, ruido realista. NO elegido por performance del selector.
  Se escribe como "calibrated fake-backend stress test, not hardware evidence".
noise_source: "NoiseModel.from_backend(FakeKolkataV2())"   # Aer local
```

### 4.2 Celdas e instancias — 3 celdas in-band, reportar TODAS
```yaml
cells:
  primary:   P004     # primaria PRE-ESPECIFICADA por el pilot (la más débil en uniforme: protege)
  secondary: [P001, P002]   # in-band; reportadas como heterogeneidad, NO como reemplazo del primario
selection_basis: >
  Las celdas se eligen por el pilot UNIFORME pre-especificado (P004 primaria por la regla de máxima
  distancia a los bordes de la banda; P001/P002 in-band). Las reducciones uniformes
  (P004=0.037, P001=0.242, P002=0.411) SOLO MOTIVAN la selección de celdas — NO son el resultado del
  de-risk. El de-risk RE-CORRE estas celdas bajo FakeKolkataV2 y reporta las tasas de fallo NUEVAS.
narrative_guard: >
  Reportar "Primary: P004 = <nuevo>; in-band secondary: P001 = <nuevo>, P002 = <nuevo>; full in-band
  panel shows heterogeneity." Prohibido titular con la celda fuerte como si fuera el endpoint.
n_qubits_circuit: 10
depth: 2                          # QAOA-MaxCut p=1, grid (gamma,beta) ya fijado
qubit_mapping_rule: >
  subconjunto conectado de menor error del dispositivo (readout + 2q error de la calibración),
  determinista, CIEGO a resultados de decisión.
transpile: {optimization_level: 1, seed_transpiler: 260616, basis: native}
mapping_frozen_2026_06_30:
  rule: >
    Transpile the P004 depth-2 QAOA-MaxCut reference circuit against FakeKolkataV2.target with
    optimization_level=1 and seed_transpiler=260616; no decision outcomes inspected.
  virtual_to_physical: {0: 16, 1: 22, 2: 25, 3: 19, 4: 20, 5: 24, 6: 23, 7: 14, 8: 26, 9: 13}
  physical_qubits_by_virtual_index: [16, 22, 25, 19, 20, 24, 23, 14, 26, 13]
  source_circuit:
    instance: P004
    n_qubits: 10
    qaoa_depth: 2
    circuit_depth: 18
    ops: {rzz: 30, rx: 20, h: 10, measure: 10, barrier: 1}
  transpiled_circuit:
    num_qubits: 27
    depth: 114
    size: 305
    ops: {cx: 135, rz: 110, sx: 50, measure: 10, barrier: 1}
    swap_count: 0
```

### 4.3 Menú (cerrado, mínimo) y selectores
```yaml
method_menu: [Raw, Raw+REM, Accuracy-ZNE, Decision-ZNE, CDR]   # 5 metodos; SIN PEC, SIN CDR+REM
selectors: {DA: argmin_GRI, MSE: argmin_MSE, tie_break: lexicographic}

REM:   # readout error mitigation — codigo NUEVO a implementar para este de-risk
  method: "confusion-matrix readout correction (Bravyi 2021), from backend readout assignment matrix"
  variant: "tensored/per-qubit calibration (full inversion solo si estable)"
  calibration_shots_charged_to_budget: true     # PAP budget matching: REM no es gratis (ver §B)
  rem_budget: {convention: matched_total, f_calib: 0.2, C_eval: "B - 2*calib",
    C_calib: "2*calib", note: "eval reducido para financiar calibracion, estilo ZNE"}
  determinism: "seeded; misma corrida -> misma matriz -> mismos resultados (test de determinismo)"
  new_code: "experiments/derisk_fakebackend/rem.py (módulo NUEVO, NO congelado) + ledger + tests"

menu_justification: >
  "PEC is excluded from the fake-backend study because the required quasiprobability characterization is
  outside the implemented calibration scope; readout mitigation is included because the fake-backend noise
  model contains heterogeneous readout error and REM is the directly relevant mitigation primitive."
```

### 4.4 Budgets / réplicas / seeds
```yaml
budgets: [256, 512, 1024, 2048, 4096, 8192]
B_star: 512                                  # operativo, pre-especificado
budget_band_secondary: [256, 512, 1024, 2048, 4096, 8192]   # banda PRE-FIJADA para el AUC (P004 in-band en todos)
paired_replicates: 40                        # por celda (como E1)
rng: {policy: "PAP §18", root_seed: 260616,
      derivation: "hash(instance_id, method, budget, replicate_id, stream)"}
```

### 4.5 Endpoints y criterio de señal (ROBUSTO — sin "existe budget")
```yaml
endpoints:
  primary:        "diferencia pareada de fallo (DA - MSE-selector) en B*=512, celda P004"
  secondary:      "AUC/promedio del fallo sobre budget_band_secondary, celda P004"
  heterogeneity:  "P001, P002, P004 reportadas todas (panel in-band)"
  mechanism_D1:   "flip del selector full-Σ vs diagonal bajo FakeKolkataV2 (en uniforme fue
                   selector_changed=False en 72/72). Flip => off-diagonal decision-relevante.
                   Sin flip NO mata nada (la diagonal domina en ese régimen)."
  qualitative_gate: "DA selecciona != Raw en al menos UNA celda in-band"

signal_for_go: >
  Hay señal si el endpoint PRIMARIO (B*=512, P004) muestra reducción pareada positiva Y el gate
  cualitativo se cumple (DA elige != Raw en >=1 celda in-band). El secundario (AUC) y D1 son
  evidencia de apoyo. NO se usa "existe algún budget favorable" como gate (eso seria multiplicidad
  post-hoc). Magnitud/significancia plena se testean recien en el tier-chico, propiamente potenciado.
```

### 4.6 Decisión
```yaml
go:   "señal en el endpoint primario + gate -> evaluar tier-chico (mas instancias; quiza PEC)"
stop: "sin señal -> STOP, reportar negativo ACOTADO (ver §6)"
output_dir: "results/derisk_fakebackend/"
artifacts: [derisk_result.md, derisk_result.json, per_cell_budget_table.csv]
```

---

## 5. Disciplina anti-p-hacking

1. Todo §4 se congela por hash **antes de correr** (backend, celdas, mapping, menú, B*, budget band,
   endpoints, criterio, STOP). Mapping de qubits por **calibración**, ciego a decisión.
2. **Un solo backend, celdas pre-fijadas.** Prohibido probar varios FakeBackends/celdas y quedarse con
   el que da señal. Prohibido cambiar B*/banda/criterio tras ver datos.
3. **Reportar lo que salga.** Sin señal → §6. Si satura (Raw ~100% por SWAP-overhead) → "régimen
   demasiado duro en este dispositivo, inconcluso", NO se re-tunea.
4. **No PEC, no pullback** (scope §3). REM se compara con presupuesto **matched** (su calibración carga al
   ledger).
5. **Aditivo:** no toca freeze 2AF91BE1 ni E1/E2/E3.

Test mental: ¿congelo backend+celdas+endpoints antes de mirar y reporto lo que salga? Sí → limpio.

---

## 6. STOP / null acotado (framing obligatorio)

> "A null result is not a failure of the theory; it indicates that under the tested fake-backend
> (FakeKolkataV2), budget band, and method menu, decision-aware selection does not produce a practical
> improvement beyond the implemented baselines."

NO escribir "QEM no ayuda" en general. Escribir **"no signal under this backend/menu/budget regime."**

---

## 7. Costo / riesgo honesto

- **Dev:** REM es código NUEVO (matriz de confusión + ledger + determinismo + verify). Modesto pero real
  → sube el de-risk de "horas, puro reuso" a "**dev modesto de REM + horas de corrida**". Aun así << tier-chico.
- **Cómputo:** 3 celdas × 5 métodos × 6 budgets × 40 réplicas, density-matrix ~10–12q con NoiseModel del
  backend. Orden **horas**.
- **Riesgo técnico (medio):** la transpilación a la topología real añade SWAPs → puede **saturar** la
  decisión → inconcluso (resultado registrado). Mitigación: mapping por qubits/aristas de menor error.
- **Riesgo "decepción" (medio-alto):** lo más probable es confirmar el negativo. Pre-aceptado — refuerza
  credibilidad.

---

## 8. Qué NO se reclama

- FakeBackend = snapshot de calibración IBM en Aer → **es simulación**, no hardware. Responde a "vos
  diseñaste el canal" (no: es IBM), **no** a "corre en hardware".
- No prueba pullback en dispositivo ni PEC.
- Un negativo es válido y esperado; confirma que bajo ruido que preserva el ranking —incluso de un
  dispositivo real— la mitigación no ayuda a la decisión, **acotado a este régimen**.

---

## 9. Punteros

- Reuso: `experiments/e1_static_da_selector.py` (+ runners), `src/daqem/{selectors,risk,qem_methods,candidates}.py`.
  Ruido: `NoiseModel.from_backend(FakeKolkataV2())` (qiskit_ibm_runtime.fake_provider, confirmado).
- Nuevo: REM en `src/daqem/qem_methods.py` + ledger + tests.
- Anclas: PAP §16.1.1, §9.4, §4.4, §18; PLAN_EXTENSION §15; DECISION_DIFERIDA_F1cB §3.2/§5.
- Freeze a respetar: `sha256:2AF91BE182897D9885C1F09816B3342BB64EB499B15B1212CB4ACD6D110E4026` (52).
- Salida nueva: `results/derisk_fakebackend/`.
- Cita de respaldo: van den Berg 2023 (Kolkata); Bravyi 2021 (REM) — ambas ya en la bibliografía.

---

## 10. Estado

PRE-REGISTRO (rev) listo para tu lectura final. **Con tu OK:** (a) el agente confirma `backend_frozen` +
mapping por calibración (ciego) e **implementa REM** (con su test/ledger); (b) **congelamos por hash**;
(c) se corre; (d) reviso read-only contra fuente y reportamos lo que salga.
