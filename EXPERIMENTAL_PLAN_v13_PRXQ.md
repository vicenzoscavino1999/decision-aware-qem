# Plan experimental — Decision-Aware Quantum Error Mitigation

## PAP v13 — executable 9.5-track plan with projected flip tolerance, Cdev learning gates, and falsifiable hardware ordering

### Título tentativo recomendado
**Decision-Aware Quantum Error Mitigation: Predicting Quantum Shot Cost from the Decision Gap Kernel**

Título fuerte condicionado, solo si hardware-Σ micro-cell valida cuantitativamente el pullback en dispositivo:

**Decision-Aware Quantum Error Mitigation: Device-Level Noise Predicts Quantum Shot Cost in Downstream Decisions**

---

# 0. Nota de alcance

Este documento es un **plan experimental / pre-analysis plan (PAP)**.  
No es el texto final del manuscrito ni afirma resultados ya obtenidos.

Su función es fijar:

- los claims primarios;
- los endpoints;
- la comparación principal;
- el contrato de budget;
- el firewall anti-circularidad;
- el árbol de calibración GRI;
- los ablations;
- la matriz mínima de robustez;
- el rol exacto del hardware;
- los criterios de éxito, muerte y degradación de claims;
- el diseño confirmatorio exacto;
- el power gate mínimo;
- las definiciones operacionales de failure/success;
- la política de degradación si GRI o hardware salen parciales;
- el Gate 0 full-vs-diagonal como filtro de mecanismo antes del pullback;
- el Gate 1/A3 de validación pullback antes del eje de escala;
- la regla pre-registrada para elegir Claim 3A vs 3B;
- el lenguaje permitido para hardware según número de budgets ejecutados;
- el gate de ejecutabilidad por shots/wall-hours antes de perseguir PRXQ;
- la micro-celda hardware-Σ como requisito para usar headline device-level fuerte;
- la conversión de A3 desde pass/fail arbitrario hacia frontera de tolerancia decisional;
- el brazo \(C_{\mathrm{dev}}^{true}\) vs \(C_{\mathrm{dev}}^{learned}\);
- el mapa de régimen donde DA-QEM debe ganar por geometría de gaps/correlación;
- la regla editorial de dos claims en texto principal y todo lo demás subordinado.

El manuscrito final podrá resumir este PAP, pero no debe copiarlo completo.

---

# 0.1 Fases de ejecución para decidir track 8.5 / 9 / 9.5

El PAP no asume que PRX Quantum está disponible por diseño. Primero se ejecutan gates que pueden cerrar el track PRXQ por logística o por mecanismo.

## Fase 0 — Gate de ejecutabilidad

Antes de ampliar teoría, escala o hardware, se llena una tabla de cómputo con shots, wall-hours, backend y riesgo por bloque.

Dos condiciones deben cerrar:

1. E1/E2/E3 deben ser corribles con la potencia requerida:
   - E1: al menos `1500` decisiones pareadas efectivas;
   - E2: al menos `1200` trayectorias dinámicas efectivas;
   - E3: estimación de pullback con error de \(\widehat\Sigma\) suficientemente pequeño para evaluar la frontera de volteo.
2. La micro-celda hardware-Σ debe ser agendable en IBM con créditos, límites de cola y backend disponibles.

Si la tabla no cierra, el track PRXQ se detiene y el paper se prepara como Quantum / QEM-methods fuerte.

```yaml
phase0_executability_gate:
  must_run_before_any_scaling_or_hardware_expansion: true
  required_primary_power:
    E1_paired_decisions_min: 1500
    E2_dynamic_trajectories_min: 1200
    E3_pullback_precision: must_resolve_decision_flip_tolerance
  required_noise_learning:
    sparse_PL_learning_budget_declared: true
    sparse_PL_learning_shots_included_in_ledger: true
  required_hardware:
    hardware_sigma_microcell_schedulable: true
    hardware_three_budget_ordering_schedulable_for_9plus: true
  if_fail:
    PRXQ_track_allowed: false
    recommended_track: Quantum_or_QEM_methods
    target_score_ceiling: approximately_8_5
  if_pass:
    PRXQ_track_allowed: conditional_on_phase1_mechanism
```

Tabla obligatoria:

| Bloque | Unidad primaria | N mínimo | Shots estimados | Wall-hours | Backend / recurso | Riesgo | Decisión |
|---|---:|---:|---:|---:|---|---|---|
| E1 static paired decisions | decisiones pareadas | 1500 | TBD | TBD | sim/Aer | medio | go/no-go |
| E2 dynamic trajectories | trayectorias | 1200 | TBD | TBD | sim/Aer | alto | go/no-go |
| E3 pullback frontier | celdas \((m,B)\) | TBD | TBD | TBD | sim/Aer | medio | go/no-go |
| Sparse-PL noise learning | configuraciones de caracterización | TBD | TBD | TBD | sim/Aer + IBM if hardware-Σ | alto | go/no-go |
| Hardware-Σ micro-cell | 2–3 gaps activos | TBD | TBD | TBD | IBM backend | alto | go/no-go |
| Hardware 3-budget ordering | below/near/above | TBD | TBD | TBD | IBM backend | alto | go/no-go |
| Scaling 4/6/8 | trend only | TBD | TBD | TBD | sim/Aer | medio/alto | go/no-go |

Regla: si la tabla no cierra para E1/E2/E3 y hardware-Σ, no se invierte en C1 escala como soporte PRXQ.

## Fase 1 — Piloto de interpretabilidad

Orden:

1. Gate 0 full-vs-diagonal en pilot held-out.
2. Si Gate 0 falla, track Quantum: no claim físico de covarianza.
3. Si Gate 0 pasa, correr A3 con:
   - brazo \(C_{\mathrm{dev}}^{true}\);
   - brazo \(C_{\mathrm{dev}}^{learned}\);
   - diagnóstico de gaussianidad condicionado a \(C_{\mathrm{dev}}^{true}\);
   - auditoría finito-muestral de \(\widehat\Sigma\);
   - frontera de tolerancia de volteo del ranking de riesgo, derivada antes de ver \(\widehat\Sigma\).

## Fase 2 — Decidir techo del paper

| Resultado del piloto | Track recomendado | Headline permitido |
|---|---|---|
| Fase 0 no cierra | Quantum / QEM methods | no device-level |
| Gate 0 full \(\approx\) diagonal | Quantum / QEM methods | decision-resource selection, no covariance physics |
| Gate 0 pasa y A3 llega solo a 3B | PRXQ posible / 9 base | predicts budget-dependent ordering |
| Gate 0 pasa y A3 llega a 3A con \(W^\star\le 0.5\) | PRXQ fuerte / 9+ | predicts budget switch |
| A3 3A + hardware-Σ + hardware ordering potente + frontera de régimen a priori | PRXQ 9.5 posible | device-level noise predicts shot-cost regime |

Plan base: construir el manuscrito para sobrevivir con 3B. 3A es upside, no supuesto.

## Fase 3 — Build mínimo de 9

Para un track PRXQ realista, el texto principal queda con dos claims:

1. El decision gap kernel predice ordering/costo de shots en decisiones downstream.
2. DA-QEM reduce shots-to-success bajo budget matched.

Claim 1 estático, generality matrix, ablations, controls y brazo \(C_{\mathrm{dev}}\) van al suplemento salvo que sean necesarios para entender el mecanismo.

## Fase 4 — Upgrade a 9.5

No se agrega un cuarto claim. Se reemplaza la tesis por una tesis única:

> El pullback del ruido mitigado al espacio de gaps decisionales predice el régimen donde la selección decisional domina estrictamente en costo de shots, y esta predicción sobrevive una prueba falsable en dispositivo.

Condiciones necesarias:

- A3 fuerte: \(W^\star\le 0.5\), idealmente \(\le 0.3\);
- frontera de régimen derivada a priori desde \(C_{\mathrm{dev}}\), no observada post-hoc;
- hardware-Σ micro-cell valida cuantitativamente \(\Sigma_m^{pred}\) vs \(\widehat\Sigma_m\);
- hardware ordering de tres budgets tiene potencia para detectar un ordering flip y no lo detecta.

---

# 1. Core scope and three primary claims

La versión PRXQ debe ser simple. El paper no debe vender diez contribuciones centrales. Debe vender tres.

---

## Claim principal 1 — DA-QEM reduces downstream decision failure

Comparación primaria estática:

\[
R_{\mathrm{DA}}^{dec}(B)
<
R_{\mathrm{MSE}}^{dec}(B).
\]

Interpretación:

> Seleccionar/ajustar QEM usando riesgo decisional reduce fallos downstream frente a seleccionar/ajustar QEM usando MSE, bajo budget matched.

---

## Claim principal 2 — DA-QEM reduces shots-to-success in a dynamic task

Endpoint principal dinámico:

\[
B_{\mathrm{DA}}(0.8)
<
B_{\mathrm{MSE}}(0.8),
\]

donde:

\[
B_m(P_{\mathrm{target}})
=
\min\{B:\ P_m(\mathrm{success};B)\ge P_{\mathrm{target}}\},
\quad
P_{\mathrm{target}}=0.8.
\]

Interpretación:

> DA-QEM no solo mejora una métrica; reduce el costo de muestreo cuántico requerido para tomar decisiones confiables.

Este es el claim más importante para PRXQ.

---

## Claim principal 3 — Device-channel pullback predicts the decision covariance and the budget switch

Este claim es el **gate físico binario** del plan, condicionado al Gate 0 full-vs-diagonal: primero debe demostrarse que la covarianza completa cambia el riesgo, el selector o la predicción de cruce. Si el full kernel no aporta frente al diagonal, no se permite vender predicción física de covarianza desde el canal.

Desde caracterización del dispositivo/noise model en pilot se predice:

\[
\Sigma_m^{pred}
=
L M_m C_{\mathrm{dev}} M_m^\top L^\top.
\]

En datos held-out se estima:

\[
\widehat\Sigma_m.
\]

La hipótesis falsable central es:

\[
\Sigma_m^{pred}\approx \widehat\Sigma_m
\quad\Rightarrow\quad
B^\star_{pred}\ \text{and ordering across budgets are predictable from device-level noise structure.}
\]

Interpretación:

> La estructura de ruido del dispositivo, propagada por QEM y proyectada por el contraste decisional, predice cuántos shots requiere una decisión confiable y cuándo conviene cambiar la estrategia de mitigación.

Consecuencia pre-registrada:

- si este pullback valida, el track PRXQ es realista;
- si falla, el paper se degrada a un claim metodológico fuerte sobre DA-QEM, más apropiado para Quantum u otro venue fuerte de QEM/metodología;
- no se permite usar lenguaje de “device-level prediction” si \(\Sigma_m^{pred}\) no predice \(\widehat\Sigma_m\) en pilot held-out.

---

# 2. Threat model / reviewer objections table

Esta tabla se coloca al inicio para mostrar que el PAP fue escrito contra las objeciones probables del referee.

