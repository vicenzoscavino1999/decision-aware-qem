# A3 Finite-Sample Sigmahat Audit Smoke

Diagnostic only: not canonical, not part of verify/reference.

- bootstrap_replicates: 200
- bootstrap_CI: 0.95

## Active Covariance Bootstrap CI Widths

| cell | method | B | active_dim | max_cov_width | max_diag_width | max_offdiag_width |
|---|---|---:|---:|---:|---:|---:|
| P001 | Raw | 256 | 3 | 0.0106928 | 0.0106928 | 0.00869767 |
| P001 | Accuracy-ZNE | 256 | 5 | 0.0283715 | 0.0283715 | 0.0245385 |
| P001 | Decision-ZNE | 256 | 5 | 0.0280009 | 0.0280009 | 0.0215067 |
| P001 | Raw | 512 | 3 | 0.00620786 | 0.00620786 | 0.00534201 |
| P001 | Accuracy-ZNE | 512 | 3 | 0.0130498 | 0.0130498 | 0.01085 |
| P001 | Decision-ZNE | 512 | 3 | 0.012953 | 0.012953 | 0.0112818 |
| P001 | Raw | 1024 | 3 | 0.00251318 | 0.00251318 | 0.00204774 |
| P001 | Accuracy-ZNE | 1024 | 3 | 0.00658786 | 0.00658786 | 0.00493787 |
| P001 | Decision-ZNE | 1024 | 3 | 0.00579888 | 0.00579888 | 0.00430098 |
| P001 | Raw | 2048 | 3 | 0.00109734 | 0.00109734 | 0.000941905 |
| P001 | Accuracy-ZNE | 2048 | 3 | 0.00283912 | 0.00283912 | 0.00251192 |
| P001 | Decision-ZNE | 2048 | 3 | 0.0028376 | 0.0028376 | 0.00252137 |
| P001 | Raw | 4096 | 3 | 0.000693816 | 0.000693816 | 0.000562539 |
| P001 | Accuracy-ZNE | 4096 | 3 | 0.00184394 | 0.00184394 | 0.00118534 |
| P001 | Decision-ZNE | 4096 | 3 | 0.00148163 | 0.00148163 | 0.00112881 |
| P001 | Raw | 8192 | 3 | 0.00029708 | 0.00029708 | 0.000226639 |
| P001 | Accuracy-ZNE | 8192 | 3 | 0.000752969 | 0.000752969 | 0.000528266 |
| P001 | Decision-ZNE | 8192 | 3 | 0.000702725 | 0.000702725 | 0.000550852 |
| P002 | Raw | 256 | 6 | 0.0126754 | 0.0126754 | 0.0105234 |
| P002 | Accuracy-ZNE | 256 | 6 | 0.0304412 | 0.0304412 | 0.0220055 |
| P002 | Decision-ZNE | 256 | 6 | 0.0333883 | 0.0333883 | 0.0246515 |
| P002 | Raw | 512 | 5 | 0.00682646 | 0.00682646 | 0.00656502 |
| P002 | Accuracy-ZNE | 512 | 6 | 0.0156161 | 0.0156161 | 0.0143318 |
| P002 | Decision-ZNE | 512 | 6 | 0.01871 | 0.01871 | 0.0128691 |
| P002 | Raw | 1024 | 5 | 0.00278715 | 0.00278715 | 0.00251082 |
| P002 | Accuracy-ZNE | 1024 | 5 | 0.00596794 | 0.00596794 | 0.00571501 |
| P002 | Decision-ZNE | 1024 | 5 | 0.0061375 | 0.0061375 | 0.00491739 |
| P002 | Raw | 2048 | 3 | 0.00213032 | 0.00213032 | 0.00155753 |
| P002 | Accuracy-ZNE | 2048 | 5 | 0.00328201 | 0.00328201 | 0.00291232 |
| P002 | Decision-ZNE | 2048 | 5 | 0.00311524 | 0.00311524 | 0.0031038 |
| P002 | Raw | 4096 | 3 | 0.00106792 | 0.00106792 | 0.000804449 |
| P002 | Accuracy-ZNE | 4096 | 3 | 0.00207872 | 0.00207872 | 0.00150269 |
| P002 | Decision-ZNE | 4096 | 3 | 0.00200975 | 0.00200975 | 0.00150856 |
| P002 | Raw | 8192 | 3 | 0.000429581 | 0.000429581 | 0.00033934 |
| P002 | Accuracy-ZNE | 8192 | 3 | 0.000889974 | 0.000889974 | 0.000681751 |
| P002 | Decision-ZNE | 8192 | 3 | 0.000948118 | 0.000948118 | 0.000731323 |
| P003 | Raw | 256 | 3 | 0.014057 | 0.014057 | 0.0110039 |
| P003 | Accuracy-ZNE | 256 | 3 | 0.0277384 | 0.0277384 | 0.0200184 |
| P003 | Decision-ZNE | 256 | 3 | 0.0315381 | 0.0315381 | 0.0226649 |
| P003 | Raw | 512 | 3 | 0.00649838 | 0.00649838 | 0.00541244 |
| P003 | Accuracy-ZNE | 512 | 3 | 0.0146066 | 0.0146066 | 0.0108547 |
| P003 | Decision-ZNE | 512 | 3 | 0.0155079 | 0.0155079 | 0.0106942 |
| P003 | Raw | 1024 | 3 | 0.00285466 | 0.00285466 | 0.00239336 |
| P003 | Accuracy-ZNE | 1024 | 3 | 0.0077512 | 0.0077512 | 0.00631135 |
| P003 | Decision-ZNE | 1024 | 3 | 0.00778141 | 0.00778141 | 0.00611213 |
| P003 | Raw | 2048 | 3 | 0.00178919 | 0.00178919 | 0.00153302 |
| P003 | Accuracy-ZNE | 2048 | 3 | 0.00412413 | 0.00412413 | 0.00369162 |
| P003 | Decision-ZNE | 2048 | 3 | 0.00396374 | 0.00396374 | 0.00341397 |
| P003 | Raw | 4096 | 3 | 0.000814836 | 0.000814836 | 0.000683547 |
| P003 | Accuracy-ZNE | 4096 | 3 | 0.00200395 | 0.00200395 | 0.00154564 |
| P003 | Decision-ZNE | 4096 | 3 | 0.00188741 | 0.00188741 | 0.00168155 |
| P003 | Raw | 8192 | 3 | 0.000443011 | 0.000443011 | 0.000317378 |
| P003 | Accuracy-ZNE | 8192 | 3 | 0.000798109 | 0.000798109 | 0.000616331 |
| P003 | Decision-ZNE | 8192 | 3 | 0.000839266 | 0.000839266 | 0.000691728 |
| P004 | Raw | 256 | 3 | 0.0106999 | 0.0106999 | 0.00950556 |
| P004 | Accuracy-ZNE | 256 | 3 | 0.0275823 | 0.0275823 | 0.0221748 |
| P004 | Decision-ZNE | 256 | 3 | 0.0269612 | 0.0269612 | 0.0230115 |
| P004 | Raw | 512 | 3 | 0.00534173 | 0.00534173 | 0.0049904 |
| P004 | Accuracy-ZNE | 512 | 3 | 0.0139798 | 0.0139798 | 0.0108689 |
| P004 | Decision-ZNE | 512 | 3 | 0.0131362 | 0.0131362 | 0.0106448 |
| P004 | Raw | 1024 | 3 | 0.00265457 | 0.00265457 | 0.00224852 |
| P004 | Accuracy-ZNE | 1024 | 3 | 0.00577055 | 0.00577055 | 0.00498777 |
| P004 | Decision-ZNE | 1024 | 3 | 0.00588366 | 0.00588366 | 0.00527478 |
| P004 | Raw | 2048 | 3 | 0.00162466 | 0.00162466 | 0.00132007 |
| P004 | Accuracy-ZNE | 2048 | 3 | 0.00369421 | 0.00369421 | 0.00258781 |
| P004 | Decision-ZNE | 2048 | 3 | 0.00370498 | 0.00370498 | 0.00286458 |
| P004 | Raw | 4096 | 3 | 0.000703994 | 0.000703994 | 0.000524994 |
| P004 | Accuracy-ZNE | 4096 | 3 | 0.0017191 | 0.0017191 | 0.00132835 |
| P004 | Decision-ZNE | 4096 | 3 | 0.00157418 | 0.00157418 | 0.0013501 |
| P004 | Raw | 8192 | 3 | 0.000466273 | 0.000466273 | 0.000320128 |
| P004 | Accuracy-ZNE | 8192 | 3 | 0.000908246 | 0.000908246 | 0.000734155 |
| P004 | Decision-ZNE | 8192 | 3 | 0.000874932 | 0.000874932 | 0.000680539 |

