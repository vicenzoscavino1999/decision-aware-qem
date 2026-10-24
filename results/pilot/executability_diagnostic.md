# Executability diagnostic

Counts follow the executable profiles. Runtime values are a single-worker QAOA proxy, not a campaign ETA or a publication gate.

E1 and E3 share raw data. E2 shares the Raw-at-B_max proposal and shot prefixes across budgets and selectors.

Characterization is one uniform two-parameter learning run. Hardware and unconfigured scaling costs remain unknown.

| block | acquisition circuits | shots | runtime proxy (hours) | timing scope |
|---|---:|---:|---:|---|
| E1_static | 144000 | 1179648000 | 9.26823 | single_worker_QAOA_proxy |
| E2_dynamic | 384000 | 3145728000 | 24.7153 | single_worker_QAOA_proxy |
| Pilot_shared | 60000 | 491520000 | 3.86176 | single_worker_QAOA_proxy |
| Uniform_Cdev | 1000 | 4096000 | not measured | not_measured |
| E3_pullback | 0 | 0 | not measured | reuses_E1_raw_analysis_time_not_measured |

proxy only: one graph, base noise, one worker; excludes parallel speedup, memory extraction, numerical analysis and differences between noise scales

The JSON file records resolved configurations, all timing samples and unknown quantities as null.