| Objeción del reviewer | Riesgo | Defensa pre-registrada |
|---|---|---|
| DA-QEM vio el test set | Circularidad / overfitting | pilot/confirmatory firewall, split disjunto, hash pre-confirmatorio |
| DA gana por más presupuesto efectivo | Comparación injusta | matched-budget accounting contract \(C_{\mathrm{DA}}(B)\le C_{\mathrm{MSE}}(B)\) |
| DA gana porque el baseline MSE es débil | Strawman | MSE selector fuerte con el mismo menú de métodos y mismo budget |
| GRI es una aproximación débil | Modelo mal calibrado | GRI calibration decision tree + empirical risk fallback |
| El cruce \(B^\star\) es cherry-picked | Data snooping | \(B^\star\) predicho desde pilot held-out antes del hash |
| El efecto solo aparece en una instancia toy | Falta de generalidad | matriz mínima 2 problems × 2 noise families × 2 depths |
| El dynamic loop es demasiado artificial | Falta de relevancia | Batch Candidate Optimizer modela decisión de selección de candidato bajo finite shots |
| Hardware pequeño/inconcluso | Overclaim | hardware solo como Level 3 stress test, sin claim cuantitativo de constantes |
| MSE pierde porque se comparó contra DA-ZNE tuneado | Confusión selector vs método | ablations: selector effect, method-tuning effect, full-vs-diagonal kernel |
| El full kernel no aporta | Métrica alternativa arbitraria | full kernel vs diagonal kernel vs shuffled \(L\) |
| DA funciona solo por empirical tuning | No hay teoría predictiva | A3 pullback gate: \(\Sigma_m^{pred}=L M_m C_{dev}M_m^\top L^\top\) debe predecir \(\widehat\Sigma_m\) desde caracterización del dispositivo antes de cualquier claim físico |
| Los resultados son significativos pero pequeños | Falta de importancia práctica | mínimos prácticos: failure reduction, shot savings, bounded \(B^\star\) window |
| GRI falla en PEC/ZNE con colas pesadas | Gaussianidad inválida | auditoría de gaussianidad + empirical/bootstrap fallback |
| CDR/PEC hacen el main inestable | Demasiadas fuentes de fallo | CDR/PEC secundarios; núcleo sobre Raw/ZNE/selectors |
| Drift de hardware afecta comparación | Ruido no estacionario | ejecución interleaved + cluster bootstrap por epoch |
| Esto es ranking-and-selection con etiqueta cuántica | Novedad física insuficiente | el claim físico solo se permite si el canal caracterizado predice la covarianza decisional y el costo de shots mediante el pullback \(L M C_{\mathrm{dev}}M^\top L^\top\) |
| Predecir covarianza multi-qubit desde caracterización es intratable | Claim 3 físico inviable | predicción cuantitativa restringida a escala núcleo en simulación, donde \(\widehat\Sigma\) es estimable; caracterización vía sparse Pauli–Lindblad aprendido, no predicción desde calibración cruda; hardware no reclama validación de \(\Sigma\) |
| La tabla de cómputo no cierra | PRXQ inviable por logística | Fase 0 exige shots, wall-hours y backend disponibles antes de escala o hardware; si falla, track Quantum/QEM-methods |
| \(C_{\mathrm{dev}}\) se aprende mal | A3 falla por estimación de ruido, no por teoría | brazo \(C_{\mathrm{dev}}^{true}\) vs \(C_{\mathrm{dev}}^{learned}\), recuperación de generadores Pauli–Lindblad y comparación \(\Sigma^{pred,true}\) vs \(\Sigma^{pred,learned}\) |
| Hardware no tenía potencia para falsar ordering | evidencia de hardware casi nula | tres budgets pre-registrados y minimum-detectable-ordering-flip; si no hay potencia, hardware queda stress test o consistencia local |
| DA gana solo en regímenes de correlación altos elegidos post-hoc | régimen contrived | frontera de régimen derivada a priori desde gap geometry y \(C_{\mathrm{dev}}\), luego confirmada; si es post-hoc, queda descriptivo |

---

# 3. Primary estimands and practical-effect thresholds

Para PRXQ no basta significancia estadística. Cada claim primario debe tener un mínimo de efecto práctico.

---

## 3.1 Claim 1 estimand

\[
\Delta R_{\mathrm{static}}
=
R_{\mathrm{DA}}^{dec}(B^\star)
-
R_{\mathrm{MSE}}^{dec}(B^\star).
\]

### Éxito estadístico

\[
\Delta R_{\mathrm{static}}<0
\]

con test unilateral \(\alpha=0.05\) o CI bootstrap 95% completamente bajo 0.

### Éxito práctico

Reducción relativa mínima:

\[
\frac{
R_{\mathrm{MSE}}^{dec}-R_{\mathrm{DA}}^{dec}
}{
R_{\mathrm{MSE}}^{dec}+\epsilon_0
}
\ge
0.15.
\]

Valor objetivo recomendado:

```yaml
claim1_min_relative_failure_reduction: 0.15
preferred_target: 0.20
```

---

## 3.2 Claim 2 estimand

\[
\Delta B_{0.8}
=
B_{\mathrm{DA}}(0.8)
-
B_{\mathrm{MSE}}(0.8).
\]

### Éxito estadístico

\[
\Delta B_{0.8}<0
\]

con CI bootstrap cuyo extremo superior sea menor que 0.

### Éxito práctico

Shot saving mínimo:

\[
\mathrm{Savings}
=
1-
\frac{
B_{\mathrm{DA}}(0.8)
}{
B_{\mathrm{MSE}}(0.8)+\epsilon_0
}
\ge
0.20.
\]

Valor objetivo recomendado:

```yaml
claim2_min_shot_savings: 0.20
preferred_target: 0.30
```

Este es el endpoint PRXQ más fuerte.

---

## 3.3 Claim 3 estimands and hard headline rule

Claim 3 tiene dos niveles inferenciales y una consecuencia directa sobre el headline.

### 3.3.1 Pullback validation estimand as a decision-flip frontier

A3 no se evalúa con un umbral Frobenius elegido a dedo. La métrica primaria es si el error de predicción de covarianza es pequeño en la **dirección que puede voltear el ranking de riesgo**, no si toda la matriz es cercana en una norma isotrópica.

Primero se define el error de pullback por método y budget:

\[
E_m(B)
=
\widehat\Sigma_m(B)-\Sigma_m^{pred}(B).
\]

También se reportan métricas globales de diagnóstico:

```yaml
pullback_distance_metrics:
  diagnostic_primary: projected_ranking_error
  diagnostic_secondary:
    - relative_frobenius_error_on_LKLT
    - active_gap_correlation_error
    - eigenvalue_spectrum_error
    - risk_prediction_error
```

Pero el gate principal es decisional. Para cada par de métodos \((m,n)\), definir la diferencia de riesgo predicha:

\[
\Delta_{mn}^{pred}(B)
=
R_m\!\left(\Sigma_m^{pred}(B)\right)
-
R_n\!\left(\Sigma_n^{pred}(B)\right).
\]

El ranking entre \(m\) y \(n\) se voltea si cambia el signo de \(\Delta_{mn}(B)\). Por eso se calcula, **antes de mirar** \(\widehat\Sigma\), la sensibilidad local del ranking de riesgo frente a perturbaciones de covarianza:

\[
G_{mn}^{(m)}(B)
=
\nabla_{\Sigma_m}
\left[
R_m(\Sigma_m)-R_n(\Sigma_n)
\right]
\Big|_{(\Sigma_m,\Sigma_n)=(\Sigma_m^{pred},\Sigma_n^{pred})},
\]

\[
G_{mn}^{(n)}(B)
=
\nabla_{\Sigma_n}
\left[
R_m(\Sigma_m)-R_n(\Sigma_n)
\right]
\Big|_{(\Sigma_m,\Sigma_n)=(\Sigma_m^{pred},\Sigma_n^{pred})}.
\]

Los gradientes se estiman numéricamente con diferencias centrales sobre la parte simétrica activa de \(\Sigma\), preservando PSD mediante jitter mínimo si una perturbación sale del cono PSD:

```yaml
risk_gradient_estimation:
  method: central_finite_difference
  perturbation_basis: symmetric_active_gap_basis
  perturbation_scale_rule: max(1e-4 * median_diag_Sigma, 1e-8)
  psd_handling: nearest_psd_or_minimal_diagonal_jitter
  freeze_before_Sigma_hat: true
```

El error que importa para el ranking no es \(\|E_m\|_F\) completo, sino su proyección sobre la dirección sensible:

\[
\delta_{mn}^{rank}(B)
=
\left|
\left\langle G_{mn}^{(m)}(B),E_m(B)\right\rangle_F
+
\left\langle G_{mn}^{(n)}(B),E_n(B)\right\rangle_F
\right|.
\]

Se define el margen de ranking:

\[
M_{mn}^{rank}(B)
=
|\Delta_{mn}^{pred}(B)|.
\]

El gate primario de A3 en el par \((m,n)\) es:

\[
\delta_{mn}^{rank}(B)
<
\rho_{flip}\,M_{mn}^{rank}(B),
\qquad
0<\rho_{flip}<1.
\]

Regla recomendada:

```yaml
A3_decision_flip_gate:
  primary_error: projected_ranking_error
  rho_flip: 0.50
  active_pair_rule: pairs_whose_predicted_risk_margin_can_affect_selector_or_Bstar
  ambiguous_pair_if_predicted_margin_below: pilot_MDE_absolute_risk
  ambiguous_pair_action: no_3A_claim_for_that_budget_pair
```

Equivalente, la tolerancia de volteo proyectada queda:

\[
\tau_{flip,mn}^{proj}(B)
=
\rho_{flip}\,|\Delta_{mn}^{pred}(B)|.
\]

A3 pasa en un budget solo si todos los pares activos cumplen:

\[
\delta_{mn}^{rank}(B)<\tau_{flip,mn}^{proj}(B).
\]

La norma Frobenius queda como proxy conservador secundario, no como gate primario:

\[
\tau_{flip,mn}^{F}(B)
=
\frac{
\rho_{flip}|\Delta_{mn}^{pred}(B)|
}{
\|G_{mn}^{(m)}(B)\|_F+
\|G_{mn}^{(n)}(B)\|_F+
\epsilon_0
}.
\]

Si además se cumple:

\[
\|E_m(B)\|_F+\|E_n(B)\|_F
<
\tau_{flip,mn}^{F}(B),
\]

entonces el resultado se etiqueta como `Frobenius-conservative pass`. Si falla el proxy Frobenius pero pasa el error proyectado, el resultado se etiqueta como `directionally-sensitive pass` y se explica que el error matricial cae en direcciones decisionalmente inofensivas.

Interpretación:

> El pullback no necesita predecir cada entrada de \(\Sigma\) perfectamente; necesita predecir la componente de \(\Sigma\) que puede cambiar la decisión QEM.

Se reporta un mapa de frontera, no solo un pass/fail:

```yaml
A3_frontier_map:
  x_axes:
    - budget_B
    - gap_correlation_strength
    - active_gap_dimension
    - noise_correlation_strength
  y_axes:
    - projected_error_over_flip_tolerance
    - frobenius_error_over_conservative_tolerance
  pass_region: projected_error_over_flip_tolerance < 1
  ambiguous_region: predicted_margin_below_MDE_or_gradient_unstable
  fail_region: projected_error_over_flip_tolerance >= 1
```

El gate A3 pasa como claim físico si el error proyectado está debajo de la tolerancia de volteo en los budgets pre-registrados relevantes y el ordering de riesgos inducido por \(\Sigma_m^{pred}\) coincide con el ordering empírico.

```yaml
A3_pullback_frontier_gate:
  depends_on: Gate0_full_vs_diagonal_pass
  input: device_or_noise_characterization_from_pilot_only
  prediction: Sigma_pred = L M C_dev M^T L^T
  target: Sigma_hat on held-out pilot data
  primary_gate: projected_prediction_error_below_decision_flip_tolerance
  secondary_gate: frobenius_conservative_proxy
  must_run_after_full_vs_diagonal_gate: true
  must_run_before_scaling_axis: true
  required_diagnostics:
    - Cdev_true_vs_Cdev_learned_arm_with_pass_criteria
    - Gaussianity_conditional_on_Cdev_true
    - finite_sample_Sigma_hat_audit
  if_3A_pass:
    physical_claim_allowed: true
    PRXQ_track_allowed: true
    allowed_language: predicts_budget_switch
  if_only_3B_pass:
    physical_claim_allowed: true
    PRXQ_track_allowed: possible
    allowed_language: predicts_budget_dependent_ordering
  if_fail:
    physical_claim_allowed: false
    PRXQ_track_not_primary: true
    recommended_venue_track: Quantum_or_strong_QEM_methods_journal
```

### 3.3.2 \(B^\star\) window estimand

\[
B^\star_{obs}
\quad \text{vs} \quad
[B^\star_{lo},B^\star_{hi}].
\]

Definir:

\[
W^\star
=
\frac{
B^\star_{hi}-B^\star_{lo}
}{
B^\star_{pred}+\epsilon_0
}.
\]

La regla no es una preferencia; decide qué claim puede ser headline:

```yaml
Bstar_window_rule:
  if W_star <= 0.5 and A3_pullback_gate == pass:
    prediction_headline: Claim_3A_strong_crossing_prediction
    allowed_language: predicts_the_budget_switch
  elif W_star > 0.5 and directional_ordering_passes and A3_pullback_gate == pass:
    prediction_headline: Claim_3B_directional_ordering
    claim3A_status: not_primary
    allowed_language: predicts_budget_dependent_ordering_not_exact_crossing
  else:
    prediction_headline: none
    claim3_status: diagnostic_only
    forbidden_language:
      - predicts_B_star
      - predicts_the_crossing
      - device_level_prediction_of_budget_switch
```

Valores guía:

```yaml
W_star_max_for_3A: 0.5
W_star_preferred_for_3A: 0.3
```

Si el pilot no soporta \(W^\star\le 0.5\), Claim 3A no puede liderar. En ese caso, el paper puede liderar con Claim 3B solo si el ordering direccional pre-registrado pasa.

---

## 3.4 Definiciones operacionales de failure, success y regret

Estas definiciones cierran la puerta a cambiar el endpoint después de ver resultados.

### Candidate set y verdad de referencia

Para una instancia confirmatoria fija se define un conjunto congelado de candidatos:

\[
\mathcal C=\{x_1,\ldots,x_K\}.
\]

