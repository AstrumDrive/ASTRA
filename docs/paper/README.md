# Architecture report

`astra2_architecture.tex` — ASTRA 2.0: architecture, algorithm, measured failure
modes and evaluation. 11 pages, six figures, English.

```bash
pdflatex -interaction=nonstopmode astra2_architecture.tex   # twice, for refs
```

Requires TeX Live with `tikz`, `pgfplots`, `booktabs`, `enumitem`, `microtype`.
No external images: every figure is drawn in TikZ/pgfplots from numbers that
appear in `docs/evidence/`.

## Where each number comes from

| Claim in the report | Source |
|---|---|
| p90 por fase, 84 ciclos | `ASTRA2_PHASE_BUDGET_20260813.md` |
| artefacto de plan en el 72 % de deliberaciones; 1 de 87 llegó a la conjetura | `ASTRA2_PLAN_ARTIFACT_INJECTION_20260814.md` |
| 7 de 87 ciclos atribuyeron mal la fase fallida | idem |
| 64 000 tokens de salida; éxitos en 59 181 y 56 630 | idem |
| 12 reparaciones con techo mediano de 165 s; 882 s vs 1249 s | `ASTRA2_ABLATION_FULL_VS_LINEAR_20260814.md` |
| enmienda A1 del presupuesto (1800 → 2400 s) | `PROTOCOL_FINGERPRINT_HISTORY.md` |
| medianas de fase con 2400 s; 0 VALIDATED vs 3 | `ASTRA2_ABLATION_RUN3_20260816.md` |
| revisión final rechazada con 571,83 s libres | idem |
| corrida corta 4/4 sin averías | `ASTRA2_SHORT_VERIFY_20260816.md` |
| caso NEC: testigo exacto y contraste con el cálculo aparte | `ASTRA2_WARP_NEC_TEST_20260814.md` |

Regla de la casa: ninguna cifra entra en el documento sin log depositado. Si una
medición se retracta, se corrige **aquí y en el documento**, no solo en el
evidence.
