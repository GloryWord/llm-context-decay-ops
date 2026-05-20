# Compliance Decay Experiment — Presentation Report

> **Generated**: 2026-04-14 18:09
> **Runs analyzed**: 1540
> **Models**: hugging-quants/Meta-Llama-3.1-8B-Instruct-AWQ-INT4

---

## 1. Figure Semantics

- **Q1**: each point is the exact-cell final-turn mean for one `(rule_count, turn_count, attack_intensity)` condition. Error bars are ±1 SD. Each point is annotated with `n`.
- **Q2**: each heatmap cell is the all-turn pass rate for one `(attack_intensity, turn_count, rule_type)` condition, counting only applicable rule evaluations (`pass is not None`).
- **Q3**: each point is the same exact-cell final-turn mean as Q1, regrouped to compare benign vs adversarial within each `rule_count`.

---

## 2. Visualizations

### 2.1 Q1: Final-turn Compliance by Rule Count
![Q1](figures/q1_compliance_by_rule_count.png)

### 2.2 Q2: Rule-type Pass Rate by Attack and Turn Count
![Q2](figures/q2_per_rule_type.png)

### 2.3 Q3: Benign vs Adversarial (exact-cell final-turn mean)
![Q3](figures/q3_benign_vs_adversarial.png)

### 2.4 Representative Heatmap
![Heatmap](figures/heatmap_representative.png)

---

## 3. Final-turn Compliance by Condition

| Condition | Mean Compliance | Std | N |
|-----------|----------------|-----|---|
| R1_T10_adversarial | 31.1% | ±46.3% | 45 |
| R1_T10_benign | 100.0% | ±0.0% | 45 |
| R1_T15_adversarial | 11.1% | ±31.4% | 45 |
| R1_T15_benign | 100.0% | ±0.0% | 45 |
| R1_T1_adversarial | 50.0% | ±50.0% | 60 |
| R1_T1_benign | 100.0% | ±0.0% | 60 |
| R1_T5_adversarial | 50.0% | ±50.0% | 60 |
| R1_T5_benign | 100.0% | ±0.0% | 60 |
| R3_T10_adversarial | 35.9% | ±25.3% | 45 |
| R3_T10_benign | 83.3% | ±19.2% | 45 |
| R3_T15_adversarial | 47.4% | ±22.2% | 45 |
| R3_T15_benign | 88.9% | ±15.7% | 45 |
| R3_T1_adversarial | 76.4% | ±25.9% | 60 |
| R3_T1_benign | 91.7% | ±14.4% | 60 |
| R3_T5_adversarial | 69.2% | ±31.6% | 60 |
| R3_T5_benign | 84.7% | ±18.6% | 60 |
| R5_T10_adversarial | 67.4% | ±17.8% | 45 |
| R5_T10_benign | 84.3% | ±14.4% | 45 |
| R5_T15_adversarial | 68.8% | ±13.9% | 45 |
| R5_T15_benign | 75.5% | ±19.4% | 45 |
| R5_T1_adversarial | 83.3% | ±18.6% | 60 |
| R5_T1_benign | 81.2% | ±17.1% | 60 |
| R5_T5_adversarial | 72.4% | ±21.7% | 60 |
| R5_T5_benign | 78.0% | ±13.3% | 60 |
| R7_T10_adversarial | 64.8% | ±14.1% | 30 |
| R7_T10_benign | 86.7% | ±9.4% | 30 |
| R7_T15_adversarial | 61.9% | ±17.4% | 30 |
| R7_T15_benign | 76.7% | ±7.5% | 30 |
| R7_T1_adversarial | 81.2% | ±13.1% | 40 |
| R7_T1_benign | 77.5% | ±12.0% | 40 |
| R7_T5_adversarial | 68.0% | ±13.3% | 40 |
| R7_T5_benign | 80.0% | ±0.0% | 40 |

---

## 4. Next Steps

- [ ] Add a slide that explicitly defines one run, one cell, and one figure point.
- [ ] Add a `rule_set_variant` appendix table for the curated combinations used at each `rule_count`.
- [ ] Consider a deferred follow-up experiment with long-document/PDF input plus strict 200-char / 300-char output limits. This idea was noted but is out of scope for the current run.

- Current overall benign vs adversarial final-turn gap: 28.1pp