La verdad de referencia se calcula con el objetivo ideal/noiseless:

\[
f_i=f(x_i),
\qquad
x^\star=\arg\min_{x_i\in\mathcal C} f_i.
\]

Para problemas de maximización se usa la convención equivalente cambiando el signo del objetivo.

---

### Static decision failure

El método o selector \(m\) produce estimaciones mitigadas:

\[
\widehat f_{m,i}(B).
\]

La decisión tomada es:

\[
\widehat x_m(B)
=
\arg\min_{x_i\in\mathcal C}\widehat f_{m,i}(B),
\]

con desempate lexicográfico por índice congelado.

El regret decisional estático es:

\[
\mathrm{Regret}_m(B)
=
f(\widehat x_m(B))-f(x^\star).
\]

El indicador primario de fallo es:

\[
I^{dec}_m(B)
=
\mathbf 1\{\mathrm{Regret}_m(B)>\epsilon_{opt}\}.
\]

Entonces:

\[
R^{dec}_m(B)=\mathbb E[I^{dec}_m(B)].
\]

La regla \(\epsilon_{opt}\) se congela desde pilot held-out usando:

```yaml
epsilon_opt_rule: ideal_landscape_quantile
epsilon_opt_quantile: 0.10
fallback_epsilon_opt: 0.01 * abs(best_ideal_objective)
```

Interpretación: no se castiga una selección casi indistinguible del óptimo ideal; se castiga elegir un candidato decisionalmente peor.

---

### Dynamic success

En el Batch Candidate Optimizer, una trayectoria dinámica tiene éxito si, al final de \(T_{max}\) rondas, el mejor punto visto cumple:

\[
\min_{t\le T_{max}} f(x_t)-f(x^\star_{grid})\le \epsilon_{opt}.
\]

El endpoint dinámico es:

\[
P_m(\mathrm{success};B)
=
\mathbb P\left[
\min_{t\le T_{max}} f(x_t)-f(x^\star_{grid})\le \epsilon_{opt}\right].
\]

El budget-to-success se estima como:

\[
B_m(0.8)=\min\{B\in\mathcal B_{primary}:\widehat P_m(\mathrm{success};B)\ge0.8\}.
\]

Si la curva empírica no es monótona por ruido Monte Carlo, se usa isotonic regression pre-registrada sobre \(\widehat P_m(\mathrm{success};B)\). La versión no suavizada se reporta en suplemento.

---

### Bad-step acceptance

Métrica secundaria:

\[
I^{badstep}_{m,t}
=
\mathbf 1\{f(x_{t+1})-f(x_t)>\epsilon_{bad}\}.
\]

Regla congelada:

```yaml
epsilon_bad_rule: 0.5 * epsilon_opt
```

No es endpoint primario, pero ayuda a explicar cómo DA-QEM reduce decisiones equivocadas durante el loop.

---

# 4. Budget matching contract

La comparación principal solo es válida si el costo está contablemente cerrado.

---

## 4.1 Costo total por método

Para cada método o selector \(m\):

\[
C_m(B)
=
C_{\mathrm{train},m}
+
C_{\mathrm{select},m}
+
C_{\mathrm{eval},m}
+
C_{\mathrm{calib},m}
+
C_{\mathrm{overhead},m}.
\]

Donde:

| Término | Significado |
|---|---|
| \(C_{\mathrm{train},m}\) | shots/circuitos usados para entrenar coefficients, CDR, selector, o allocation |
| \(C_{\mathrm{select},m}\) | costo de elegir método/hyperparameters |
| \(C_{\mathrm{eval},m}\) | shots usados en evaluación del task |
| \(C_{\mathrm{calib},m}\) | readout/noise calibration si se usa |
| \(C_{\mathrm{noiselearn},m}\) | shots/circuitos usados para aprender \(C_{\mathrm{dev}}\), sparse Pauli–Lindblad, o calibración de canal |
| \(C_{\Sigmahat,m}\) | shots/circuitos usados para estimar directamente \(\widehat\Sigma_m\) en pilot o hardware-Σ |
| \(C_{\mathrm{overhead},m}\) | overhead por ZNE branches, PEC quasiprobabilities, circuit repetitions |

---

## 4.2 Regla primaria

La comparación primaria exige:

\[
C_{\mathrm{DA}}(B)
\le
C_{\mathrm{MSE}}(B)
\]

en la celda primaria.

Si se usa igualdad exacta:

\[
C_{\mathrm{DA}}(B)
=
C_{\mathrm{MSE}}(B).
\]

Si DA tiene costo menor, el remanente se puede:

1. no usar, comparación conservadora;
2. reasignar según regla pre-registrada;
3. reportar como savings adicional.

La opción primaria debe congelarse antes del hash.

---

## 4.3 Non-amortized vs amortized cost

Se reportan dos análisis.

### Análisis primario: non-amortized

Incluye:

\[
C_{\mathrm{train}}
+
C_{\mathrm{select}}
+
C_{\mathrm{eval}}
+
C_{\mathrm{calib}}
+
C_{\mathrm{noiselearn}}
+
C_{\Sigmahat}
+
C_{\mathrm{overhead}}.
\]

Este es el análisis más duro y debe ser el primario si es viable.

### Análisis secundario: amortized

El costo de pilot/training se considera reutilizable y se reporta aparte:

\[
C^{amortized}_m(B)
=
C_{\mathrm{eval},m}
+
C_{\mathrm{overhead},m}.
\]

El claim principal no debe depender únicamente del análisis amortized.

---

## 4.4 Budget ledger obligatorio

Archivo:

```text
results/frozen/budget_ledger.csv
```

Columnas:

```csv
method,selector,task,B_nominal,C_train,C_select,C_eval,C_calib,C_noiselearn,C_Sigmahat,C_overhead,C_total,amortization_flag
```

El ledger debe existir antes del análisis confirmatorio.

### 4.4.1 Costo explícito de aprender \(C_{\mathrm{dev}}\) y estimar \(\widehat\Sigma\)

La estimación de covarianza decisional y el aprendizaje sparse Pauli–Lindblad no pueden quedar escondidos como costo amortizado si sostienen el claim físico.

Regla primaria:

```yaml
non_amortized_cost_rule_for_A3:
  C_noiselearn_charged_to_DA_if_used_for_selector_or_claim3: true
  C_Sigmahat_charged_to_A3_validation: true
  hardware_sigma_microcell_shots_reported_separately_and_in_total: true
  if_same_shots_used_for_mean_and_covariance:
    require_overlap_accounting_table: true
  if_covariance_requires_extra_repetitions:
    extra_repetitions_counted_in_C_Sigmahat: true
```

El brazo \(C_{\mathrm{dev}}^{true}\) vs \(C_{\mathrm{dev}}^{learned}\) debe declarar antes del freeze:

```yaml
sparse_PL_learning_budget:
  characterization_circuits: TBD
  shots_per_characterization_circuit: TBD
  epochs_or_repetitions: TBD
  backend_or_simulator: TBD
  included_in_phase0_executability_gate: true
  included_in_budget_ledger: true
```

El número de circuitos/shots de caracterización no es arbitrario: se elige para alcanzar los targets de recuperación del Gate C1 sobre pilot, y se declara en Fase 0 y en el ledger.

```yaml
sparse_PL_learning_protocol:
  method: sparse_Pauli_Lindblad_learning          # ref: van den Berg et al. 2023
  weight_locality_cutoff: frozen_pre_hash
  shots_rule: set_to_reach_Gate_C1_targets_on_pilot   # rel. weighted generator error <= 0.20, support F1 >= 0.90
  epochs_rule: until_C1_targets_or_budget_cap
  declared_in_phase0_and_ledger: true
```

Si este presupuesto no está declarado, A3 no puede usarse como headline predictivo.
---

## 4.5 Budget grid congelado y regla de igualdad efectiva

El grid primario recomendado queda:

```yaml
primary_budget_grid:
  - 256
  - 512
  - 1024
  - 2048
  - 4096
  - 8192
```

El pilot puede eliminar budgets solamente por inviabilidad computacional o porque todos los métodos tienen failure rate extremo:

```yaml
remove_budget_if:
  all_methods_failure_rate_below: 0.05
  all_methods_failure_rate_above: 0.95
```

La eliminación debe ocurrir antes del freeze manifest. No se puede eliminar un budget porque DA pierda.

---

### Budget efectivo por candidato

Para static selection:

\[
B_{nominal}=\text{shots por candidato antes de overhead QEM}.
\]

El costo total se reporta como \(C_m(B)\), no solo como \(B_{nominal}\).

Para dynamic loop:

\[
C^{dyn}_m(B)
=
\sum_{t=1}^{T_{max}}\sum_{k=1}^{K}C_m(B;t,k).
\]

La comparación primaria exige:

\[
C^{dyn}_{DA}(B)\le C^{dyn}_{MSE}(B).
\]

Si una rama ZNE o PEC consume más circuitos físicos, esos circuitos se cargan al ledger. No se permite reportar solo “shots lógicos” como costo primario.

---

### Regla primaria si DA usa menos costo

La opción primaria queda congelada como:

```yaml
unused_budget_policy: conservative_unused
```

Es decir: si DA consume menos costo total que MSE, el remanente no se reutiliza en el endpoint principal. La reasignación de remanente solo se reporta como análisis secundario.

## 4.6 Metodología de asignación de shots (DA allocation)

La asignación de shots del selector DA sigue una regla tipo OCBA: distribuir el presupuesto entre candidatos/escalas para maximizar la reducción de riesgo decisional por shot, ponderando hacia los gaps de la banda crítica con mayor efecto marginal sobre el exponente de decisión, bajo el mismo presupuesto total que MSE. La asignación equal-allocation es el control del ablation (§12). Valores congelados pre-hash desde pilot held-out.

```yaml
da_shot_allocation:
  method: decision_aware_OCBA_style          # ref: Wang & Zhou 2022; Wu & Zhou 2018
  objective: minimize_decision_risk_at_fixed_total_budget
  rule: allocate_proportional_to_marginal_decision_risk_reduction
  baseline_for_ablation: equal_allocation
  same_total_budget_as_MSE: true             # matched-budget contract (§4)
  frozen_pre_hash: true
  config: config/budget_allocation.yaml
```


---

# 5. Anti-circularity and Decision-Aware Training Firewall

La objeción más peligrosa:

> “DA-QEM gana porque fue entrenado para ganar la métrica decisional.”

Respuesta:

> DA-QEM no ve el examen final.

---

## 5.0 Orden de ejecución: Gate 0 antes de A3, A3 antes de escala

Antes de ejecutar el eje de escala, hardware amplio o robustez adicional, se debe decidir si el mecanismo de covarianza completa realmente importa. El pullback A3 solo tiene valor físico si el full kernel cambia el riesgo, el selector o la predicción de cruce frente al diagonal.

El orden de ejecución queda congelado:

```yaml
execution_order:
  step_minus_1: run_phase0_executability_gate_shots_wallhours_backend
  step_0: run_full_vs_diagonal_mechanism_gate_on_pilot_heldout
  step_1: if_Gate0_passes_run_A3_pullback_frontier_on_pilot_heldout
  step_2: run_Cdev_true_vs_learned_arm_Gaussianity_and_Sigma_hat_audit
  step_3: decide_venue_track_prediction_headline_and_3A_vs_3B
  step_4: freeze_confirmatory_design
  step_5: run_primary_E1_E2_E3
  step_6: run_scaling_axis_only_if_Phase0_Gate0_and_A3_support_physical_claim
  step_7: run_hardware_Sigma_microcell_if_device_level_headline_is_desired
  step_8: run_hardware_three_budget_ordering_only_if_powered
```

### Gate 0: full-vs-diagonal mechanism decision

```yaml
Gate0_full_vs_diagonal:
  if_full_kernel_improves_GRI_selector_or_Bstar_prediction_with_margin:
    covariance_mechanism_relevant: true
    run_A3_pullback_validation: true
    scaling_axis_priority_if_A3_passes: high
  elif_full_kernel_approximately_equals_diagonal:
    covariance_mechanism_relevant: false
    run_A3_pullback_validation: optional_diagnostic_only
    physical_covariance_prediction_claim_allowed: false
    scaling_axis_priority: low
    allowed_main_message: QEM should be selected by quantum decision-resource cost, not estimator MSE.
```

### Decisión binaria de venue/ambición

```yaml
A3_decision_gate:
  precondition: Gate0_full_vs_diagonal_pass
  if_Sigma_pred_predicts_Sigma_hat:
    venue_track: PRX_Quantum_realistic
    main_message: Device-level noise structure predicts when MSE-selected QEM wastes quantum shots in downstream decisions.
    scaling_axis_priority: high
    claim3A_or_3B_allowed: according_to_W_star_rule
  else:
    venue_track: Quantum_or_strong_QEM_methods_journal
    main_message: QEM should be selected by quantum decision-resource cost, not estimator MSE.
    scaling_axis_priority: low
    claim3A_or_3B_allowed: false
```