## Shrinkage Sensitivity

| cell | method | B | risk_LW | risk_sample_cov | abs_shift |
|---|---|---:|---:|---:|---:|
| P001 | Raw | 256 | 0.470866 | 0.467573 | 0.00329299 |
| P001 | Accuracy-ZNE | 256 | 0.623365 | 0.618101 | 0.00526406 |
| P001 | Decision-ZNE | 256 | 0.623252 | 0.618009 | 0.00524324 |
| P001 | Raw | 512 | 0.338797 | 0.336852 | 0.00194531 |
| P001 | Accuracy-ZNE | 512 | 0.499925 | 0.49608 | 0.00384551 |
| P001 | Decision-ZNE | 512 | 0.499945 | 0.496102 | 0.00384341 |
| P001 | Raw | 1024 | 0.206467 | 0.206098 | 0.000368861 |
| P001 | Accuracy-ZNE | 1024 | 0.364105 | 0.362124 | 0.00198071 |
| P001 | Decision-ZNE | 1024 | 0.364089 | 0.362092 | 0.00199639 |
| P001 | Raw | 2048 | 0.0970023 | 0.0971448 | 0.000142531 |
| P001 | Accuracy-ZNE | 2048 | 0.231 | 0.230646 | 0.000353804 |
| P001 | Decision-ZNE | 2048 | 0.231251 | 0.230894 | 0.000356884 |
| P001 | Raw | 4096 | 0.0319471 | 0.0321479 | 0.00020082 |
| P001 | Accuracy-ZNE | 4096 | 0.126091 | 0.126476 | 0.000385183 |
| P001 | Decision-ZNE | 4096 | 0.126035 | 0.126414 | 0.000379858 |
| P001 | Raw | 8192 | 0.00341349 | 0.00343689 | 2.33962e-05 |
| P001 | Accuracy-ZNE | 8192 | 0.040285 | 0.0404966 | 0.000211613 |
| P001 | Decision-ZNE | 8192 | 0.0404236 | 0.0406329 | 0.000209326 |
| P002 | Raw | 256 | 0.204387 | 0.202762 | 0.0016252 |
| P002 | Accuracy-ZNE | 256 | 0.46059 | 0.455916 | 0.00467441 |
| P002 | Decision-ZNE | 256 | 0.460674 | 0.45596 | 0.0047143 |
| P002 | Raw | 512 | 0.0481563 | 0.0482562 | 9.99335e-05 |
| P002 | Accuracy-ZNE | 512 | 0.238809 | 0.236675 | 0.0021338 |
| P002 | Decision-ZNE | 512 | 0.23866 | 0.236497 | 0.00216271 |
| P002 | Raw | 1024 | 0.0030448 | 0.00308634 | 4.15415e-05 |
| P002 | Accuracy-ZNE | 1024 | 0.0565724 | 0.0563829 | 0.000189515 |
| P002 | Decision-ZNE | 1024 | 0.0567333 | 0.0565323 | 0.000200995 |
| P002 | Raw | 2048 | 3.83314e-05 | 3.9689e-05 | 1.35763e-06 |
| P002 | Accuracy-ZNE | 2048 | 0.00468296 | 0.00472138 | 3.84197e-05 |
| P002 | Decision-ZNE | 2048 | 0.0048149 | 0.00485673 | 4.18331e-05 |
| P002 | Raw | 4096 | 1.14472e-08 | 1.21192e-08 | 6.71992e-10 |
| P002 | Accuracy-ZNE | 4096 | 0.000129459 | 0.000132789 | 3.33023e-06 |
| P002 | Decision-ZNE | 4096 | 0.000130433 | 0.00013383 | 3.39657e-06 |
| P002 | Raw | 8192 | 1.1402e-13 | 1.42331e-13 | 2.83107e-14 |
| P002 | Accuracy-ZNE | 8192 | 6.19669e-07 | 6.86189e-07 | 6.65193e-08 |
| P002 | Decision-ZNE | 8192 | 6.349e-07 | 7.03534e-07 | 6.86345e-08 |
| P003 | Raw | 256 | 0.000213495 | 0.000221783 | 8.28817e-06 |
| P003 | Accuracy-ZNE | 256 | 0.0139337 | 0.0141842 | 0.000250532 |
| P003 | Decision-ZNE | 256 | 0.013917 | 0.0141679 | 0.000250897 |
| P003 | Raw | 512 | 7.15433e-08 | 7.36802e-08 | 2.13695e-09 |
| P003 | Accuracy-ZNE | 512 | 0.00043479 | 0.000446547 | 1.17574e-05 |
| P003 | Decision-ZNE | 512 | 0.000434978 | 0.000446666 | 1.16879e-05 |
| P003 | Raw | 1024 | 2.59792e-14 | 2.85327e-14 | 2.55351e-15 |
| P003 | Accuracy-ZNE | 1024 | 5.95485e-07 | 6.27716e-07 | 3.22308e-08 |
| P003 | Decision-ZNE | 1024 | 6.05836e-07 | 6.3852e-07 | 3.26838e-08 |
| P003 | Raw | 2048 | 0 | 0 | 0 |
| P003 | Accuracy-ZNE | 2048 | 3.42126e-12 | 3.6896e-12 | 2.68341e-13 |
| P003 | Decision-ZNE | 2048 | 3.20799e-12 | 3.4549e-12 | 2.46914e-13 |
| P003 | Raw | 4096 | 0 | 0 | 0 |
| P003 | Accuracy-ZNE | 4096 | 0 | 0 | 0 |
| P003 | Decision-ZNE | 4096 | 0 | 0 | 0 |
| P003 | Raw | 8192 | 0 | 0 | 0 |
| P003 | Accuracy-ZNE | 8192 | 0 | 0 | 0 |
| P003 | Decision-ZNE | 8192 | 0 | 0 | 0 |
| P004 | Raw | 256 | 0.339518 | 0.339276 | 0.000241828 |
| P004 | Accuracy-ZNE | 256 | 0.41921 | 0.417981 | 0.00122889 |
| P004 | Decision-ZNE | 256 | 0.419064 | 0.417826 | 0.00123806 |
| P004 | Raw | 512 | 0.266434 | 0.266315 | 0.000118581 |
| P004 | Accuracy-ZNE | 512 | 0.352821 | 0.352495 | 0.000325644 |
| P004 | Decision-ZNE | 512 | 0.352747 | 0.35242 | 0.000326292 |
| P004 | Raw | 1024 | 0.185975 | 0.18585 | 0.000124761 |
| P004 | Accuracy-ZNE | 1024 | 0.286994 | 0.287153 | 0.000159403 |
| P004 | Decision-ZNE | 1024 | 0.28676 | 0.286906 | 0.000146706 |
| P004 | Raw | 2048 | 0.1129 | 0.112759 | 0.000140584 |
| P004 | Accuracy-ZNE | 2048 | 0.215744 | 0.215887 | 0.000142661 |
| P004 | Decision-ZNE | 2048 | 0.215555 | 0.215685 | 0.000129803 |
| P004 | Raw | 4096 | 0.0468482 | 0.0469391 | 9.09332e-05 |
| P004 | Accuracy-ZNE | 4096 | 0.13794 | 0.138229 | 0.000289475 |
| P004 | Decision-ZNE | 4096 | 0.137823 | 0.138103 | 0.000280505 |
| P004 | Raw | 8192 | 0.00788667 | 0.00788998 | 3.30881e-06 |
| P004 | Accuracy-ZNE | 8192 | 0.0627506 | 0.0631227 | 0.000372107 |
| P004 | Decision-ZNE | 8192 | 0.0626446 | 0.0630049 | 0.000360264 |

