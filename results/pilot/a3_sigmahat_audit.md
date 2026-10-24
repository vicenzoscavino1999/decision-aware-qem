# A3 covariance bootstrap diagnostic

All draws resample shared replicate IDs jointly across methods. Each draw refits the full Ledoit-Wolf covariance before extracting submatrices. Coefficients, ideal margins and reference covariance remain fixed.
Pointwise percentile intervals describe estimator variability conditional on this pilot. They are not simultaneous coverage bounds or certified population-error bounds. One random subsample per size is a sensitivity check, not proof of sample-size sufficiency.
Full-risk point relations and bootstrap relations on one common restricted gap event are reported separately. A tilde means numerically unresolved within 2e-6, not exact equality. Repeated unresolved relations do not certify a strict order.
Projection uses the full analytic Frobenius gradient of the reference covariance and recomputed margins. Pairs below the original absolute risk margin 0.005 are inactive. The projected condition is linearized and does not control Taylor remainder or method-dependent bias.

Bootstrap draws: 200; percentile interval: 0.95.

## Projected covariance-error ratios

| cell | B | pair | active | point | CI low | CI high | fraction above 1 | diagnostic |
|---|---:|---|---|---:|---:|---:|---:|---|
| P001 | 1024 | Raw_vs_Accuracy-ZNE | True | 0.01128685321157586 | 0.003173373252607523 | 0.27066986682649125 | 0.0 | interval_below_threshold |
| P001 | 1024 | Raw_vs_Decision-ZNE | True | 0.012821209028628891 | 0.0029579248220642745 | 0.2671656664592477 | 0.0 | interval_below_threshold |
| P001 | 1024 | Accuracy-ZNE_vs_Decision-ZNE | False | None | None | None | None | inactive_pair |
| P001 | 2048 | Raw_vs_Accuracy-ZNE | True | 0.03433996642839106 | 0.00396928980667127 | 0.27654428510187423 | 0.0 | interval_below_threshold |
| P001 | 2048 | Raw_vs_Decision-ZNE | True | 0.029567499859923994 | 0.0026394266027340006 | 0.268665539637987 | 0.0 | interval_below_threshold |
| P001 | 2048 | Accuracy-ZNE_vs_Decision-ZNE | False | None | None | None | None | inactive_pair |
| P001 | 256 | Raw_vs_Accuracy-ZNE | True | 0.18744289504369915 | 0.008316263709477505 | 0.4018068084040515 | 0.0 | interval_below_threshold |
| P001 | 256 | Raw_vs_Decision-ZNE | True | 0.18735503438938492 | 0.011888560729025319 | 0.4010433591098375 | 0.0 | interval_below_threshold |
| P001 | 256 | Accuracy-ZNE_vs_Decision-ZNE | False | None | None | None | None | inactive_pair |
| P001 | 4096 | Raw_vs_Accuracy-ZNE | True | 0.03342218620725838 | 0.011413454902672955 | 0.35369503195578395 | 0.0 | interval_below_threshold |
| P001 | 4096 | Raw_vs_Decision-ZNE | True | 0.03287579187843868 | 0.0075462831065348035 | 0.34813708660658677 | 0.0 | interval_below_threshold |
| P001 | 4096 | Accuracy-ZNE_vs_Decision-ZNE | False | None | None | None | None | inactive_pair |
| P001 | 512 | Raw_vs_Accuracy-ZNE | True | 0.06260970054852873 | 0.003988576707397038 | 0.25921780475320033 | 0.0 | interval_below_threshold |
| P001 | 512 | Raw_vs_Decision-ZNE | True | 0.0640182076747458 | 0.004287032000871229 | 0.2542695406948691 | 0.0 | interval_below_threshold |
| P001 | 512 | Accuracy-ZNE_vs_Decision-ZNE | False | None | None | None | None | inactive_pair |
| P001 | 8192 | Raw_vs_Accuracy-ZNE | True | 0.3519112870649335 | 0.021242145572804662 | 0.8069518903709059 | 0.0 | interval_below_threshold |
| P001 | 8192 | Raw_vs_Decision-ZNE | True | 0.3440721368517937 | 0.02599974153529038 | 0.7932047729031273 | 0.0 | interval_below_threshold |
| P001 | 8192 | Accuracy-ZNE_vs_Decision-ZNE | False | None | None | None | None | inactive_pair |
| P002 | 1024 | Raw_vs_Accuracy-ZNE | True | 0.39934669009667007 | 0.07278748917173154 | 0.7835873904764067 | 0.0 | interval_below_threshold |
| P002 | 1024 | Raw_vs_Decision-ZNE | True | 0.3919991946479436 | 0.06565870274755801 | 0.7710164539989072 | 0.0 | interval_below_threshold |
| P002 | 1024 | Accuracy-ZNE_vs_Decision-ZNE | False | None | None | None | None | inactive_pair |
| P002 | 2048 | Raw_vs_Accuracy-ZNE | True | 0.9048410149132998 | 0.15755576280471925 | 1.8169966798327442 | 0.475 | interval_crosses_threshold |
| P002 | 2048 | Raw_vs_Decision-ZNE | True | 0.8567522089916556 | 0.16394368750110247 | 1.7528780664830579 | 0.44 | interval_crosses_threshold |
| P002 | 2048 | Accuracy-ZNE_vs_Decision-ZNE | False | None | None | None | None | inactive_pair |
| P002 | 256 | Raw_vs_Accuracy-ZNE | True | 0.014123519001304234 | 0.003516697178365182 | 0.15788666672379828 | 0.0 | interval_below_threshold |
| P002 | 256 | Raw_vs_Decision-ZNE | True | 0.013176371677210409 | 0.0036882905091650342 | 0.15317206751624682 | 0.0 | interval_below_threshold |
| P002 | 256 | Accuracy-ZNE_vs_Decision-ZNE | False | None | None | None | None | inactive_pair |
| P002 | 4096 | Raw_vs_Accuracy-ZNE | False | None | None | None | None | inactive_pair |
| P002 | 4096 | Raw_vs_Decision-ZNE | False | None | None | None | None | inactive_pair |
| P002 | 4096 | Accuracy-ZNE_vs_Decision-ZNE | False | None | None | None | None | inactive_pair |
| P002 | 512 | Raw_vs_Accuracy-ZNE | True | 0.01987250785974611 | 0.0011971053828041679 | 0.19955888244236902 | 0.0 | interval_below_threshold |
| P002 | 512 | Raw_vs_Decision-ZNE | True | 0.019536687364710377 | 0.000689417049419184 | 0.1948197980534129 | 0.0 | interval_below_threshold |
| P002 | 512 | Accuracy-ZNE_vs_Decision-ZNE | False | None | None | None | None | inactive_pair |
| P002 | 8192 | Raw_vs_Accuracy-ZNE | False | None | None | None | None | inactive_pair |
| P002 | 8192 | Raw_vs_Decision-ZNE | False | None | None | None | None | inactive_pair |
| P002 | 8192 | Accuracy-ZNE_vs_Decision-ZNE | False | None | None | None | None | inactive_pair |
| P003 | 1024 | Raw_vs_Accuracy-ZNE | False | None | None | None | None | inactive_pair |
| P003 | 1024 | Raw_vs_Decision-ZNE | False | None | None | None | None | inactive_pair |
| P003 | 1024 | Accuracy-ZNE_vs_Decision-ZNE | False | None | None | None | None | inactive_pair |
| P003 | 2048 | Raw_vs_Accuracy-ZNE | False | None | None | None | None | inactive_pair |
| P003 | 2048 | Raw_vs_Decision-ZNE | False | None | None | None | None | inactive_pair |
| P003 | 2048 | Accuracy-ZNE_vs_Decision-ZNE | False | None | None | None | None | inactive_pair |
| P003 | 256 | Raw_vs_Accuracy-ZNE | True | 1.0538376744567286 | 0.114983819350223 | 2.2429384200042546 | 0.555 | interval_crosses_threshold |
| P003 | 256 | Raw_vs_Decision-ZNE | True | 1.0521106506911442 | 0.1180912088102417 | 2.2522196251263313 | 0.555 | interval_crosses_threshold |
| P003 | 256 | Accuracy-ZNE_vs_Decision-ZNE | False | None | None | None | None | inactive_pair |
| P003 | 4096 | Raw_vs_Accuracy-ZNE | False | None | None | None | None | inactive_pair |
| P003 | 4096 | Raw_vs_Decision-ZNE | False | None | None | None | None | inactive_pair |
| P003 | 4096 | Accuracy-ZNE_vs_Decision-ZNE | False | None | None | None | None | inactive_pair |
| P003 | 512 | Raw_vs_Accuracy-ZNE | False | None | None | None | None | inactive_pair |
| P003 | 512 | Raw_vs_Decision-ZNE | False | None | None | None | None | inactive_pair |
| P003 | 512 | Accuracy-ZNE_vs_Decision-ZNE | False | None | None | None | None | inactive_pair |
| P003 | 8192 | Raw_vs_Accuracy-ZNE | False | None | None | None | None | inactive_pair |
| P003 | 8192 | Raw_vs_Decision-ZNE | False | None | None | None | None | inactive_pair |
| P003 | 8192 | Accuracy-ZNE_vs_Decision-ZNE | False | None | None | None | None | inactive_pair |
| P004 | 1024 | Raw_vs_Accuracy-ZNE | True | 0.17912554020811852 | 0.005978840413918136 | 0.42812495915474735 | 0.0 | interval_below_threshold |
| P004 | 1024 | Raw_vs_Decision-ZNE | True | 0.17515204696382264 | 0.006907938693108851 | 0.4195104284932783 | 0.0 | interval_below_threshold |
| P004 | 1024 | Accuracy-ZNE_vs_Decision-ZNE | False | None | None | None | None | inactive_pair |
| P004 | 2048 | Raw_vs_Accuracy-ZNE | True | 0.015621299861171445 | 0.006675997519917175 | 0.30256559580452164 | 0.0 | interval_below_threshold |
| P004 | 2048 | Raw_vs_Decision-ZNE | True | 0.012722424839061922 | 0.005647848002023924 | 0.2909659692849177 | 0.0 | interval_below_threshold |
| P004 | 2048 | Accuracy-ZNE_vs_Decision-ZNE | False | None | None | None | None | inactive_pair |
| P004 | 256 | Raw_vs_Accuracy-ZNE | True | 0.07351340102937458 | 0.0037313324481644955 | 0.32067543327626347 | 0.0 | interval_below_threshold |
| P004 | 256 | Raw_vs_Decision-ZNE | True | 0.07031511583314028 | 0.004531129300148249 | 0.31625421703318957 | 0.0 | interval_below_threshold |
| P004 | 256 | Accuracy-ZNE_vs_Decision-ZNE | False | None | None | None | None | inactive_pair |
| P004 | 4096 | Raw_vs_Accuracy-ZNE | True | 0.006179737047464709 | 0.007175411664602984 | 0.317774677298484 | 0.0 | interval_below_threshold |
| P004 | 4096 | Raw_vs_Decision-ZNE | True | 0.008033112727478501 | 0.006017834082669769 | 0.3162716410474228 | 0.0 | interval_below_threshold |
| P004 | 4096 | Accuracy-ZNE_vs_Decision-ZNE | False | None | None | None | None | inactive_pair |
| P004 | 512 | Raw_vs_Accuracy-ZNE | True | 0.1622880187562749 | 0.009443483659808913 | 0.4395887409123483 | 0.0 | interval_below_threshold |
| P004 | 512 | Raw_vs_Decision-ZNE | True | 0.16104429493827888 | 0.009510561169273143 | 0.4331367079865365 | 0.0 | interval_below_threshold |
| P004 | 512 | Accuracy-ZNE_vs_Decision-ZNE | False | None | None | None | None | inactive_pair |
| P004 | 8192 | Raw_vs_Accuracy-ZNE | True | 0.045138684969884144 | 0.006948208394718211 | 0.56642697778237 | 0.0 | interval_below_threshold |
| P004 | 8192 | Raw_vs_Decision-ZNE | True | 0.04214223266477211 | 0.011452376441009311 | 0.5534697865856194 | 0.0 | interval_below_threshold |
| P004 | 8192 | Accuracy-ZNE_vs_Decision-ZNE | False | None | None | None | None | inactive_pair |

All covariance widths, shrinkage comparisons, subsamples, relations and underlying bootstrap arrays are saved in a3_audit_evidence/. See audit_index.json for source hashes and schema.