No se permite reubicar Gate 0 ni A3 como narrativa posterior. Gate 0 decide si vale la pena hablar de covarianza completa; A3 decide si esa covarianza puede reclamarse como predicción física desde estructura de ruido.

### Fase 0 dentro del firewall

La fase de ejecutabilidad no mira resultados científicos. Solo verifica si el experimento es posible bajo recursos reales.

```yaml
phase0_before_science:
  allowed_inputs:
    - estimated_circuit_counts
    - estimated_shots
    - backend_queue_constraints
    - simulator_wallhours
    - IBM_credit_or_runtime_limits
  forbidden_inputs:
    - pilot_effect_sizes_not_yet_frozen
    - confirmatory_outcomes
  decision:
    if_not_executable: stop_PRXQ_track_before_extra_compute
```

La decisión de bajar a Quantum por logística no es falla científica. Es selección correcta de venue.

### A3 como frontera caracterizada

A3 no produce solo una etiqueta `pass/fail`. Produce un mapa de dónde el pullback predice y dónde se rompe. El claim PRXQ fuerte solo se permite si la región primaria cae dentro de la zona `error_over_tolerance < 1` y si \(W^\star\le0.5\) para Claim 3A.


## 5.1 Split estricto

Cada instancia tiene split:

```csv
instance_id,split,role
G001,pilot,train_DA_QEM
G002,pilot,choose_B_star
G101,confirmatory,primary_static
G102,confirmatory,primary_dynamic
```

Reglas:

- ninguna instancia `pilot` entra como confirmatoria;
- ninguna instancia confirmatoria entrena DA-QEM;
- ninguna instancia confirmatoria modifica \(B^\star\), coefficients, allocation, \(L\), \(\epsilon\), \(T\), shrinkage o thresholds.

---

## 5.2 Congelado pre-hash

Antes de la ejecución confirmatoria quedan congelados:

| Elemento | Archivo |
|---|---|
| DA selector rule | `config/qem_selectors.yaml` |
| MSE selector rule | `config/qem_selectors.yaml` |
| DA-ZNE coefficients | `config/decision_aware_qem.yaml` |
| shot allocation | `config/budget_allocation.yaml` |
| \(B^\star\) | `results/pilot/predicted_crossing_report.md` |\n| A3 pullback validation | `results/pilot/pullback_validation_report.md` |\n| \(\Sigma_m^{pred}\) construction | `analysis/pullback_prediction_spec.yaml` |
| \(T_{\mathrm{final}}\) | `results/pilot/pilot_power_report.md` |
| critical band | `results/frozen/critical_bands.csv` |
| \(L\) | `results/frozen/contrast_matrices.npz` |
| dynamic task | `config/dynamic_task.yaml` |
| GRI calibration threshold | `analysis/gri_calibration_spec.yaml` |
| estimator/shrinkage | `analysis/estimator_spec.yaml` |
| multiplicity plan | `analysis/multiplicity_plan.yaml` |
| budget ledger | `results/frozen/budget_ledger.csv` |
| analysis code | `freeze_manifest.json` |

Si falta uno, estado:

```text
NO_FREEZE
```

---

## 5.3 Diseño confirmatorio exacto recomendado

Esta tabla convierte el PAP en un diseño ejecutable. Los números pueden reducirse solo si el pilot demuestra que la potencia sigue siendo suficiente.

| Bloque | Rol | Problema | Noise | Depth | Instancias confirmatorias | Replicates/trajectories | Budgets | Endpoint |
|---|---|---|---|---:|---:|---:|---|---|
| E1-primary | Static claim | QAOA-MaxCut | Pauli/depolarizing | 2 | 48 | 40 shot replicates | 256–8192 | \(R^{dec}(B^\star)\) |
| E2-primary | Dynamic claim | QAOA-MaxCut | Pauli/depolarizing | 2 | 32 | 50 trajectories | 256–8192 | \(B(0.8)\) |
| E3-primary | Crossing | QAOA-MaxCut | Pauli/depolarizing | 2 | same as E1 | same as E1 | grid + near \(B^\star\) | \(B^\star_{obs}\) |
| R1 | Robustness | QAOA-MaxCut | amplitude damping + dephasing | 2 | 16 | 30 | 512–4096 | direction/order |
| R2 | Robustness | VQE Ising/Heisenberg small | Pauli/depolarizing | 1–2 | 16 | 30 | 512–4096 | direction/order |
| R3 | Robustness | portfolio/cardinality QAOA or second MaxCut family | Pauli/depolarizing | 1–2 | 16 | 30 | 512–4096 | direction/order |
| H1 | Hardware Level 3 | 3–5 qubit decision task | real IBM backend | shallow | 6–10 batches | interleaved epochs | below/near/above \(B^\star\) if ordering is claimed | ordering only if 3 budgets run; otherwise crossing-point consistency only |

Primary claims 1–3 depend only on E1/E2/E3. R1–R3 defend non-toy robustness. H1 is a stress test, not a gate for the simulated claims.

---

### Default instance construction

```yaml
qaoa_maxcut_primary:
  graph_families:
    - Erdos_Renyi
    - random_regular_or_sparse_weighted
  n_qubits: 8_to_12
  qaoa_depth: 2
  candidate_set_static: frozen_local_grid_around_ideal_optimum
  static_candidates_K: 25
  dynamic_candidates_per_round: 5
  max_rounds: 20
  graph_seed_policy: hash(instance_id, graph_family, depth)
```

Depth 1 is kept as robustness/control. Depth 2 is primary because depth 1 can be too easy and may make all methods look similar.

---

## 5.4 Pilot power gate

Antes de freeze confirmatorio, el pilot debe producir un power report:

```text
results/pilot/pilot_power_report.md
```

El power gate mínimo es:

```yaml
static_primary_min_paired_decisions: 1500
dynamic_primary_min_paired_trajectories: 1200
baseline_failure_rate_acceptable_range: [0.15, 0.70]
minimum_detectable_relative_failure_reduction: 0.15
minimum_detectable_shot_savings: 0.20
bootstrap_repetitions: 10000
alpha_primary: 0.05
```

Si el failure rate de MSE en la celda primaria cae fuera de \([0.15,0.70]\), la celda no tiene sensibilidad suficiente. En ese caso se ajusta antes del freeze una sola de estas variables, en este orden:

1. \(B^\star\) dentro del grid primario;
2. \(\epsilon_{opt}\) usando la regla de quantile ya definida;
3. profundidad primaria;
4. ruido primario.

No se permite ajustar la celda primaria mirando el desempeño confirmatorio.

---

### Diseño pareado

Siempre que sea posible, DA y MSE comparten:

- misma instancia;
- mismo candidate set;
- mismos seeds de shot noise;
- mismo orden de evaluación;
- mismo backend/noise realization.

Esto convierte la comparación en pareada y reduce varianza. Los tests primarios usan bootstrap pareado por instancia y replicate/trajectory.

---

# 6. Methodological grounding

El PAP combina piezas ya establecidas:

1. quantum error mitigation;
2. VQA/QAOA bajo finite shots;
3. ranking-and-selection;
4. inferencia estadística pre-registrada;
5. cálculo de riesgo gaussiano multivariado.

La novedad es la integración:

\[
\text{QEM} + \text{decision risk} + \text{gap kernel} + \text{shots-to-success}.
\]

---

## 6.1 QEM as budgeted estimator design

QEM ya es un tradeoff entre bias, variance, overhead y recursos. El PAP cambia el objetivo:

\[
\arg\min_m \mathrm{MSE}_m
\quad \rightarrow \quad
\arg\min_m R_m^{dec}.
\]

Métodos base:

- Raw;
- ZNE;
- DA-ZNE;
- CDR si es estable;
- PEC si el overhead es viable.

---

## 6.2 Ranking-and-selection grounding

El Batch Candidate Optimizer es un problema de selección:

- finite candidate set;
- noisy estimates;
- finite budget;
- probability of correct selection.

La diferencia con ranking-and-selection clásico es que el ruido viene del pullback de QEM y se proyecta por:

\[
\Sigma_m=L K_m L^\top.
\]

---

## 6.3 VQA finite-shot grounding

En VQA/QAOA, la decisión relevante es:

- qué candidato aceptar;
- qué punto mantener;
- cuándo alcanzar una solución;
- cuántos shots se requieren para éxito confiable.

Por eso el endpoint principal es:

\[
B_m(0.8),
\]

no solo MSE.

---

## 6.4 Methodological references to cite in the PAP

### QEM foundations

- Temme, Bravyi, and Gambetta, *Error Mitigation for Short-Depth Quantum Circuits*, Physical Review Letters 119, 180509 (2017).
- Endo, Benjamin, and Li, *Practical Quantum Error Mitigation for Near-Future Applications*, Physical Review X 8, 031027 (2018).

### Data-driven QEM

- Czarnik, Arrasmith, Coles, and Cincio, *Error mitigation with Clifford quantum-circuit data*, Quantum 5, 592 (2021).
- Lowe et al., *Unified approach to data-driven quantum error mitigation*, Physical Review Research 3, 033098 (2021).

### VQA/QAOA finite-shot resources

- Zhou et al., *Quantum Approximate Optimization Algorithm: Performance, Mechanism, and Implementation on Near-Term Devices*, Physical Review X 10, 021067 (2020).
- Scriva et al., *Challenges of variational quantum optimization with measurement shot noise*, arXiv:2308.00044.
- Spall, *Implementation of the Simultaneous Perturbation Algorithm for Stochastic Optimization*, IEEE Transactions on Aerospace and Electronic Systems 34, 817–823 (1998).
- Spall, *Multivariate Stochastic Approximation Using a Simultaneous Perturbation Gradient Approximation*, IEEE Transactions on Automatic Control 37, 332–341 (1992).
- Powell, *A direct search optimization method that models the objective and constraint functions by linear interpolation* (1994).
- Kandala et al., *Hardware-efficient variational quantum eigensolver for small molecules and quantum magnets*, Nature 549, 242–246 (2017).

### Covariance estimation / shrinkage

- Ledoit and Wolf, *A well-conditioned estimator for large-dimensional covariance matrices*, Journal of Multivariate Analysis 88, 365–411 (2004).

### Ranking-and-selection

- Wu and Zhou, *Analyzing and provably improving fixed budget ranking and selection algorithms*, arXiv:1811.12183.
- Wang and Zhou, *Optimal Computing Budget Allocation for Data-driven Ranking and Selection*, arXiv:2209.11809.

### Inference

- Berger and Hsu, *Bioequivalence Trials, Intersection–Union Tests and Equivalence Confidence Sets*, Statistical Science 11, 283–319 (1996).
- Romano and Wolf, *Stepwise Multiple Testing as Formalized Data Snooping*, Econometrica 73, 1237–1282 (2005).

### Multivariate normal probabilities

- Genz, *Numerical Computation of Multivariate Normal Probabilities*, Journal of Computational and Graphical Statistics 1, 141–149 (1992).

### Predictibilidad de varianza/covarianza desde calibración

- Seksaria and Prabhakar, *Shots and variance on noisy quantum circuits*, arXiv:2501.03194.

### Aprendizaje escalable de ruido correlacionado

- van den Berg, Minev, Kandala, and Temme, *Probabilistic error cancellation with sparse Pauli–Lindblad models on noisy quantum processors*, Nature Physics 19, 1116–1121 (2023); arXiv:2201.09866.

---

# 7. GRI calibration decision tree

GRI es un plug-in gaussiano. Debe estar calibrado o degradarse formalmente.

---

## 7.1 Calibration metric

Para cada método \(m\) y budget \(B\):

\[
\delta_{\mathrm{GRI}}(m,B)
=
\left|
R_m^{GRI}(B)-R_m^{emp}(B)
\right|.
\]

Criterio primario:

\[
\max_{m,B\in \mathcal B_{\mathrm{cal}}}
\delta_{\mathrm{GRI}}(m,B)
\le
\tau_R.
\]

Valor inicial:

```yaml
tau_R: 0.05
preferred_tau_R: 0.03
```

\(\tau_R\) final se congela desde pilot held-out.

---

## 7.2 Decision tree

| Resultado del pilot | Acción pre-registrada |
|---|---|
| GRI calibra | Claim 3 usa GRI para predecir \(B^\star\) |
| GRI no calibra, empirical pilot risk predice bien | Claims 1/2 siguen; Claim 3 baja a empirical-predictive |
| GRI no calibra y empirical pilot risk tampoco predice | Claim 3 falla / no se usa como claim principal |
| GRI calibra excepto PEC | PEC queda fuera del núcleo; GRI válido para core |
| GRI falla en bajo \(B\) pero calibra en medio/alto \(B\) | restringir \(B^\star\) a rango calibrado |