## Replicate Count Sufficiency

| cell | method | B | subsample_R | risk_subsample | risk_full_R | abs_shift |
|---|---|---:|---:|---:|---:|---:|
| P001 | Raw | 256 | 50 | 0.477988 | 0.470866 | 0.00712192 |
| P001 | Raw | 256 | 100 | 0.473047 | 0.470866 | 0.00218038 |
| P001 | Raw | 256 | 200 | 0.470866 | 0.470866 | 6.66134e-16 |
| P001 | Accuracy-ZNE | 256 | 50 | 0.623758 | 0.623365 | 0.000393122 |
| P001 | Accuracy-ZNE | 256 | 100 | 0.641626 | 0.623365 | 0.018261 |
| P001 | Accuracy-ZNE | 256 | 200 | 0.623365 | 0.623365 | 2.22045e-16 |
| P001 | Decision-ZNE | 256 | 50 | 0.652118 | 0.623252 | 0.0288661 |
| P001 | Decision-ZNE | 256 | 100 | 0.60811 | 0.623252 | 0.0151419 |
| P001 | Decision-ZNE | 256 | 200 | 0.623252 | 0.623252 | 2.22045e-16 |
| P001 | Raw | 512 | 50 | 0.362626 | 0.338797 | 0.0238291 |
| P001 | Raw | 512 | 100 | 0.338649 | 0.338797 | 0.000148742 |
| P001 | Raw | 512 | 200 | 0.338797 | 0.338797 | 4.44089e-16 |
| P001 | Accuracy-ZNE | 512 | 50 | 0.501415 | 0.499925 | 0.00149014 |
| P001 | Accuracy-ZNE | 512 | 100 | 0.500151 | 0.499925 | 0.00022522 |
| P001 | Accuracy-ZNE | 512 | 200 | 0.499925 | 0.499925 | 2.22045e-16 |
| P001 | Decision-ZNE | 512 | 50 | 0.507892 | 0.499945 | 0.0079469 |
| P001 | Decision-ZNE | 512 | 100 | 0.512415 | 0.499945 | 0.0124695 |
| P001 | Decision-ZNE | 512 | 200 | 0.499945 | 0.499945 | 2.22045e-16 |
| P001 | Raw | 1024 | 50 | 0.20575 | 0.206467 | 0.000716892 |
| P001 | Raw | 1024 | 100 | 0.190932 | 0.206467 | 0.0155346 |
| P001 | Raw | 1024 | 200 | 0.206467 | 0.206467 | 3.33067e-16 |
| P001 | Accuracy-ZNE | 1024 | 50 | 0.379089 | 0.364105 | 0.0149839 |
| P001 | Accuracy-ZNE | 1024 | 100 | 0.362669 | 0.364105 | 0.00143595 |
| P001 | Accuracy-ZNE | 1024 | 200 | 0.364105 | 0.364105 | 2.22045e-16 |
| P001 | Decision-ZNE | 1024 | 50 | 0.37553 | 0.364089 | 0.0114411 |
| P001 | Decision-ZNE | 1024 | 100 | 0.372154 | 0.364089 | 0.00806549 |
| P001 | Decision-ZNE | 1024 | 200 | 0.364089 | 0.364089 | 4.44089e-16 |
| P001 | Raw | 2048 | 50 | 0.117886 | 0.0970023 | 0.0208836 |
| P001 | Raw | 2048 | 100 | 0.082287 | 0.0970023 | 0.0147152 |
| P001 | Raw | 2048 | 200 | 0.0970023 | 0.0970023 | 3.33067e-16 |
| P001 | Accuracy-ZNE | 2048 | 50 | 0.239352 | 0.231 | 0.0083522 |
| P001 | Accuracy-ZNE | 2048 | 100 | 0.227687 | 0.231 | 0.00331272 |
| P001 | Accuracy-ZNE | 2048 | 200 | 0.231 | 0.231 | 2.22045e-16 |
| P001 | Decision-ZNE | 2048 | 50 | 0.220924 | 0.231251 | 0.0103262 |
| P001 | Decision-ZNE | 2048 | 100 | 0.243758 | 0.231251 | 0.0125071 |
| P001 | Decision-ZNE | 2048 | 200 | 0.231251 | 0.231251 | 2.22045e-16 |
| P001 | Raw | 4096 | 50 | 0.0393068 | 0.0319471 | 0.00735965 |
| P001 | Raw | 4096 | 100 | 0.0304156 | 0.0319471 | 0.00153157 |
| P001 | Raw | 4096 | 200 | 0.0319471 | 0.0319471 | 0 |
| P001 | Accuracy-ZNE | 4096 | 50 | 0.075169 | 0.126091 | 0.0509223 |
| P001 | Accuracy-ZNE | 4096 | 100 | 0.156582 | 0.126091 | 0.0304902 |
| P001 | Accuracy-ZNE | 4096 | 200 | 0.126091 | 0.126091 | 1.11022e-16 |
| P001 | Decision-ZNE | 4096 | 50 | 0.14465 | 0.126035 | 0.0186153 |
| P001 | Decision-ZNE | 4096 | 100 | 0.102603 | 0.126035 | 0.0234313 |
| P001 | Decision-ZNE | 4096 | 200 | 0.126035 | 0.126035 | 3.33067e-16 |
| P001 | Raw | 8192 | 50 | 0.0033771 | 0.00341349 | 3.63974e-05 |
| P001 | Raw | 8192 | 100 | 0.00194128 | 0.00341349 | 0.00147221 |
| P001 | Raw | 8192 | 200 | 0.00341349 | 0.00341349 | 0 |
| P001 | Accuracy-ZNE | 8192 | 50 | 0.0405587 | 0.040285 | 0.000273709 |
| P001 | Accuracy-ZNE | 8192 | 100 | 0.0442097 | 0.040285 | 0.00392475 |
| P001 | Accuracy-ZNE | 8192 | 200 | 0.040285 | 0.040285 | 0 |
| P001 | Decision-ZNE | 8192 | 50 | 0.0305537 | 0.0404236 | 0.00986986 |
| P001 | Decision-ZNE | 8192 | 100 | 0.0352482 | 0.0404236 | 0.00517542 |
| P001 | Decision-ZNE | 8192 | 200 | 0.0404236 | 0.0404236 | 1.11022e-16 |
| P002 | Raw | 256 | 50 | 0.222998 | 0.204387 | 0.0186109 |
| P002 | Raw | 256 | 100 | 0.219783 | 0.204387 | 0.0153958 |
| P002 | Raw | 256 | 200 | 0.204387 | 0.204387 | 3.33067e-16 |
| P002 | Accuracy-ZNE | 256 | 50 | 0.438331 | 0.46059 | 0.0222596 |
| P002 | Accuracy-ZNE | 256 | 100 | 0.452976 | 0.46059 | 0.00761427 |
| P002 | Accuracy-ZNE | 256 | 200 | 0.46059 | 0.46059 | 1.11022e-16 |
| P002 | Decision-ZNE | 256 | 50 | 0.489114 | 0.460674 | 0.0284397 |
| P002 | Decision-ZNE | 256 | 100 | 0.468912 | 0.460674 | 0.00823765 |
| P002 | Decision-ZNE | 256 | 200 | 0.460674 | 0.460674 | 2.22045e-16 |
| P002 | Raw | 512 | 50 | 0.0560627 | 0.0481563 | 0.00790638 |
| P002 | Raw | 512 | 100 | 0.0569782 | 0.0481563 | 0.00882189 |
| P002 | Raw | 512 | 200 | 0.0481563 | 0.0481563 | 0 |
| P002 | Accuracy-ZNE | 512 | 50 | 0.223466 | 0.238809 | 0.0153424 |
| P002 | Accuracy-ZNE | 512 | 100 | 0.239463 | 0.238809 | 0.00065454 |
| P002 | Accuracy-ZNE | 512 | 200 | 0.238809 | 0.238809 | 0 |
| P002 | Decision-ZNE | 512 | 50 | 0.216677 | 0.23866 | 0.0219828 |
| P002 | Decision-ZNE | 512 | 100 | 0.262959 | 0.23866 | 0.0242996 |
| P002 | Decision-ZNE | 512 | 200 | 0.23866 | 0.23866 | 1.11022e-16 |
| P002 | Raw | 1024 | 50 | 0.0025112 | 0.0030448 | 0.000533595 |
| P002 | Raw | 1024 | 100 | 0.00436551 | 0.0030448 | 0.00132071 |
| P002 | Raw | 1024 | 200 | 0.0030448 | 0.0030448 | 0 |
| P002 | Accuracy-ZNE | 1024 | 50 | 0.0529236 | 0.0565724 | 0.00364887 |
| P002 | Accuracy-ZNE | 1024 | 100 | 0.0649224 | 0.0565724 | 0.00834994 |
| P002 | Accuracy-ZNE | 1024 | 200 | 0.0565724 | 0.0565724 | 1.11022e-16 |
| P002 | Decision-ZNE | 1024 | 50 | 0.0490918 | 0.0567333 | 0.0076415 |
| P002 | Decision-ZNE | 1024 | 100 | 0.060833 | 0.0567333 | 0.00409967 |
| P002 | Decision-ZNE | 1024 | 200 | 0.0567333 | 0.0567333 | 2.22045e-16 |
| P002 | Raw | 2048 | 50 | 7.6094e-05 | 3.83314e-05 | 3.77626e-05 |
| P002 | Raw | 2048 | 100 | 8.75099e-05 | 3.83314e-05 | 4.91785e-05 |
| P002 | Raw | 2048 | 200 | 3.83314e-05 | 3.83314e-05 | 0 |
| P002 | Accuracy-ZNE | 2048 | 50 | 0.0084927 | 0.00468296 | 0.00380974 |
| P002 | Accuracy-ZNE | 2048 | 100 | 0.00645839 | 0.00468296 | 0.00177543 |
| P002 | Accuracy-ZNE | 2048 | 200 | 0.00468296 | 0.00468296 | 0 |
| P002 | Decision-ZNE | 2048 | 50 | 0.00133686 | 0.0048149 | 0.00347804 |
| P002 | Decision-ZNE | 2048 | 100 | 0.00428438 | 0.0048149 | 0.000530518 |
| P002 | Decision-ZNE | 2048 | 200 | 0.0048149 | 0.0048149 | 0 |
| P002 | Raw | 4096 | 50 | 1.65762e-07 | 1.14472e-08 | 1.54314e-07 |
| P002 | Raw | 4096 | 100 | 1.29069e-07 | 1.14472e-08 | 1.17622e-07 |
| P002 | Raw | 4096 | 200 | 1.14472e-08 | 1.14472e-08 | 0 |
| P002 | Accuracy-ZNE | 4096 | 50 | 0.000238142 | 0.000129459 | 0.000108683 |
| P002 | Accuracy-ZNE | 4096 | 100 | 9.22038e-05 | 0.000129459 | 3.72551e-05 |
| P002 | Accuracy-ZNE | 4096 | 200 | 0.000129459 | 0.000129459 | 0 |
| P002 | Decision-ZNE | 4096 | 50 | 4.91166e-05 | 0.000130433 | 8.13166e-05 |
| P002 | Decision-ZNE | 4096 | 100 | 5.01968e-05 | 0.000130433 | 8.02364e-05 |
| P002 | Decision-ZNE | 4096 | 200 | 0.000130433 | 0.000130433 | 0 |
| P002 | Raw | 8192 | 50 | 3.44502e-13 | 1.1402e-13 | 2.30482e-13 |
| P002 | Raw | 8192 | 100 | 7.54952e-15 | 1.1402e-13 | 1.0647e-13 |
| P002 | Raw | 8192 | 200 | 1.1402e-13 | 1.1402e-13 | 0 |
| P002 | Accuracy-ZNE | 8192 | 50 | 5.73138e-07 | 6.19669e-07 | 4.65319e-08 |
| P002 | Accuracy-ZNE | 8192 | 100 | 1.48772e-07 | 6.19669e-07 | 4.70897e-07 |
| P002 | Accuracy-ZNE | 8192 | 200 | 6.19669e-07 | 6.19669e-07 | 0 |
| P002 | Decision-ZNE | 8192 | 50 | 1.89146e-06 | 6.349e-07 | 1.25656e-06 |
| P002 | Decision-ZNE | 8192 | 100 | 1.14954e-07 | 6.349e-07 | 5.19945e-07 |
| P002 | Decision-ZNE | 8192 | 200 | 6.349e-07 | 6.349e-07 | 0 |
| P003 | Raw | 256 | 50 | 0.000156517 | 0.000213495 | 5.6978e-05 |
| P003 | Raw | 256 | 100 | 0.000222195 | 0.000213495 | 8.70086e-06 |
| P003 | Raw | 256 | 200 | 0.000213495 | 0.000213495 | 0 |
| P003 | Accuracy-ZNE | 256 | 50 | 0.0191211 | 0.0139337 | 0.00518739 |
| P003 | Accuracy-ZNE | 256 | 100 | 0.0153194 | 0.0139337 | 0.00138571 |
| P003 | Accuracy-ZNE | 256 | 200 | 0.0139337 | 0.0139337 | 1.11022e-16 |
| P003 | Decision-ZNE | 256 | 50 | 0.0158078 | 0.013917 | 0.00189077 |
| P003 | Decision-ZNE | 256 | 100 | 0.0120525 | 0.013917 | 0.00186453 |
| P003 | Decision-ZNE | 256 | 200 | 0.013917 | 0.013917 | 0 |
| P003 | Raw | 512 | 50 | 1.22298e-10 | 7.15433e-08 | 7.1421e-08 |
| P003 | Raw | 512 | 100 | 4.14719e-08 | 7.15433e-08 | 3.00713e-08 |
| P003 | Raw | 512 | 200 | 7.15433e-08 | 7.15433e-08 | 0 |
| P003 | Accuracy-ZNE | 512 | 50 | 0.000489644 | 0.00043479 | 5.48538e-05 |
| P003 | Accuracy-ZNE | 512 | 100 | 0.000398528 | 0.00043479 | 3.62623e-05 |
| P003 | Accuracy-ZNE | 512 | 200 | 0.00043479 | 0.00043479 | 0 |
| P003 | Decision-ZNE | 512 | 50 | 0.000952861 | 0.000434978 | 0.000517883 |
| P003 | Decision-ZNE | 512 | 100 | 0.000233651 | 0.000434978 | 0.000201327 |
| P003 | Decision-ZNE | 512 | 200 | 0.000434978 | 0.000434978 | 0 |
| P003 | Raw | 1024 | 50 | 1.03296e-11 | 2.59792e-14 | 1.03036e-11 |
| P003 | Raw | 1024 | 100 | 1.94289e-14 | 2.59792e-14 | 6.55032e-15 |
| P003 | Raw | 1024 | 200 | 2.59792e-14 | 2.59792e-14 | 0 |
| P003 | Accuracy-ZNE | 1024 | 50 | 2.33916e-07 | 5.95485e-07 | 3.6157e-07 |
| P003 | Accuracy-ZNE | 1024 | 100 | 1.26045e-06 | 5.95485e-07 | 6.64966e-07 |
| P003 | Accuracy-ZNE | 1024 | 200 | 5.95485e-07 | 5.95485e-07 | 0 |
| P003 | Decision-ZNE | 1024 | 50 | 1.22183e-06 | 6.05836e-07 | 6.15993e-07 |
| P003 | Decision-ZNE | 1024 | 100 | 1.42978e-07 | 6.05836e-07 | 4.62857e-07 |
| P003 | Decision-ZNE | 1024 | 200 | 6.05836e-07 | 6.05836e-07 | 0 |
| P003 | Raw | 2048 | 50 | 0 | 0 | 0 |
| P003 | Raw | 2048 | 100 | 0 | 0 | 0 |
| P003 | Raw | 2048 | 200 | 0 | 0 | 0 |
| P003 | Accuracy-ZNE | 2048 | 50 | 2.74171e-09 | 3.42126e-12 | 2.73829e-09 |
| P003 | Accuracy-ZNE | 2048 | 100 | 2.70671e-11 | 3.42126e-12 | 2.36459e-11 |
| P003 | Accuracy-ZNE | 2048 | 200 | 3.42126e-12 | 3.42126e-12 | 0 |
| P003 | Decision-ZNE | 2048 | 50 | 4.17633e-12 | 3.20799e-12 | 9.68337e-13 |
| P003 | Decision-ZNE | 2048 | 100 | 1.9984e-14 | 3.20799e-12 | 3.18801e-12 |
| P003 | Decision-ZNE | 2048 | 200 | 3.20799e-12 | 3.20799e-12 | 0 |
| P003 | Raw | 4096 | 50 | 0 | 0 | 0 |
| P003 | Raw | 4096 | 100 | 0 | 0 | 0 |
| P003 | Raw | 4096 | 200 | 0 | 0 | 0 |
| P003 | Accuracy-ZNE | 4096 | 50 | 0 | 0 | 0 |
| P003 | Accuracy-ZNE | 4096 | 100 | 0 | 0 | 0 |
| P003 | Accuracy-ZNE | 4096 | 200 | 0 | 0 | 0 |
| P003 | Decision-ZNE | 4096 | 50 | 0 | 0 | 0 |
| P003 | Decision-ZNE | 4096 | 100 | 0 | 0 | 0 |
| P003 | Decision-ZNE | 4096 | 200 | 0 | 0 | 0 |
| P003 | Raw | 8192 | 50 | 0 | 0 | 0 |
| P003 | Raw | 8192 | 100 | 0 | 0 | 0 |
| P003 | Raw | 8192 | 200 | 0 | 0 | 0 |
| P003 | Accuracy-ZNE | 8192 | 50 | 0 | 0 | 0 |
| P003 | Accuracy-ZNE | 8192 | 100 | 0 | 0 | 0 |
| P003 | Accuracy-ZNE | 8192 | 200 | 0 | 0 | 0 |
| P003 | Decision-ZNE | 8192 | 50 | 0 | 0 | 0 |
| P003 | Decision-ZNE | 8192 | 100 | 0 | 0 | 0 |
| P003 | Decision-ZNE | 8192 | 200 | 0 | 0 | 0 |
| P004 | Raw | 256 | 50 | 0.335468 | 0.339518 | 0.00404999 |
| P004 | Raw | 256 | 100 | 0.35457 | 0.339518 | 0.0150518 |
| P004 | Raw | 256 | 200 | 0.339518 | 0.339518 | 0 |
| P004 | Accuracy-ZNE | 256 | 50 | 0.429799 | 0.41921 | 0.0105896 |
| P004 | Accuracy-ZNE | 256 | 100 | 0.417483 | 0.41921 | 0.00172707 |
| P004 | Accuracy-ZNE | 256 | 200 | 0.41921 | 0.41921 | 0 |
| P004 | Decision-ZNE | 256 | 50 | 0.434748 | 0.419064 | 0.0156849 |
| P004 | Decision-ZNE | 256 | 100 | 0.432053 | 0.419064 | 0.0129896 |
| P004 | Decision-ZNE | 256 | 200 | 0.419064 | 0.419064 | 1.11022e-16 |
| P004 | Raw | 512 | 50 | 0.269793 | 0.266434 | 0.00335889 |
| P004 | Raw | 512 | 100 | 0.258268 | 0.266434 | 0.00816549 |
| P004 | Raw | 512 | 200 | 0.266434 | 0.266434 | 1.11022e-16 |
| P004 | Accuracy-ZNE | 512 | 50 | 0.372367 | 0.352821 | 0.0195467 |
| P004 | Accuracy-ZNE | 512 | 100 | 0.355575 | 0.352821 | 0.00275457 |
| P004 | Accuracy-ZNE | 512 | 200 | 0.352821 | 0.352821 | 1.11022e-16 |
| P004 | Decision-ZNE | 512 | 50 | 0.354984 | 0.352747 | 0.00223724 |
| P004 | Decision-ZNE | 512 | 100 | 0.360944 | 0.352747 | 0.00819699 |
| P004 | Decision-ZNE | 512 | 200 | 0.352747 | 0.352747 | 0 |
| P004 | Raw | 1024 | 50 | 0.185286 | 0.185975 | 0.000688609 |
| P004 | Raw | 1024 | 100 | 0.189384 | 0.185975 | 0.00340981 |
| P004 | Raw | 1024 | 200 | 0.185975 | 0.185975 | 0 |
| P004 | Accuracy-ZNE | 1024 | 50 | 0.284284 | 0.286994 | 0.0027102 |
| P004 | Accuracy-ZNE | 1024 | 100 | 0.283243 | 0.286994 | 0.00375072 |
| P004 | Accuracy-ZNE | 1024 | 200 | 0.286994 | 0.286994 | 0 |
| P004 | Decision-ZNE | 1024 | 50 | 0.305151 | 0.28676 | 0.0183916 |
| P004 | Decision-ZNE | 1024 | 100 | 0.29271 | 0.28676 | 0.00595081 |
| P004 | Decision-ZNE | 1024 | 200 | 0.28676 | 0.28676 | 1.11022e-16 |
| P004 | Raw | 2048 | 50 | 0.129193 | 0.1129 | 0.0162933 |
| P004 | Raw | 2048 | 100 | 0.120804 | 0.1129 | 0.00790386 |
| P004 | Raw | 2048 | 200 | 0.1129 | 0.1129 | 0 |
| P004 | Accuracy-ZNE | 2048 | 50 | 0.201946 | 0.215744 | 0.0137977 |
| P004 | Accuracy-ZNE | 2048 | 100 | 0.212238 | 0.215744 | 0.00350559 |
| P004 | Accuracy-ZNE | 2048 | 200 | 0.215744 | 0.215744 | 6.66134e-16 |
| P004 | Decision-ZNE | 2048 | 50 | 0.231078 | 0.215555 | 0.0155224 |
| P004 | Decision-ZNE | 2048 | 100 | 0.213697 | 0.215555 | 0.00185805 |
| P004 | Decision-ZNE | 2048 | 200 | 0.215555 | 0.215555 | 4.44089e-16 |
| P004 | Raw | 4096 | 50 | 0.021897 | 0.0468482 | 0.0249512 |
| P004 | Raw | 4096 | 100 | 0.0527992 | 0.0468482 | 0.00595104 |
| P004 | Raw | 4096 | 200 | 0.0468482 | 0.0468482 | 3.33067e-16 |
| P004 | Accuracy-ZNE | 4096 | 50 | 0.140366 | 0.13794 | 0.00242571 |
| P004 | Accuracy-ZNE | 4096 | 100 | 0.153614 | 0.13794 | 0.015674 |
| P004 | Accuracy-ZNE | 4096 | 200 | 0.13794 | 0.13794 | 2.22045e-16 |
| P004 | Decision-ZNE | 4096 | 50 | 0.14385 | 0.137823 | 0.00602757 |
| P004 | Decision-ZNE | 4096 | 100 | 0.12054 | 0.137823 | 0.0172831 |
| P004 | Decision-ZNE | 4096 | 200 | 0.137823 | 0.137823 | 3.33067e-16 |
| P004 | Raw | 8192 | 50 | 0.0100089 | 0.00788667 | 0.00212222 |
| P004 | Raw | 8192 | 100 | 0.012742 | 0.00788667 | 0.00485533 |
| P004 | Raw | 8192 | 200 | 0.00788667 | 0.00788667 | 0 |
| P004 | Accuracy-ZNE | 8192 | 50 | 0.0356722 | 0.0627506 | 0.0270784 |
| P004 | Accuracy-ZNE | 8192 | 100 | 0.0633673 | 0.0627506 | 0.00061678 |
| P004 | Accuracy-ZNE | 8192 | 200 | 0.0627506 | 0.0627506 | 0 |
| P004 | Decision-ZNE | 8192 | 50 | 0.0473906 | 0.0626446 | 0.015254 |
| P004 | Decision-ZNE | 8192 | 100 | 0.0806767 | 0.0626446 | 0.018032 |
| P004 | Decision-ZNE | 8192 | 200 | 0.0626446 | 0.0626446 | 0 |

