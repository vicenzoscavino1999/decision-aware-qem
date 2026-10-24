# Proof Of Mechanism Result

No confirmatory C-ids are used. Instances are selected by ideal epsilon only.

## Headline: CDR Affine Control

The cleanest proof-of-mechanism result is the CDR negative control. Across all aggregate budgets, CDR sharply lowers estimator MSE while leaving the decision statistic unchanged relative to Raw:

| budget | Raw MSE | CDR MSE | MSE drop factor | Raw R | CDR R | Raw GRI | CDR GRI |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 768 | 0.399290456514 | 0.00927751866011 | 43.04 | 0.491666666667 | 0.491666666667 | 0.517616702852 | 0.517616702852 |
| 1536 | 0.395805926886 | 0.00543443498906 | 72.85 | 0.470833333333 | 0.470833333333 | 0.448916256498 | 0.448916256498 |
| 3072 | 0.3935056566 | 0.00313695405859 | 125.44 | 0.354166666667 | 0.354166666667 | 0.390456121725 | 0.390456121725 |
| 6144 | 0.393846083261 | 0.00218868772838 | 179.94 | 0.366666666667 | 0.366666666667 | 0.349640111612 | 0.349640111612 |

Interpretation: CDR is a global positive affine correction of Raw, `a*x+b`. The offset cancels in gaps and the positive scale cancels in the standardized gap statistic, so the gap-kernel decision risk is exactly Raw. This is the sharpest evidence in this artifact that lower MSE is not the same object as better decision performance.

## Selected Instances

| instance | epsilon_opt | graph_seed |
|:---|---:|---:|
| POM_001 | 0.00906606065434 | 2069068057 |
| POM_003 | 0.0106646883413 | 308104174 |
| POM_004 | 0.0121524306207 | 1721104813 |
| POM_012 | 0.00038970610069 | 768728133 |
| POM_015 | 0.0128871124524 | 1653595009 |
| POM_017 | 0.00939103254428 | 1825628384 |
| POM_018 | 0.0164439914235 | 2035330806 |
| POM_022 | 0.00193665788097 | 918575863 |

## PEC Coexistence: Aggregate Present, Instance-Dependent

The aggregate PEC result shows the intended coexistence pattern: PEC has lower MSE than Raw but worse empirical decision failure and worse gap-kernel risk. This is present in the aggregate table at all budgets.

| budget | Raw MSE | PEC MSE | Raw R | PEC R | Raw GRI | PEC GRI | Raw I_hat | PEC I_hat |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 768 | 0.399290456514 | 0.309850664514 | 0.491666666667 | 0.841666666667 | 0.517616702852 | 0.870384516811 | 0.142579188256 | 0.00221234001652 |
| 1536 | 0.395805926886 | 0.151722237252 | 0.470833333333 | 0.85 | 0.448916256498 | 0.817833427045 | 0.285158376512 | 0.00464591403469 |
| 3072 | 0.3935056566 | 0.0750711618482 | 0.354166666667 | 0.770833333333 | 0.390456121725 | 0.753184493506 | 0.570316753025 | 0.00929182806938 |
| 6144 | 0.393846083261 | 0.0381852263554 | 0.366666666667 | 0.666666666667 | 0.349640111612 | 0.675092833863 | 1.14063350605 | 0.0185836561388 |

### Per-instance coexistence (reproducible)

Re-derived from the proof-of-mechanism machinery by `experiments/proof_of_mechanism_coexistence_table.py`; per-instance booleans are in `results/proof_of_mechanism/coexistence_by_instance.csv`.

| budget | MSE_PEC<Raw | GRI_PEC>Raw (decision worse) | Coexistence (both) | instances without coexistence |
|---:|:---:|:---:|:---:|:---|
| 768 | 5/8 | 8/8 | 5/8 | POM_004, POM_015, POM_018 |
| 1536 | 7/8 | 8/8 | 7/8 | POM_004 |
| 3072 | 8/8 | 7/8 | 7/8 | POM_004 |
| 6144 | 8/8 | 7/8 | 7/8 | POM_004 |

Reading: the decision-worsening of PEC (`GRI_PEC>Raw`) is near-universal: 8/8, 8/8, 7/8, 7/8. The full coexistence pattern, lower MSE and worse decision simultaneously, holds in a strong majority: 5/8 at the lowest budget and 7/8 thereafter. At budget 768 the count is lower only because PEC's gamma-squared sampling variance keeps `MSE_PEC` above Raw in three instances; once the budget grows, PEC's unbiasedness wins MSE and coexistence appears. `POM_004` is the consistent exception, for two distinct reasons at opposite ends of the budget range. It has the lowest Raw MSE of the eight instances (about 0.10), so at the two lowest budgets PEC's gamma-squared sampling variance cannot beat Raw on MSE and the MSE leg of coexistence fails. At the two highest budgets PEC's unbiasedness recovers a better decision than Raw's residual decision-adverse bias: here Raw GRI is in fact the highest of the eight (rising to 0.85) while PEC GRI falls to 0.68, so the decision leg fails. Coexistence needs both a Raw bias large enough to spoil the active gaps and a budget high enough for PEC to pay its variance, and `POM_004` never satisfies both at once, exactly as the decision-kernel geometry predicts.

## Full Aggregate Table