---

## 7.3 Gaussianity diagnostics

Se reportan:

- Anderson–Darling por gap activo;
- skewness/kurtosis;
- Henze–Zirkler si dimensión permite;
- QQ plots;
- tail ratios.

No gatean el paper por sí solos. Gatea la calibración GRI vs empirical risk.

Diagnósticos adicionales para A3:

```yaml
A3_extra_diagnostics:
  Gaussianity_conditional_on_Cdev_true:
    purpose: separate_pullback_failure_from_nonGaussian_sampling_failure
  finite_sample_Sigma_hat_audit:
    purpose: separate_prediction_failure_from_empirical_covariance_estimation_noise
    required_outputs:
      - bootstrap_CI_for_each_active_covariance
      - shrinkage_sensitivity
      - replicate_count_sufficiency
      - stability_of_risk_ordering_under_Sigma_hat_uncertainty
```

---

## 7.4 Política exacta para calibración parcial de GRI

Se define una máscara de validez:

\[
\mathcal V=\{(m,B):\delta_{GRI}(m,B)\le \tau_R\}.
\]

### Caso A — GRI válido en el core

Si Raw, Accuracy-ZNE y Decision-ZNE calibran en los budgets de E1/E2/E3:

```yaml
gri_status: core_valid
claim3_allowed: strong_3A
selector_primary: GRI
```

### Caso B — GRI falla solo en métodos secundarios

Si GRI falla para PEC/CDR pero calibra para el core:

```yaml
gri_status: core_valid_secondary_methods_invalid
claim3_allowed: strong_3A_for_core_only
pec_cdr_status: secondary_descriptive_or_excluded
```

### Caso C — GRI falla en parte del budget grid

Si GRI calibra solo en un rango contiguo:

```yaml
gri_status: range_restricted
claim3_allowed: only_inside_valid_budget_range
```

El crossing \(B^\star\) solo puede ser claim fuerte si cae dentro del rango válido.

### Caso D — GRI no calibra en el core

Si GRI no calibra en Raw/Accuracy-ZNE/Decision-ZNE:

```yaml
gri_status: core_invalid
claim3_allowed: no_strong_3A
selector_primary: empirical_pilot_risk
claim_language: empirical_predictive_only
```

Claims 1 y 2 pueden sobrevivir si el selector empírico estaba pre-registrado y no vio confirmatory. Claim 3 deja de ser headline.

---

### Regla anti-rescate

No se permite cambiar \(\tau_R\), cambiar el rango de budgets, ni redefinir \(L\) después de ver confirmatory. Cualquier degradación debe seguir esta tabla, no decisiones ad hoc.

---

## 7.5 Estimador de covarianza y shrinkage

La estimación de \(\widehat\Sigma\) en la banda crítica usa shrinkage lineal óptimo de Ledoit–Wolf hacia un target diagonal/escalar-identidad; la intensidad de shrinkage es el óptimo data-driven en forma cerrada, no ajustado a mano. La elección se congela pre-hash y su efecto sobre el ordering de riesgo se reporta como `shrinkage_sensitivity` en la auditoría finito-muestral de A3 (§7.3).

```yaml
covariance_estimator:
  base: empirical_paired_gap_sample_covariance
  shrinkage: Ledoit_Wolf_linear_shrinkage      # ref: Ledoit & Wolf 2004
  shrinkage_intensity: closed_form_optimal
  target: scaled_identity_or_diagonal
  fallback_if_unstable: diagonal_loading_with_pilot_tuned_floor
  frozen_pre_hash: true
  audit: shrinkage_sensitivity_reported_in_A3
  config: analysis/estimator_spec.yaml
```

---

# 8. Claim 3: three-level predictive structure with pre-registered headline demotion

Claim 3 no es un bloque único. Se divide en 3 niveles, y el nivel permitido depende de dos gates:

1. A3 pullback gate: \(\Sigma_m^{pred}\) debe predecir \(\widehat\Sigma_m\).
2. \(W^\star\) gate: la ventana de cruce debe ser suficientemente estrecha para sostener lenguaje de crossing.

---

## 8.1 Claim 3A — strong device-level predictive crossing

Permitido solo si:

```yaml
A3_pullback_gate: pass
W_star: <= 0.5
B_star_obs_inside_interval: true
```

Endpoint:

\[
B^\star_{obs}
\in
[B^\star_{lo},B^\star_{hi}].
\]

Lenguaje permitido:

> Device-level noise structure predicts the budget at which the optimal mitigation strategy changes.

Este es el claim fuerte. Si \(W^\star>0.5\), no se puede usar como headline aunque el intervalo contenga \(B^\star_{obs}\).

---

## 8.2 Claim 3B — device-level directional ordering

Permitido si A3 pasa pero el crossing exacto es demasiado ancho o ruidoso.

```yaml
A3_pullback_gate: pass
W_star: > 0.5
directional_ordering_passes: true
```

El kernel debe predecir el signo/order antes, cerca y después del cruce:

\[
\mathrm{sign}
\left(
R_{DA}(B)-R_{MSE}(B)
\right)
\]

coincide con la predicción en budgets pre-registrados:

```yaml
directional_budgets:
  below_crossing: B_low
  near_crossing: B_star
  above_crossing: B_high
```

Lenguaje permitido:

> Device-level noise structure predicts the budget-dependent ordering of mitigation strategies.

Lenguaje prohibido bajo 3B:

- “predicts the exact crossing”;
- “predicts \(B^\star\)”;
- “predicts the budget switch” sin aclarar que es ordering direccional.

---

## 8.3 Claim 3C — diagnostic only

Si A3 falla o no hay potencia suficiente, Claim 3 no puede ser headline.

| Diagnóstico | Criterio | Consecuencia |
|---|---|---|
| DA domina todo el rango | \(R_{DA}<R_{MSE}\) para todos los \(B\) con CI | no crossing; reportar dominance |
| MSE domina todo el rango | \(R_{MSE}<R_{DA}\) para todos los \(B\) con CI | DA no soporta headline |
| No hay potencia | CI demasiado anchos / riesgos raros | Claim 3 diagnóstico |
| Pullback falla | \(\Sigma_m^{pred}\) no predice \(\widehat\Sigma_m\) | no PRXQ physical-prediction headline |
| Ordering contrario | predicción direccional contraria a datos con potencia suficiente | kernel falsado |

Solo 3A cuenta como crossing predictivo fuerte. 3B es predicción direccional. 3C es diagnóstico honesto.

---

# 9. Primary comparison: DA selector vs MSE selector

## 9.1 MSE selector

\[
m^\star_{\mathrm{MSE}}(B)
=
\arg\min_{m\in\mathcal M}
\widehat{\mathrm{MSE}}_m(B).
\]

## 9.2 DA selector

\[
m^\star_{\mathrm{DA}}(B)
=
\arg\min_{m\in\mathcal M}
\widehat{\mathrm{GRI}}_m(B,\mathcal C),
\]

o, si GRI no calibra:

\[
m^\star_{\mathrm{DA}}(B)
=
\arg\min_{m\in\mathcal M}
\widehat R^{emp,pilot}_m(B,\mathcal C).
\]

La regla exacta se fija en el GRI decision tree antes del hash.

---

## 9.3 Core menu

El menú mínimo:

\[
\mathcal M_{\mathrm{core}}
=
\{
\mathrm{Raw},
\mathrm{Accuracy\mbox{-}ZNE},
\mathrm{Decision\mbox{-}ZNE}
\}.
\]

CDR/PEC:

- entran si el pilot los aprueba;
- no son necesarios para que el paper sobreviva;
- no deben complicar el claim principal.

---

## 9.4 Algoritmo exacto de selección DA y MSE

La comparación primaria es entre dos selectores fuertes, no entre DA y un baseline débil.

---

### Inputs congelados

```yaml
selector_inputs:
  method_menu: [Raw, Accuracy-ZNE, Decision-ZNE]
  budget_grid: primary_budget_grid
  problem_cell: problem_family, noise_family, depth
  contrast_matrix: results/frozen/contrast_matrices.npz
  estimator_spec: analysis/estimator_spec.yaml
  budget_ledger: results/frozen/budget_ledger.csv
  tie_breaking: lowest_C_total_then_simpler_method
```

---

### MSE selector

Para cada \((m,B)\):

\[
\widehat{\mathrm{MSE}}_m(B)
=
\widehat{\mathrm{Bias}}_m(B)^2+\widehat{\mathrm{Var}}_m(B).
\]

El selector MSE elige:

\[
m^\star_{MSE}(B)=\arg\min_{m\in\mathcal M_{core}}\widehat{\mathrm{MSE}}_m(B).
\]

La estimación de MSE sale del pilot held-out y queda congelada en:

```text
results/pilot/mse_selector_table.csv
```

---

### DA selector con GRI válido

Para cada \((m,B)\):

\[
\Sigma_m(B)=L K_m(B)L^\top.
\]

El riesgo decisional plug-in es:

\[
\widehat R^{GRI}_m(B)
=
\mathbb P_{Z\sim\mathcal N(\hat\mu_m(B),\hat\Sigma_m(B))}
\left[\mathcal A(g+Z)\ne \mathcal A(g)\right],
\]

estimado sobre la distribución de gaps/candidatos definida en pilot. \(\mathcal A\) es la regla de decisión congelada: elegir el candidato de menor objetivo estimado.

El selector DA elige:

\[
m^\star_{DA}(B)=\arg\min_{m\in\mathcal M_{core}}\widehat R^{GRI}_m(B).
\]

La tabla congelada se guarda en:

```text
results/pilot/da_selector_table.csv
```

---

### DA selector con fallback empírico

Si GRI no calibra en el core, el selector primario cambia a:

\[
m^\star_{DA}(B)=\arg\min_{m\in\mathcal M_{core}}\widehat R^{emp,pilot}_m(B).
\]

Esto solo es válido si el fallback fue activado por el decision tree antes del hash.

---

### Tie-breaking

Si dos métodos tienen riesgos indistinguibles dentro de \(10^{-4}\):

1. elegir menor \(C_{total}\);
2. si empatan, elegir método más simple en este orden:

```yaml
tie_breaking_order:
  - Raw
  - Accuracy-ZNE
  - Decision-ZNE
  - CDR
  - PEC
```

Esta regla evita favorecer artificialmente a DA-ZNE cuando la diferencia es numéricamente irrelevante.

---

# 10. Dynamic loop central

## 10.1 Optimizer principal

Solo uno en el claim principal:

\[
\boxed{\text{Batch Candidate Optimizer}}
\]

SPSA/COBYLA quedan como robustez.

---

## 10.2 Ronda dinámica

En cada ronda \(t\):

1. generar \(K\) candidatos alrededor del mejor punto actual;
2. evaluar candidatos con el selector QEM;
3. elegir el mejor estimado;
4. actualizar;
5. registrar si la decisión fue correcta y el regret.

---

## 10.3 Parámetros congelados

```yaml
dynamic_task:
  optimizer: BatchCandidateOptimizer
  candidates_per_round: 5
  max_rounds: 20
  P_target: 0.80
  epsilon_opt_rule: ideal_landscape_quantile
  tie_breaking: lexicographic_by_grid_index
```

Valores finales se fijan por pilot held-out.
---

## 10.4 Justificación del dynamic loop frente a reviewers

El Batch Candidate Optimizer no se presenta como el único modelo realista de VQA. Se presenta como el modelo mínimo donde aparece la decisión que el paper estudia:

> bajo finite shots, un algoritmo variacional debe elegir entre candidatos con valores estimados ruidosos.

En QAOA/VQE reales, esta situación aparece cuando se decide:

- qué parámetro mantener;
- qué candidato explorar después;
- qué punto aceptar como incumbent;
- cuándo parar;
- cuántos shots gastar para distinguir candidatos cercanos.

Por eso el loop dinámico es una abstracción controlada de una decisión real, no un toy arbitrario.

---

### Anti-artificialidad

Para evitar que el loop favorezca a DA-QEM por construcción:

```yaml
dynamic_loop_safeguards:
  candidate_generation_independent_of_selector: true
  same_candidates_for_DA_and_MSE: true
  same_initial_points_for_DA_and_MSE: true
  same_budget_grid_for_DA_and_MSE: true
  same_stopping_rule_for_DA_and_MSE: true
  selector_does_not_generate_candidates: true
```

DA-QEM solo afecta cómo se estiman/evalúan candidatos, no qué candidatos aparecen.

---

### Robustez ecológica