## Ordering And P003 B=256 Projected-Ratio Bootstrap

| cell | B | item | baseline/order | CI_low | CI_high | fail_fraction/stability | verdict |
|---|---:|---|---|---:|---:|---:|---|
| P001 | 256 | ordering | Raw<Decision-ZNE<Accuracy-ZNE | NA | NA | 0.575 | sample_cov=Raw<Decision-ZNE<Accuracy-ZNE |
| P001 | 256 | Raw_vs_Accuracy-ZNE | 0.151418 | 0.0139258 | 0.384332 | 0 | robust_pass |
| P001 | 256 | Raw_vs_Decision-ZNE | 0.151499 | 0.00859867 | 0.378448 | 0 | robust_pass |
| P001 | 256 | Accuracy-ZNE_vs_Decision-ZNE | 0.0468663 | 0.241368 | 10.0985 | 0.9 | ci_includes_1_sampling_sensitive |
| P001 | 512 | ordering | Raw<Decision-ZNE<Accuracy-ZNE | NA | NA | 0.58 | sample_cov=Raw<Decision-ZNE<Accuracy-ZNE |
| P001 | 512 | Raw_vs_Accuracy-ZNE | 0.0288224 | 0.00455263 | 0.227641 | 0 | robust_pass |
| P001 | 512 | Raw_vs_Decision-ZNE | 0.0287433 | 0.00441271 | 0.223237 | 0 | robust_pass |
| P001 | 512 | Accuracy-ZNE_vs_Decision-ZNE | 0.125223 | 0.217019 | 8.64449 | 0.85 | ci_includes_1_sampling_sensitive |
| P001 | 1024 | ordering | Raw<Accuracy-ZNE<Decision-ZNE | NA | NA | 0.5 | sample_cov=Raw<Decision-ZNE<Accuracy-ZNE |
| P001 | 1024 | Raw_vs_Accuracy-ZNE | 0.00410209 | 0.00565016 | 0.282297 | 0 | robust_pass |
| P001 | 1024 | Raw_vs_Decision-ZNE | 0.00254061 | 0.00315836 | 0.273838 | 0 | robust_pass |
| P001 | 1024 | Accuracy-ZNE_vs_Decision-ZNE | 1.8379 | 0.186272 | 11.0388 | 0.865 | ci_includes_1_sampling_sensitive |
| P001 | 2048 | ordering | Raw<Accuracy-ZNE<Decision-ZNE | NA | NA | 0.76 | sample_cov=Raw<Accuracy-ZNE<Decision-ZNE |
| P001 | 2048 | Raw_vs_Accuracy-ZNE | 0.0273648 | 0.00251278 | 0.264504 | 0 | robust_pass |
| P001 | 2048 | Raw_vs_Decision-ZNE | 0.0226024 | 0.00152694 | 0.257405 | 0 | robust_pass |
| P001 | 2048 | Accuracy-ZNE_vs_Decision-ZNE | 5.61384 | 0.332207 | 16.3233 | 0.915 | ci_includes_1_sampling_sensitive |
| P001 | 4096 | ordering | Raw<Decision-ZNE<Accuracy-ZNE | NA | NA | 0.55 | sample_cov=Raw<Decision-ZNE<Accuracy-ZNE |
| P001 | 4096 | Raw_vs_Accuracy-ZNE | 0.033886 | 0.0114074 | 0.354483 | 0 | robust_pass |
| P001 | 4096 | Raw_vs_Decision-ZNE | 0.0333211 | 0.00706502 | 0.348891 | 0 | robust_pass |
| P001 | 4096 | Accuracy-ZNE_vs_Decision-ZNE | 0.660331 | 0.411168 | 21.3164 | 0.925 | ci_includes_1_sampling_sensitive |
| P001 | 8192 | ordering | Raw<Accuracy-ZNE<Decision-ZNE | NA | NA | 0.71 | sample_cov=Raw<Accuracy-ZNE<Decision-ZNE |
| P001 | 8192 | Raw_vs_Accuracy-ZNE | 0.351911 | 0.0212436 | 0.80695 | 0 | robust_pass |
| P001 | 8192 | Raw_vs_Decision-ZNE | 0.344074 | 0.0259992 | 0.79321 | 0 | robust_pass |
| P001 | 8192 | Accuracy-ZNE_vs_Decision-ZNE | 7.39207 | 0.509819 | 28.9218 | 0.94 | ci_includes_1_sampling_sensitive |
| P002 | 256 | ordering | Raw<Decision-ZNE<Accuracy-ZNE | NA | NA | 0.48 | sample_cov=Raw<Decision-ZNE<Accuracy-ZNE |
| P002 | 256 | Raw_vs_Accuracy-ZNE | 0.0472159 | 0.00281688 | 0.151752 | 0 | robust_pass |
| P002 | 256 | Raw_vs_Decision-ZNE | 0.0461967 | 0.0019603 | 0.145955 | 0 | robust_pass |
| P002 | 256 | Accuracy-ZNE_vs_Decision-ZNE | 10.0496 | 1.02847 | 77.8979 | 0.975 | robust_fail |
| P002 | 512 | ordering | Raw<Decision-ZNE<Accuracy-ZNE | NA | NA | 0.695 | sample_cov=Raw<Decision-ZNE<Accuracy-ZNE |
| P002 | 512 | Raw_vs_Accuracy-ZNE | 0.00905917 | 0.00510913 | 0.201047 | 0 | robust_pass |
| P002 | 512 | Raw_vs_Decision-ZNE | 0.0114217 | 0.00305973 | 0.192697 | 0 | robust_pass |
| P002 | 512 | Accuracy-ZNE_vs_Decision-ZNE | 3.49984 | 0.834526 | 20.0654 | 0.95 | ci_includes_1_sampling_sensitive |
| P002 | 1024 | ordering | Raw<Accuracy-ZNE<Decision-ZNE | NA | NA | 0.625 | sample_cov=Raw<Accuracy-ZNE<Decision-ZNE |
| P002 | 1024 | Raw_vs_Accuracy-ZNE | 0.390165 | 0.0578524 | 0.778076 | 0 | robust_pass |
| P002 | 1024 | Raw_vs_Decision-ZNE | 0.384073 | 0.0508725 | 0.767464 | 0 | robust_pass |
| P002 | 1024 | Accuracy-ZNE_vs_Decision-ZNE | 4.12897 | 0.334343 | 17.0965 | 0.9 | ci_includes_1_sampling_sensitive |
| P002 | 2048 | ordering | Raw<Accuracy-ZNE<Decision-ZNE | NA | NA | 0.945 | sample_cov=Raw<Accuracy-ZNE<Decision-ZNE |
| P002 | 2048 | Raw_vs_Accuracy-ZNE | 0.907102 | 0.1655 | 1.81987 | 0.47 | ci_includes_1_sampling_sensitive |
| P002 | 2048 | Raw_vs_Decision-ZNE | 0.859567 | 0.182367 | 1.75777 | 0.445 | ci_includes_1_sampling_sensitive |
| P002 | 2048 | Accuracy-ZNE_vs_Decision-ZNE | 14.1315 | 1.23703 | 27.4997 | 0.98 | robust_fail |
| P002 | 4096 | ordering | Raw<Accuracy-ZNE<Decision-ZNE | NA | NA | 0.615 | sample_cov=Raw<Accuracy-ZNE<Decision-ZNE |
| P002 | 4096 | Raw_vs_Accuracy-ZNE | 0.287375 | 0.027767 | 2.0917 | 0.345 | ci_includes_1_sampling_sensitive |
| P002 | 4096 | Raw_vs_Decision-ZNE | 0.267582 | 0.0712107 | 2.09773 | 0.355 | ci_includes_1_sampling_sensitive |
| P002 | 4096 | Accuracy-ZNE_vs_Decision-ZNE | 2.95956 | 0.28195 | 22.9173 | 0.925 | ci_includes_1_sampling_sensitive |
| P002 | 8192 | ordering | Raw<Accuracy-ZNE<Decision-ZNE | NA | NA | 0.63 | sample_cov=Raw<Accuracy-ZNE<Decision-ZNE |
| P002 | 8192 | Raw_vs_Accuracy-ZNE | 4.1006 | 0.127041 | 10.9218 | 0.855 | ci_includes_1_sampling_sensitive |
| P002 | 8192 | Raw_vs_Decision-ZNE | 4.20207 | 0.171083 | 10.931 | 0.87 | ci_includes_1_sampling_sensitive |
| P002 | 8192 | Accuracy-ZNE_vs_Decision-ZNE | 2.8801 | 0.441519 | 18.8582 | 0.925 | ci_includes_1_sampling_sensitive |
| P003 | 256 | ordering | Raw<Decision-ZNE<Accuracy-ZNE | NA | NA | 0.54 | sample_cov=Raw<Decision-ZNE<Accuracy-ZNE |
| P003 | 256 | Raw_vs_Accuracy-ZNE | 1.05374 | 0.112386 | 2.23562 | 0.56 | ci_includes_1_sampling_sensitive |
| P003 | 256 | Raw_vs_Decision-ZNE | 1.05237 | 0.109691 | 2.24569 | 0.555 | ci_includes_1_sampling_sensitive |
| P003 | 256 | Accuracy-ZNE_vs_Decision-ZNE | 5.53321 | 1.64385 | 86.4189 | 0.985 | robust_fail |
| P003 | 512 | ordering | Raw<Accuracy-ZNE<Decision-ZNE | NA | NA | 0.58 | sample_cov=Raw<Accuracy-ZNE<Decision-ZNE |
| P003 | 512 | Raw_vs_Accuracy-ZNE | 0.908498 | 0.0809789 | 3.36711 | 0.515 | ci_includes_1_sampling_sensitive |
| P003 | 512 | Raw_vs_Decision-ZNE | 0.911682 | 0.0768825 | 3.39247 | 0.515 | ci_includes_1_sampling_sensitive |
| P003 | 512 | Accuracy-ZNE_vs_Decision-ZNE | 2.82718 | 0.511423 | 47.4153 | 0.955 | ci_includes_1_sampling_sensitive |
| P003 | 1024 | ordering | Raw<Accuracy-ZNE<Decision-ZNE | NA | NA | 0.8 | sample_cov=Raw<Accuracy-ZNE<Decision-ZNE |
| P003 | 1024 | Raw_vs_Accuracy-ZNE | 0.320305 | 0.0825889 | 5.16779 | 0.67 | ci_includes_1_sampling_sensitive |
| P003 | 1024 | Raw_vs_Decision-ZNE | 0.359333 | 0.0522654 | 5.13265 | 0.67 | ci_includes_1_sampling_sensitive |
| P003 | 1024 | Accuracy-ZNE_vs_Decision-ZNE | 21.7409 | 1.21917 | 63.7837 | 0.98 | robust_fail |
| P003 | 2048 | ordering | Raw<Decision-ZNE<Accuracy-ZNE | NA | NA | 0.915 | sample_cov=Raw<Decision-ZNE<Accuracy-ZNE |
| P003 | 2048 | Raw_vs_Accuracy-ZNE | 0.752166 | 0.170011 | 11.5497 | 0.83 | ci_includes_1_sampling_sensitive |
| P003 | 2048 | Raw_vs_Decision-ZNE | 0.635126 | 0.142259 | 11.434 | 0.84 | ci_includes_1_sampling_sensitive |
| P003 | 2048 | Accuracy-ZNE_vs_Decision-ZNE | 0.140455 | 0.00513043 | 0.363312 | 0 | robust_pass |
| P003 | 4096 | ordering | Raw<Accuracy-ZNE<Decision-ZNE | NA | NA | 1 | sample_cov=Raw<Accuracy-ZNE<Decision-ZNE |
| P003 | 4096 | Raw_vs_Accuracy-ZNE | 0 | 0 | 0 | 0 | robust_pass |
| P003 | 4096 | Raw_vs_Decision-ZNE | 0 | 0 | 0 | 0 | robust_pass |
| P003 | 4096 | Accuracy-ZNE_vs_Decision-ZNE | 0 | 0 | 0 | 0 | robust_pass |
| P003 | 8192 | ordering | Raw<Accuracy-ZNE<Decision-ZNE | NA | NA | 1 | sample_cov=Raw<Accuracy-ZNE<Decision-ZNE |
| P003 | 8192 | Raw_vs_Accuracy-ZNE | 0 | 0 | 0 | 0 | robust_pass |
| P003 | 8192 | Raw_vs_Decision-ZNE | 0 | 0 | 0 | 0 | robust_pass |
| P003 | 8192 | Accuracy-ZNE_vs_Decision-ZNE | 0 | 0 | 0 | 0 | robust_pass |
| P004 | 256 | ordering | Raw<Decision-ZNE<Accuracy-ZNE | NA | NA | 0.895 | sample_cov=Raw<Decision-ZNE<Accuracy-ZNE |
| P004 | 256 | Raw_vs_Accuracy-ZNE | 0.0738229 | 0.00407764 | 0.32105 | 0 | robust_pass |
| P004 | 256 | Raw_vs_Decision-ZNE | 0.0706228 | 0.00413281 | 0.316636 | 0 | robust_pass |
| P004 | 256 | Accuracy-ZNE_vs_Decision-ZNE | 10.1306 | 0.695194 | 28.9334 | 0.955 | ci_includes_1_sampling_sensitive |
| P004 | 512 | ordering | Raw<Decision-ZNE<Accuracy-ZNE | NA | NA | 0.705 | sample_cov=Raw<Decision-ZNE<Accuracy-ZNE |
| P004 | 512 | Raw_vs_Accuracy-ZNE | 0.162288 | 0.00944349 | 0.439589 | 0 | robust_pass |
| P004 | 512 | Raw_vs_Decision-ZNE | 0.161044 | 0.00951048 | 0.433136 | 0 | robust_pass |
| P004 | 512 | Accuracy-ZNE_vs_Decision-ZNE | 3.91073 | 0.287364 | 28.1153 | 0.935 | ci_includes_1_sampling_sensitive |
| P004 | 1024 | ordering | Raw<Decision-ZNE<Accuracy-ZNE | NA | NA | 0.795 | sample_cov=Raw<Decision-ZNE<Accuracy-ZNE |
| P004 | 1024 | Raw_vs_Accuracy-ZNE | 0.179126 | 0.00597885 | 0.428125 | 0 | robust_pass |
| P004 | 1024 | Raw_vs_Decision-ZNE | 0.175152 | 0.00690779 | 0.41951 | 0 | robust_pass |
| P004 | 1024 | Accuracy-ZNE_vs_Decision-ZNE | 14.2069 | 1.36928 | 39.8841 | 0.98 | robust_fail |
| P004 | 2048 | ordering | Raw<Decision-ZNE<Accuracy-ZNE | NA | NA | 0.805 | sample_cov=Raw<Decision-ZNE<Accuracy-ZNE |
| P004 | 2048 | Raw_vs_Accuracy-ZNE | 0.0156213 | 0.006676 | 0.302566 | 0 | robust_pass |
| P004 | 2048 | Raw_vs_Decision-ZNE | 0.0127223 | 0.00564786 | 0.290965 | 0 | robust_pass |
| P004 | 2048 | Accuracy-ZNE_vs_Decision-ZNE | 9.91511 | 0.517944 | 36.814 | 0.965 | ci_includes_1_sampling_sensitive |
| P004 | 4096 | ordering | Raw<Decision-ZNE<Accuracy-ZNE | NA | NA | 0.7 | sample_cov=Raw<Decision-ZNE<Accuracy-ZNE |
| P004 | 4096 | Raw_vs_Accuracy-ZNE | 0.00617974 | 0.00717541 | 0.317775 | 0 | robust_pass |
| P004 | 4096 | Raw_vs_Decision-ZNE | 0.00803321 | 0.00601829 | 0.316272 | 0 | robust_pass |
| P004 | 4096 | Accuracy-ZNE_vs_Decision-ZNE | 5.36758 | 0.398562 | 34.3544 | 0.94 | ci_includes_1_sampling_sensitive |
| P004 | 8192 | ordering | Raw<Decision-ZNE<Accuracy-ZNE | NA | NA | 0.665 | sample_cov=Raw<Decision-ZNE<Accuracy-ZNE |
| P004 | 8192 | Raw_vs_Accuracy-ZNE | 0.0451387 | 0.00694821 | 0.566427 | 0 | robust_pass |
| P004 | 8192 | Raw_vs_Decision-ZNE | 0.0421421 | 0.0114521 | 0.553469 | 0 | robust_pass |
| P004 | 8192 | Accuracy-ZNE_vs_Decision-ZNE | 6.52135 | 0.735661 | 41.7009 | 0.97 | ci_includes_1_sampling_sensitive |