| budget | method | MSE | MSE CI | R empirical | R CI | GRI | I_hat |
|---:|:---|---:|:---|---:|:---|---:|---:|
| 768 | Raw | 0.399290456514 | [0.37620642206, 0.42145280672] | 0.491666666667 | [0.429166666667, 0.554166666667] | 0.517616702852 | 0.142579188256 |
| 768 | Accuracy-ZNE | 0.0990049678425 | [0.0929270165342, 0.104471983525] | 0.666666666667 | [0.604166666667, 0.725] | 0.686879416301 | 0.0216637467109 |
| 768 | Decision-ZNE | 0.0972476037194 | [0.0913518131391, 0.102919767299] | 0.670833333333 | [0.608333333333, 0.729166666667] | 0.686551180982 | 0.0216793588226 |
| 768 | CDR | 0.00927751866011 | [0.00890430798274, 0.00963158990082] | 0.491666666667 | [0.425, 0.558333333333] | 0.517616702852 | 0.142579188256 |
| 768 | PEC | 0.309850664514 | [0.297662084718, 0.322639026418] | 0.841666666667 | [0.795833333333, 0.883333333333] | 0.870384516811 | 0.00221234001652 |
| 1536 | Raw | 0.395805926886 | [0.374849301548, 0.419093309434] | 0.470833333333 | [0.4125, 0.5334375] | 0.448916256498 | 0.285158376512 |
| 1536 | Accuracy-ZNE | 0.0826703083125 | [0.0769177572921, 0.0888573125136] | 0.6 | [0.5375, 0.658333333333] | 0.609385566507 | 0.0433274934218 |
| 1536 | Decision-ZNE | 0.0809195656592 | [0.0757799078597, 0.086198912138] | 0.5875 | [0.524895833333, 0.65] | 0.608882034229 | 0.0433587176452 |
| 1536 | CDR | 0.00543443498906 | [0.00520151537379, 0.00564344617131] | 0.470833333333 | [0.404166666667, 0.533333333333] | 0.448916256498 | 0.285158376512 |
| 1536 | PEC | 0.151722237252 | [0.145274699788, 0.158259943478] | 0.85 | [0.808229166667, 0.891666666667] | 0.817833427045 | 0.00464591403469 |
| 3072 | Raw | 0.3935056566 | [0.370260331439, 0.413828039289] | 0.354166666667 | [0.291666666667, 0.416666666667] | 0.390456121725 | 0.570316753025 |
| 3072 | Accuracy-ZNE | 0.075308109784 | [0.0700060666499, 0.0804903123755] | 0.5375 | [0.475, 0.6] | 0.529558139326 | 0.0866549868437 |
| 3072 | Decision-ZNE | 0.0735941490944 | [0.068743592618, 0.079000496691] | 0.533333333333 | [0.470729166667, 0.5959375] | 0.52888212128 | 0.0867174352904 |
| 3072 | CDR | 0.00313695405859 | [0.00302727927824, 0.0032591493993] | 0.354166666667 | [0.295833333333, 0.416666666667] | 0.390456121725 | 0.570316753025 |
| 3072 | PEC | 0.0750711618482 | [0.0719138616145, 0.0783143833455] | 0.770833333333 | [0.7125, 0.825] | 0.753184493506 | 0.00929182806938 |
| 6144 | Raw | 0.393846083261 | [0.370810859497, 0.415838646156] | 0.366666666667 | [0.308229166667, 0.425] | 0.349640111612 | 1.14063350605 |
| 6144 | Accuracy-ZNE | 0.0721809900211 | [0.0668645378833, 0.0774248196217] | 0.483333333333 | [0.420833333333, 0.545833333333] | 0.451550821761 | 0.173309973687 |
| 6144 | Decision-ZNE | 0.0703954416316 | [0.0651865541282, 0.0756347599045] | 0.466666666667 | [0.4, 0.529166666667] | 0.450721990686 | 0.173434870581 |
| 6144 | CDR | 0.00218868772838 | [0.00210894425861, 0.00227010402868] | 0.366666666667 | [0.304166666667, 0.429166666667] | 0.349640111612 | 1.14063350605 |
| 6144 | PEC | 0.0381852263554 | [0.0366965747121, 0.0397388617531] | 0.666666666667 | [0.608333333333, 0.725] | 0.675092833863 | 0.0185836561388 |

## Model Caveat

The PEC reported here is the scalar-overhead proof model from section 1835 and from the PEC signature theorem: `Sigma_PEC = gamma^2 * Sigma_ideal` under matched total shot cost. This is the intended analytic mechanism check. Separately, the genuine quasi-probabilistic PEC de-risk already verified the same decision-worsening mechanism through `lambda * gamma > 1`; the two checks are consistent but not identical implementations.

## Section 1835 Status

The phenomenon required by section 1835 is present at the aggregate level and is explained by the gap-kernel diagnostics:

- PEC coexistence (per-instance): 5/8, 7/8, 7/8, 7/8 at budgets 768/1536/3072/6144; decision-worsening alone (`GRI_PEC>Raw`): 8/8, 8/8, 7/8, 7/8.
- CDR affine-control budgets: `[768, 1536, 3072, 6144]`
- gap-kernel explained budgets: `[768, 1536, 3072, 6144]`

The correct claim is not "PEC always worsens the decision." The correct claim is that MSE improvement and decision improvement are distinct: CDR demonstrates this exactly through affine decision-flatness, and PEC demonstrates coexistence in the aggregate with instance-dependent geometry.

## Death Criteria

- margins_nondegenerate: PASS
- pec_effect_persists_matched_shot: PASS
- randomized_execution_order: PASS
- gap_kernel_explains: PASS
- not_affine_control_only: PASS