SPSA/COBYLA no son endpoints primarios. Se usan solo para verificar que el signo del efecto no desaparece cuando el candidate generator cambia.

```yaml
secondary_optimizers:
  - SPSA_candidate_generator
  - COBYLA_trace_replay_if_feasible
claim_status: robustness_only
```

La asignación de valores de SPSA/COBYLA sigue la misma convención que el resto del PAP: exponentes/constantes fijados por literatura, parámetros sensibles calibrados en pilot held-out, congelados pre-hash, idénticos para DA y MSE, y con el costo de calibración cargado al budget ledger. No se tunean con datos confirmatorios.

```yaml
secondary_optimizer_value_assignment:
  status: robustness_only
  freeze_before_hash: true
  forbid_tuning_on_confirmatory: true
  same_values_for_DA_and_MSE: true
  candidate_trace_shared_across_selectors: true   # trace replay -> pairing
  budget_charged_to_ledger: true                  # incluye la fase de calibracion

  SPSA:
    method: Spall_power_series_with_pilot_calibration
    gain_sequences: "a_k = a/(A+k+1)^alpha ; c_k = c/(k+1)^gamma"
    fixed_from_literature:        # Spall 1998
      alpha: 0.602
      gamma: 0.101
      A_fraction_of_maxiter: 0.10
      perturbation_distribution: bernoulli_pm1
      resamplings: 1
    calibrated_on_pilot_heldout:
      c_rule: stddev_of_objective_at_initial_point   # ~25 evals
      a_rule: first_step_target_magnitude            # target ~ 2*pi/10
      calibration_cost_evals: ~50_charged_to_ledger
    maxiter: TBD_frozen_from_pilot
    restarts_or_initial_points: TBD_frozen_from_pilot

  COBYLA:
    method: Powell_trust_region
    mode: trace_replay_if_feasible
    rhobeg_rule: fraction_of_frozen_parameter_range
    rhoend_rule: pilot_measurement_resolution_floor
    maxiter: TBD_frozen_from_pilot
```

Nota de pairing: SPSA es estocástico y guiado por gradiente; para no romper el diseño pareado de §10.4, la secuencia de candidatos se genera una sola vez (desde una traza de referencia congelada) y se reproduce idéntica para DA y MSE. Es la misma razón por la que COBYLA está marcado `trace_replay`.

Si SPSA/COBYLA no confirman pero E2 sí confirma, el claim principal se mantiene limitado al Batch Candidate Optimizer. Si todos contradicen E2 con potencia suficiente, Claim 2 se degrada.


---

# 11. Experimentos principales

## E0 — Phase 0 executability audit

Objetivo: decidir si PRXQ está sobre la mesa antes de gastar cómputo.

Output obligatorio:

```text
results/pilot/executability_budget_table.md
results/pilot/executability_budget_table.csv
```

Debe incluir shots, wall-hours, backend, cola esperada, riesgos y decisión go/no-go por bloque.

## E0.5 — Pilot interpretability gates

Incluye:

1. Gate 0 full-vs-diagonal;
2. A3 frontier gate;
3. \(C_{\mathrm{dev}}^{true}\) vs \(C_{\mathrm{dev}}^{learned}\);
4. gaussianidad condicional;
5. auditoría finito-muestral de \(\widehat\Sigma\).

Si E0.5 falla en Gate 0 o A3, C1 escala deja de ser soporte físico PRXQ y se degrada a análisis secundario o se cancela.

## E1 — Static DA-QEM selector

Claim: DA reduce decision failure.

Endpoint:

\[
R_{\mathrm{DA}}^{dec}(B^\star)
<
R_{\mathrm{MSE}}^{dec}(B^\star).
\]

Usa:

- same menu;
- same budget contract;
- same critical band;
- same task.

---

## E2 — Dynamic Batch Candidate Optimizer

Claim: DA reduce shots-to-success.

Endpoint:

\[
B_{\mathrm{DA}}(0.8)
<
B_{\mathrm{MSE}}(0.8).
\]

Métricas secundarias:

- final regret;
- best-seen regret;
- bad-step acceptance;
- per-round decision failure;
- success at fixed budget.

---

## E3 — \(B^\star\) prediction

Claim: decision kernel predicts \(B^\star\).

Endpoints:

- 3A strong crossing;
- 3B directional ordering;
- 3C no-crossing diagnosis.

---

## E4 — Power, sensitivity and failure-rate audit

Este experimento no es un claim científico; es un control de interpretabilidad.

Antes de reportar Claims 1–3, se reporta:

- failure rate base de MSE por budget;
- failure rate base de Raw por budget;
- número efectivo de decisiones pareadas;
- ancho de CI para \(\Delta R_{static}\);
- ancho de CI para \(\Delta B_{0.8}\);
- sensibilidad a \(\epsilon_{opt}\) dentro de la regla pre-registrada.

Si el régimen es demasiado fácil o imposible, el paper no debe vender una victoria artificial.

---

## E5 — Exact claim survival table

Al final del análisis se llena una tabla binaria:

| Resultado observado | Claim permitido |
|---|---|
| Claim 2 confirma + efecto práctico | headline PRXQ fuerte |
| Claim 2 falla pero Claim 1 confirma | paper baja a static decision-aware QEM |
| Claim 1/2 confirman pero Claim 3A falla y 3B confirma | mecanismo predictivo parcial |
| Claim 1/2 confirman pero GRI falla | empirical decision-aware selector, no kernel headline |
| Solo análisis amortized gana | claim principal no permitido |
| Hardware inconcluso | hardware stress test descriptivo |
| Hardware contradice con potencia suficiente | limitar external validity; no claim hardware |

---

# 12. Ablations to separate mechanisms

Estas ablations evitan que el reviewer atribuya el resultado al mecanismo equivocado.

| Ablation | Pregunta que responde | Estado |
|---|---|---|
| Same methods: MSE selector vs DA selector | ¿el criterio decisional importa? | obligatorio |
| Accuracy-ZNE only vs DA-ZNE only | ¿el ajuste DA ayuda dentro del mismo método? | obligatorio |
| Full kernel vs diagonal kernel | ¿las covarianzas importan? | obligatorio |
| Full kernel vs shuffled \(L\) | ¿el efecto depende de la estructura decisional real? | obligatorio |
| GRI selector vs empirical-risk selector | ¿el modelo gaussiano aporta? | obligatorio si GRI calibra |
| Equal allocation vs DA allocation | ¿la asignación de shots explica el ahorro? | secundario |
| Raw-only vs selector | ¿el selector realmente agrega valor? | secundario |

---

## 12.1 Full kernel vs diagonal kernel

Comparar:

\[
\Sigma_m=L K_m L^\top
\]

contra:

\[
\mathrm{diag}(\Sigma_m).
\]

Endpoint:

- predictive accuracy of GRI;
- selector performance;
- \(B^\star\) prediction.

Si full kernel no mejora, el claim debe limitarse: la estructura diagonal de gaps basta en ese régimen.

---

## 12.1.1 Full-vs-diagonal como gate de mecanismo

El ablation full-vs-diagonal se evalúa en pilot held-out **antes** de comprometer cómputo confirmatorio, antes de validar el pullback completo (§16.1) y antes del eje de escala (§14, C1).

Su resultado fija el tier del claim físico, no solo la fuerza de una figura:

| Resultado pilot | Consecuencia pre-registrada |
|---|---|
| full kernel mejora GRI/selector/\(B^\star\) con margen | la covarianza decisional es relevante; el claim de predicción desde el canal (§16.1, Claim 3) tiene blanco; se procede a validar \(\Sigma_m^{pred}\) vs \(\widehat\Sigma_m\) y al eje de escala |
| full \(\approx\) diagonal | la estructura diagonal de gaps basta; el claim se limita a selección por riesgo decisional vs MSE; **no** se reclama predicción de covarianza desde el canal; el eje de escala C1 no se ejecuta como soporte del claim físico |

Esta regla es un gate de mecanismo: predecir covarianzas que no cambian la decisión no aporta, con independencia de la calidad de la predicción.

---

## 12.2 Shuffled \(L\)

Construir \(L_{\mathrm{shuffled}}\) que preserve dimensión pero destruya correspondencia con gaps reales.

Si DA con \(L_{\mathrm{shuffled}}\) también gana, el mecanismo está en duda.

Predicción:

\[
R_{\mathrm{DA,true}\ L}
<
R_{\mathrm{DA,shuffled}\ L}.
\]

---

# 13. Controls

## 13.1 Negative control: common-mode

Añadir:

\[
C_r\mathbf 1.
\]

Predicción:

- MSE cambia;
- decision risk no cambia;
- \(L E\) no cambia.

---

## 13.2 Positive control: when MSE is enough

Régimen con:

- ruido de gaps independiente;
- homoscedasticidad;
- sin correlaciones relevantes.

Predicción:

- MSE selector y DA selector coinciden o tienen desempeño indistinguible;
- no debe aparecer separación artificial.

---

## 13.3 Affine control

\[
F'(x)=aF(x)+b,
\quad a>0.
\]

Predicción:

- shift no cambia decisión;
- escala positiva preserva argmin;
- métricas cambian coherentemente.

---

# 14. Generality matrix: non-toy robustness

No se vende como universalidad. Se vende como robustez no-toy.

Matriz mínima:

\[
2\ \text{problems}
\times
2\ \text{noise families}
\times
2\ \text{depths}.
\]

| Eje | Configuración mínima |
|---|---|
| Problema 1 | QAOA-MaxCut |
| Problema 2 | VQE Ising/Heisenberg pequeño o portfolio/cardinality QAOA |
| Ruido 1 | depolarizing / Pauli |
| Ruido 2 | amplitude damping + dephasing |
| Depth 1 | shallow |
| Depth 2 | deeper, por ejemplo \(q_{\mathrm{depth}}=2\) |
| Realismo adicional | Aer backend-calibrated |

El claim de generalidad queda secundario:

> The effect is not restricted to a single toy instance.

No decir:

> universal across QEM.

---

## 14.1 Prioridad si la matriz completa es demasiado costosa

La matriz completa no debe ejecutarse con potencia baja solo para parecer amplia.

Orden de prioridad:

1. E1/E2/E3 primary con potencia alta.
2. Una segunda noise family con QAOA-MaxCut.
3. Un segundo problema pequeño.
4. Depth 1 como positive/easy control.
5. Hardware Level 3.
6. CDR/PEC secundarios.

Regla:

```yaml
never_trade_primary_power_for_secondary_breadth: true
```

Si los recursos son limitados, es mejor una celda primaria limpia, pareada y potente que una matriz grande con CIs inútiles.

---

# 15. Hardware Level 3

## 15.1 Rol metodológico

Hay dos niveles de hardware:

1. **Hardware-Σ micro-cell**: celda pequeña, 2–3 gaps activos, cuyo propósito es validar cuantitativamente \(\Sigma_m^{pred}\) vs \(\widehat\Sigma_m\) en dispositivo real. Esta celda es requisito para usar headline fuerte con lenguaje `device-level`.
2. **Hardware ordering Level 3**: prueba de ordering across budgets, sin reclamar constantes universales ni validación cuantitativa amplia de \(\Sigma\).

Hardware no se usa para validar el full kernel multi-qubit a escala grande ni constantes universales. La micro-celda solo demuestra que el pipeline de predicción desde \(C_{\mathrm{dev}}\) aprendido puede acertar covarianzas decisionales directamente estimables en dispositivo.

---

## 15.1.1 Hardware-Σ micro-cell

Diseño mínimo:

- IBM backend real;
- 2–3 gaps activos;
- 3–5 qubits;
- Raw / Accuracy-ZNE / DA-ZNE o selector core mínimo;
- \(C_{\mathrm{dev}}\) aprendido antes de estimar \(\widehat\Sigma_m\);
- estimación directa de \(\widehat\Sigma_m\) por repeticiones independientes;
- ejecución interleaved por método/budget;
- cluster bootstrap por epoch.

Endpoint:

\[
\Sigma_m^{pred}=L M_m C_{\mathrm{dev}}M_m^\top L^\top
\quad \text{vs} \quad
\widehat\Sigma_m^{hardware}.
\]

Regla de lenguaje:

```yaml
hardware_sigma_microcell:
  required_for_device_level_headline: true
  active_gaps: 2_to_3
  quantitative_claim_scope: local_microcell_only
  if_pass:
    allowed_language: device_level_noise_predicts_decision_covariance_in_a_microcell
  if_fail:
    forbidden_language:
      - device_level_noise_predicts_shot_cost
      - device_level_prediction_of_covariance
    required_title_demotion: true
```

Si esta celda no se puede correr, el título no debe contener `device-level`.

---

## 15.2 Diseño mínimo para hardware ordering

