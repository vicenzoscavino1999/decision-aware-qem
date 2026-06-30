# CDR P0 Validity Evidence

Date: 2026-06-24

Scope: non-confirmatory graph seeds only; no C-ids, no pipeline run, no freeze update.

## Summary

| metric | value |
|---|---:|
| instances | 6 |
| instances improved | 6 |
| instances passed all validity checks | 6 |
| training_exact_std range | [0.27766953544136797, 0.3744478653648967] |
| abs(slope) range | [1.0682280305898002, 1.155378985696129] |
| error_mitigated/error_noisy range | [0.16878945615558924, 0.8508032888712009] |

## Instance Evidence

| instance | graph_seed | training_exact_std | target_bracketed | abs_slope | error_noisy | error_mitigated | ratio | pass |
|---|---:|---:|---|---:|---:|---:|---:|---|
| CDR_P0_VALIDITY_S001 | 260616 | 0.31288499439090417 | true | 1.0682280305898002 | 0.27635149976010887 | 0.0719026803912346 | 0.2601855986077543 | true |
| CDR_P0_VALIDITY_S002 | 260617 | 0.3192216383938204 | true | 1.1060193200853072 | 0.16990618726010887 | 0.044205038385721096 | 0.26017321145608274 | true |
| CDR_P0_VALIDITY_S003 | 260618 | 0.3744478653648967 | true | 1.155378985696129 | 0.10899999304146668 | 0.09273755256661786 | 0.8508032888712009 | true |
| CDR_P0_VALIDITY_S004 | 260619 | 0.27766953544136797 | true | 1.1036103947864186 | 0.2929566079126644 | 0.11988411463143933 | 0.4092214047862642 | true |
| CDR_P0_VALIDITY_S005 | 260620 | 0.3483584390916934 | true | 1.098715821224029 | 0.2580773481669496 | 0.05604674348282579 | 0.21717033238643357 | true |
| CDR_P0_VALIDITY_S006 | 260621 | 0.33428134199261617 | true | 1.1232946743105385 | 0.1518742495453509 | 0.02563477198479802 | 0.16878945615558924 | true |

All six instances pass the pre-fixed P0 validity bar: nonzero training spread, target inside the training exact range, CDR improves over the noisy target estimate, and the fitted slope is non-degenerate.