- IBM backend;
- 3–5 qubits;
- batch candidate decision pequeña;
- Raw / Accuracy-ZNE / DA selector;
- matched budget;
- interleaved scheduling;
- cluster bootstrap por epoch.

---

## 15.3 Regla dura de lenguaje según budgets ejecutados

Hardware solo puede reclamar ordering si se ejecutan tres budgets pre-registrados:

```yaml
hardware_budget_grid_for_ordering:
  required:
    - below_crossing
    - near_crossing
    - above_crossing
```

Potencia mínima:

```yaml
hardware_ordering_power_gate:
  required_for_directional_ordering_claim: true
  minimum_detectable_ordering_flip: pre_registered_from_pilot
  target_power: 0.80
  alpha: 0.05
  if_underpowered:
    allowed_claim: stress_test_or_local_consistency_only
```

Regla:

```yaml
hardware_claim_language:
  if budgets_run == [below_crossing, near_crossing, above_crossing]:
    allowed_claim: hardware ordering is directionally consistent with the predicted budget-dependent ordering
    allowed_words:
      - directional_ordering
      - budget_dependent_ordering
      - survives_across_budgets
  elif budgets_run == [near_crossing]:
    allowed_claim: hardware is consistent at the crossing budget only
    forbidden_words:
      - directional_ordering
      - survives_across_budgets
      - hardware_confirms_predicted_ordering
  else:
    allowed_claim: hardware stress test only
```

Un solo punto de hardware no permite decir “directional ordering”. Solo permite decir “consistent at the crossing budget”, si el signo local coincide.

---

## 15.4 Claims permitidos

### Si se corren tres budgets

> The hardware run is directionally consistent with the predicted budget-dependent ordering.

### Si se corre solo near-crossing

> The hardware run is locally consistent at the crossing budget.

### Si hardware es inconcluso

> The hardware run is reported as an inconclusive stress test and is not used to support the main simulated claims.

No reclamar:

- validación cuantitativa amplia de \(\Sigma\) fuera de la micro-celda hardware-Σ;
- validación de lower bound;
- universalidad;
- constants-level agreement;
- directional ordering si solo se ejecutó un budget.

---

## 15.5 Política si hardware sale inconcluso o contrario

Hardware no decide Claims 1–3. Su rol es stress test.

### Caso H-A — tres budgets consistentes

```yaml
hardware_claim: directionally_consistent_budget_dependent_ordering
figure_status: secondary_main_or_supplement
```

### Caso H-B — un budget consistente

```yaml
hardware_claim: locally_consistent_at_crossing_budget
figure_status: supplement_or_short_main_note
forbidden_claim: directional_ordering
```

### Caso H-C — inconcluso

```yaml
hardware_claim: inconclusive_stress_test
figure_status: supplement
main_text_language: no_quantitative_hardware_validation
```

### Caso H-D — contrario con baja potencia

```yaml
hardware_claim: underpowered_opposite_sign
interpretation: limitation_not_refutation
```

### Caso H-E — contrario con potencia suficiente

```yaml
hardware_claim: external_validity_limited
required_action: remove_hardware_positive_language
main_claims: simulation_and_model_only
```

No se permite ocultar hardware si fue ejecutado. Si se ejecuta, se reporta.

---

# 16. Secondary strong results

## 16.1 Pullback QEM as the physical prediction bridge

### 16.1.0 Dónde se valida \(\Sigma\) cuantitativamente y dónde no

El claim de predicción desde el canal opera en tres niveles. La versión v13 mantiene una micro-celda de hardware para que el lenguaje `device-level` no dependa solo de simulación.

| Pieza | Régimen de validación | Estatus del claim |
|---|---|---|
| \(\Sigma_m^{pred}=L M_m C_{\mathrm{dev}} M_m^\top L^\top\) vs \(\widehat\Sigma_m\) | **simulación**, escala núcleo, sobre matriz de generalidad | cuantitativo; aquí vive el Claim 3A/3B principal |
| \(\Sigma_m^{pred}\) vs \(\widehat\Sigma_m^{hardware}\) | **hardware-Σ micro-cell**, 2–3 gaps activos | cuantitativo local; requisito para headline `device-level` fuerte |
| caracterización de \(C_{\mathrm{dev}}\) | sparse Pauli–Lindblad aprendido, citado y no re-derivado | insumo; no contribución principal |
| ordering direccional | hardware Level 3, 3 budgets | falsable; sin reclamo de constantes ni \(\Sigma\) grande |

Regla: la predicción cuantitativa amplia de \(\Sigma\) se establece en simulación a escala donde \(\widehat\Sigma_m\) es estimable directamente. La micro-celda hardware-Σ valida que el pipeline también puede acertar una covarianza decisional pequeña en dispositivo real. El hardware de tres budgets confirma ordering falsable, no magnitud de \(\Sigma\) a escala.

### 16.1.0.1 Brazo \(C_{\mathrm{dev}}^{true}\) vs \(C_{\mathrm{dev}}^{learned}\) con criterios de pase

Para evitar que una falla de A3 sea ininterpretable, se separan cuatro fuentes de error:

1. teoría del pullback;
2. aprendizaje de ruido;
3. estimación finito-muestral de \(\widehat\Sigma\);
4. aproximación gaussiana usada por GRI.

Diseño:

\[
C_{\mathrm{dev}}^{true}
\rightarrow
\Sigma^{pred,true}
=
L M C_{\mathrm{dev}}^{true}M^\top L^\top,
\]

\[
C_{\mathrm{dev}}^{learned}
\rightarrow
\Sigma^{pred,learned}
=
L M C_{\mathrm{dev}}^{learned}M^\top L^\top.
\]

El brazo no es solo descriptivo. Tiene tres criterios de pase pre-registrados.

#### Gate C1 — recuperación del canal aprendido

Se mide el error relativo del canal aprendido sobre los generadores activos del modelo sparse Pauli–Lindblad:

\[
e_C
=
\frac{
\|C_{\mathrm{dev}}^{learned}-C_{\mathrm{dev}}^{true}\|_{W}
}{
\|C_{\mathrm{dev}}^{true}\|_{W}+\epsilon_0
}.
\]

\(\|\cdot\|_W\) es una norma ponderada congelada antes del freeze, con peso mayor en los generadores que afectan los observables decisionales. Se reporta también recuperación de soporte:

Concretamente, el peso de cada generador se fija por su sensibilidad de ranking proyectada: \(w_g\) proporcional a \(|\partial(\text{margen de ranking})/\partial g|\) usando los mismos gradientes \(G_{mn}\) de §3.3.1, agregados sobre los pares activos y los budgets de pilot, normalizados a suma uno. Los pesos se congelan antes de ver los resultados de learning.

```yaml
Cdev_recovery_weight_W:
  rule: weight_by_projected_ranking_sensitivity   # reuse G_mn from 3.3.1
  w_g: proportional_to_abs_d_rank_margin_d_generator_g
  aggregation: over_active_pairs_and_pilot_budgets
  normalization: sum_to_one
  freeze_weights_before_learning_results: true
```

\[
F1_{support}
=
\frac{2\,precision\,recall}{precision+recall+\epsilon_0}.
\]

Valores iniciales recomendados:

```yaml
Cdev_learning_recovery_gate:
  relative_weighted_generator_error_max: 0.20
  support_F1_min: 0.90
  freeze_weights_before_learning_results: true
```

Estos umbrales son diagnósticos duros para decir que el noise-learning recuperó el canal. Si fallan, no se puede atribuir una falla de A3 directamente a la teoría del pullback.

#### Gate C2 — propagación del canal aprendido a \(\Sigma\)

Se compara el pullback desde canal verdadero y desde canal aprendido:

\[
e_{\Sigma,C}
=
\frac{
\|\Sigma^{pred,learned}-\Sigma^{pred,true}\|_F
}{
\|\Sigma^{pred,true}\|_F+\epsilon_0
}.
\]

Además del error Frobenius, se exige preservación decisional usando la misma métrica proyectada de §3.3.1:

\[
\delta^{rank,C}_{mn}(B)
=
\left|
\left\langle G_{mn}^{(m)}(B),
\Sigma_m^{pred,learned}(B)-\Sigma_m^{pred,true}(B)
\right\rangle_F
+
\left\langle G_{mn}^{(n)}(B),
\Sigma_n^{pred,learned}(B)-\Sigma_n^{pred,true}(B)
\right\rangle_F
\right|.
\]

Gate primario:

\[
\delta^{rank,C}_{mn}(B)
<
\rho_C |\Delta_{mn}^{pred,true}(B)|.
\]

Regla recomendada:

```yaml
Cdev_to_Sigma_decision_gate:
  primary_gate: projected_ranking_error_from_learned_vs_true_Cdev
  rho_C: 0.25
  secondary_relative_frobenius_error_max: 0.20
  same_active_pairs_as_A3: true
```

#### Gate C3 — interpretación de fallas

```yaml
Cdev_disentangling_arm:
  recover_sparse_PL_generators: true
  compare_true_vs_learned_Cdev: true
  compare_Sigma_pred_true_vs_learned: true
  compare_Sigma_pred_learned_vs_Sigma_hat: true
  pass_requires:
    - Cdev_learning_recovery_gate
    - Cdev_to_Sigma_decision_gate
  if_true_matches_hat_but_learned_fails:
    interpretation: noise_learning_failure_not_pullback_failure
    A3_status: noise_learning_limited
  if_true_fails_against_hat_and_Sigmahat_audit_passes:
    interpretation: pullback_or_sampling_model_failure
    A3_status: theory_or_model_limited
  if_Sigmahat_audit_fails:
    interpretation: finite_sample_covariance_estimation_limited
    A3_status: inconclusive
  if_gaussianity_conditional_on_Cdev_true_fails:
    interpretation: GRI_distributional_assumption_limited
    A3_status: empirical_fallback_only
```

Sin estos criterios de pase, el brazo \(C_{\mathrm{dev}}^{true}\) vs learned no puede usarse para decir que la estimación de ruido no fue culpable.

---


Rol central:

\[
\Sigma_m^{pred}
=
L M_m C_{\mathrm{dev}}M_m^\top L^\top
\]

contra:

\[
\widehat\Sigma_m.
\]

Estado: **core physical bridge**.

Este análisis ya no es solo secundario fuerte. Es el gate A3 que decide si el paper puede reclamar predicción física desde caracterización del dispositivo. Si falla, Claim 3 se degrada y el paper no debe venderse como PRXQ-predictive.

### 16.1.1 Frontera de régimen donde DA-QEM debe ganar

La tensión “efecto vs mecanismo” se resuelve convirtiendo la heterogeneidad del efecto en resultado. El paper no debe decir solo que DA gana en algunos regímenes; debe predecir desde el ruido y la geometría de gaps dónde DA debe ganar.

Definir una variable de régimen:

\[
\rho_{gap/noise}
=
\Phi\left(L, K_m, C_{\mathrm{dev}}, B\right),
\]

que resume dimensión activa de gaps, correlación decisional y fuerza de correlación inducida por ruido. Antes del confirmatorio se predice una frontera:

\[
\rho_{gap/noise}\ge \rho_c
\quad \Rightarrow \quad
\mathrm{Savings}_{DA}\ge 0.20.
\]

Regla:

```yaml
regime_frontier:
  must_be_derived_before_confirmatory: true
  inputs_allowed:
    - Cdev_from_pilot
    - L_from_frozen_candidate_geometry
    - pilot_noise_family_parameters
  forbidden:
    - confirmatory_effect_sizes
  if_confirmed:
    claim_strength: PRXQ_9plus_support
  if_observed_posthoc_only:
    claim_strength: descriptive_3B_only
```

La forma funcional de \(\Phi\) y el umbral \(\rho_c\) se fijan a priori (pre-hash), no post-hoc:

```yaml
regime_variable_definition:
  track: optional_9p5
  Phi_components:
    - effective_active_gap_dimension              # de L y la banda crítica
    - decision_gap_correlation_strength           # off-diagonals de Sigma = L K L^T
    - noise_induced_gap_correlation               # del pullback L M C_dev M^T L^T
  Phi_rule: monotone_scalar_summary_fixed_pre_hash
  rho_c_rule: regime_value_where_GRI_predicted_savings_equals_practical_threshold  # Savings_pred = 0.20
  inputs_allowed: [Cdev_from_pilot, L_frozen, pilot_noise_params]
  forbidden_inputs: [confirmatory_effect_sizes]
  if_posthoc_only: descriptive_3B_only
```

Si la frontera solo se observa post-hoc, no cuenta para 9.5.


---

## 16.2 Focal lower bound

Claim modesto:

> In a focal two-candidate regime, DA-QEM approaches the finite-shot decision-reliability lower bound more closely than MSE-QEM.

No decir:

> universal fundamental limit of all QEM decisions.

---

## 16.3 CDR/PEC

CDR entra si:

- training es estable;
- split está congelado;
- mejora o aporta contraste claro.

PEC entra si:

- overhead es viable;
- budget matching está claro;
- no domina todo el costo.

Ambos son secundarios.

---

# 17. Multiplicity and inference

## 17.1 Familia primaria

Claims:

1. Claim 2 — shots-to-success;
2. Claim 1 — static failure;
3. Claim 3 — \(B^\star\) prediction.

Recomendación: gatekeeping.

Orden:

1. Claim 2.
2. Claim 1.
3. Claim 3A.

Si Claim 2 falla, Claim 1/3 se reportan como soporte, no headline.

---

## 17.2 Escaneos secundarios

Todo escaneo sobre:

- budgets;
- problemas;
- profundidades;
- noise families;
- bands;
- methods;

usa Romano–Wolf step-down o se reporta como descriptivo.

---

# 18. Reproducibility and data release

## 18.1 RNG

```yaml
rng:
  library: numpy
  bit_generator: PCG64DXSM
  root_seed: 260616
  seed_derivation: hash(instance_id, method, budget, replicate_id, stream)
```

---

## 18.2 Freeze manifest

Debe incluir:

- Git commit;
- Docker digest;
- Python/Qiskit/Aer versions;
- config hashes;
- script hashes;
- PAP hash;
- pilot outputs hash;
- confirmatory analysis scripts hash.

---

## 18.3 Data release

Preparar:

- GitHub tag;
- Zenodo DOI;
- Docker image;
- frozen configs;
- raw confirmatory outputs;
- processed figures;
- Data Availability Statement.

---

# 19. Figure manifest

## Figuras principales

| Figura | Claim |
|---|---|
| Fig. 1 Concept and threat model summary | motivation/design |
| Fig. 2 Static DA selector reduces decision failure | Claim 1 |
| Fig. 3 Dynamic shots-to-success | Claim 2 |
| Fig. 4 \(B^\star\) prediction | Claim 3 |

---

## Figuras secundarias

| Figura | Rol |
|---|---|
| Budget ledger | fairness |
| GRI calibration | model validity |
| Ablations | mechanism |
| Controls | defense |
| Generality matrix | non-toy robustness |
| Hardware Level 3 | stress test |
| Pullback QEM | physical connection |
| Focal lower bound | theoretical support |

---

# 20. Criterios de éxito PRXQ

Para sostener versión PRXQ deben cumplirse:

1. Claim 2: DA reduce shots-to-success con efecto práctico.
2. Claim 1: DA reduce static decision failure como consistency check.
3. Gate 0 full-vs-diagonal demuestra que la covarianza completa aporta al mecanismo.
4. A3 pullback valida \(\Sigma_m^{pred}\) vs \(\widehat\Sigma_m\) antes de reclamar predicción física.
5. Claim 3A o al menos 3B: kernel predice cruce u ordering bajo la regla \(W^\star\).
6. Diseño confirmatorio ejecutado según freeze manifest.
7. Power report confirma sensibilidad suficiente.
8. Budget ledger no favorece artificialmente DA.
9. GRI calibra o el fallback está pre-registrado.
10. Ablations apoyan el mecanismo.
11. Controls no contradicen teoría.
12. Generality matrix muestra robustez no-toy sin sacrificar potencia primaria.
13. Hardware Level 3, si se ejecuta, se reporta con lenguaje limitado.

---
# 21. Criterios de muerte

El claim PRXQ queda débil si:

1. DA no mejora shots-to-success.
2. DA gana solo con cost accounting amortized pero no non-amortized.
3. \(B^\star\) falla y tampoco hay directional predictive ordering.
4. DA-QEM fue ajustado con datos confirmatorios.
5. MSE selector no fue un baseline fuerte.
6. El dynamic loop favorece a DA por candidate generation no pareado.
7. Full kernel no mejora contra diagonal/shuffled y aun así el manuscrito reclama predicción física de covarianza desde el canal.
8. A3 pullback no predice \(\widehat\Sigma_m\) y aun así el manuscrito mantiene lenguaje PRXQ-predictive.
9. GRI no calibra y empirical fallback no predice.
10. El control “when MSE is enough” también muestra DA win artificial.
11. El análisis primario queda underpowered.
12. Generality falla en todos los regímenes secundarios.
13. Hardware se sobre-reclama, se oculta o se usa para afirmar más de lo que permite.

---
# 22. Claim language

## Mensaje principal si A3 pasa y hardware-Σ micro-cell valida

> Device-level noise structure predicts when MSE-selected QEM wastes quantum shots in downstream decisions.

## Mensaje principal si A3 pasa solo en simulación/pullback pero no hay hardware-Σ

> The decision gap kernel predicts when MSE-selected QEM wastes quantum shots in downstream decisions.

Este mensaje solo se permite si:

```yaml
A3_pullback_gate: pass
claim3_level: 3A_or_3B
```

---

## Mensaje principal si A3 falla

> QEM should be selected by quantum decision-resource cost, not estimator MSE.

Este mensaje corresponde al track Quantum / metodología fuerte. No usa lenguaje de predicción desde canal físico.

---

## Permitido si Claim 2 confirma

> Decision-aware QEM reduces the quantum sampling cost required to reach a fixed downstream success probability.

---

## Permitido si Claim 1 confirma

> Decision-aware QEM reduces downstream decision failure at matched budget.

Pero Claim 1 debe presentarse como consistency check del mecanismo, no como descubrimiento principal.

---

## Permitido si Claim 3A confirma

> Device-level noise structure predicts the budget at which the optimal mitigation strategy changes.

---

## Permitido si Claim 3B confirma

> Device-level noise structure predicts the budget-dependent ordering of mitigation strategies.

---

## Permitido para hardware

Tres budgets:

> The hardware run is directionally consistent with the predicted budget-dependent ordering.

Un budget:

> The hardware run is locally consistent at the crossing budget.

---

## No permitido

- “Decision-aware QEM always wins.”
- “MSE is useless.”
- “Hardware quantitatively validates the full theory.”
- “Hardware shows directional ordering” si solo se corrió un budget.
- “The method universally saturates the lower bound.”
- “CDR/PEC are generally worse or better.”
- “The result proves universal superiority across QEM.”
- “Device-level prediction” si A3 falla.
- “Predicts \(B^\star\)” si \(W^\star>0.5\) y solo queda 3B.

---

# 23. Título recomendado

Primera opción si A3 pasa:

**Decision-Aware Quantum Error Mitigation: Predicting Quantum Shot Cost from the Decision Gap Kernel**

Título fuerte condicionado, solo si hardware-Σ micro-cell valida cuantitativamente el pullback en dispositivo:

**Decision-Aware Quantum Error Mitigation: Device-Level Noise Predicts Quantum Shot Cost in Downstream Decisions**

Alternativas si A3 pasa:

1. **Device-Level Noise Structure Predicts Finite-Shot Decision Cost in Quantum Error Mitigation**
2. **Predicting Quantum Shot Waste in Decision-Aware Error Mitigation**
3. **Decision Kernels for Device-Predicted Quantum Error Mitigation**

Título si A3 falla y el paper va por track Quantum/metodología:

**Decision-Aware Quantum Error Mitigation: Reducing Finite-Shot Decision Failure at Matched Budget**

---

# 24. Decisión final de diseño

El PAP queda organizado alrededor de un gate físico y dos claims operacionales.

## Gate 0 — mecanismo full-vs-diagonal

\[
\boxed{
\Sigma_m = L K_m L^\top
\quad\text{adds decision-relevant information beyond}\quad
\mathrm{diag}(\Sigma_m)
}
\]

Este gate se ejecuta antes de A3. Si full \(\approx\) diagonal, el paper no reclama predicción física de covarianza desde canal; se limita a selección por riesgo decisional vs MSE.

## Gate físico A3

\[
\boxed{
\Sigma_m^{pred}=L M_m C_{\mathrm{dev}}M_m^\top L^\top
\approx
\widehat\Sigma_m
}
\]

Este gate se ejecuta solo si Gate 0 pasa. Decide si el paper tiene claim PRXQ de predicción física desde canal caracterizado.

## Claim operacional principal

\[
\boxed{
B_{DA}(0.8)<B_{MSE}(0.8)
}
\]

Este es el endpoint más importante: reducción del costo de shots para alcanzar éxito decisional.

## Claim de consistencia

\[
\boxed{
R_{DA}^{dec}(B)<R_{MSE}^{dec}(B)
}
\]

Este claim confirma que el selector decisional reduce failure bajo budget matched. No debe ser el headline principal.

## Claim predictivo condicionado

Si Gate 0 pasa, A3 pasa y \(W^\star\le 0.5\):

\[
\boxed{
B^\star_{obs}\in[B^\star_{lo},B^\star_{hi}]
}
\]

Si Gate 0 y A3 pasan pero \(W^\star>0.5\), el claim baja a ordering direccional 3B.

Si Gate 0 falla, Claim 3 queda limitado: no hay headline de covarianza física.

Si A3 falla, Claim 3 queda diagnóstico y el paper se degrada a track Quantum/metodología.

---

# 25. Orden práctico de ejecución

1. Ejecutar Fase 0: tabla de shots, wall-hours, backend, cola y riesgo.
2. Si Fase 0 no cierra para E1/E2/E3 y hardware-Σ, detener track PRXQ; preparar track Quantum/QEM-methods.
3. Ejecutar Gate 0 full-vs-diagonal en pilot held-out.
4. Si Gate 0 falla o full \(\approx\) diagonal, no vender predicción física de covarianza; preparar track Quantum/metodología con Claim 2 como núcleo.
5. Si Gate 0 pasa, ejecutar A3 frontier validation: \(\Sigma_m^{pred}\) vs \(\widehat\Sigma_m\), usando tolerancia de volteo del ranking de riesgo.
6. Ejecutar brazo \(C_{\mathrm{dev}}^{true}\) vs \(C_{\mathrm{dev}}^{learned}\), diagnóstico de gaussianidad condicional y auditoría finito-muestral de \(\widehat\Sigma\).
7. Decidir 3A vs 3B según \(W^\star\le0.5\) y la frontera de A3.
8. Si A3 llega solo a 3B, construir el paper base para PRXQ/9 con dos claims: prediction of budget-dependent ordering + shots-to-success.
9. Si A3 llega a 3A, considerar upgrade 9+ con predicción de budget switch.
10. Ejecutar hardware-Σ micro-cell si se quiere usar lenguaje `device-level` en título/headline.
11. Ejecutar hardware ordering de tres budgets solo si tiene potencia para detectar ordering flip; si no, reportarlo como stress test o consistencia local.
12. Ejecutar escala 4/6/8 solo si Fase 0, Gate 0 y A3 justifican soporte físico; 8 qubits queda explícitamente como trend only.
13. Ejecutar E1/E2/E3 confirmatorios solo después del freeze.
14. Mantener CDR/PEC como secundarios.
15. No agregar más ablations/controles salvo que el pilot revele una falla específica.

---

# 26. Control de extensión del manuscrito

Para track PRXQ, el texto principal debe tener máximo dos claims sustantivos.

## Track 9 base

Tesis:

> The decision gap kernel predicts budget-dependent QEM ordering, and DA-QEM reduces shots-to-success under matched budget.

Texto principal:

1. decision gap kernel / ordering prediction;
2. shots-to-success;
3. hardware-Σ micro-cell si existe y es limpia;
4. hardware three-budget ordering si es powered.

Suplemento:

- Claim 1 static failure;
- full ablations;
- controls;
- generality matrix;
- \(C_{\mathrm{dev}}^{true}\) vs learned details;
- CDR/PEC.

## Track 9.5 upside

Tesis única:

> The pullback of mitigated device noise into the decision-gap space predicts the regime where decision-aware mitigation strictly dominates in quantum shot cost, and this prediction survives a falsifiable device test.

No se agregan claims paralelos. Claim 1, Claim 2, hardware-Σ, ordering de hardware, ablations y controls quedan subordinados a esa tesis.

## Tres no-se-puede honestos

1. Si Gate 0 da full \(\approx\) diagonal, el track 9/9.5 se cierra: Quantum/QEM-methods.
2. Si Fase 0 no cierra, el track 9/9.5 se cierra por logística.
3. Si A3 no llega a 3A o la frontera de régimen no es derivable a priori, el track 9.5 se cierra; 3B puede sostener un 9 si hardware y Claim 2 son fuertes.

La versión v12 incorpora la ruta dura: no se persigue PRXQ por narrativa. Primero se demuestra ejecutabilidad, luego mecanismo, luego pullback, luego dispositivo. Si cualquiera de esos gates falla, se degrada el venue o el lenguaje antes de gastar meses.
