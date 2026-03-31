# Compliance Decay Experiment — Interim Report

> **Generated**: 2026-03-31 22:15
> **Runs analyzed**: 1594 / 1,540 (target)
> **Models**: hugging-quants/Meta-Llama-3.1-8B-Instruct-AWQ-INT4

---

## 1. Experiment Overview

| Variable | Levels |
|----------|--------|
| rule_count | 1, 3, 5, 7 |
| turn_count | 1, 5, 10, 15 |
| attack_intensity | benign, adversarial |
| repetitions | 5 per cell |
| models | Llama 3.1 8B (vLLM) |

---

## 2. Key Findings

### 2.1 Final Compliance by Condition

| Condition | Mean Compliance | Std | N |
|-----------|----------------|-----|---|
| R1_T10_adversarial | 43.1% | ±49.5% | 51 |
| R1_T10_benign | 100.0% | ±0.0% | 51 |
| R1_T15_adversarial | 30.6% | ±46.1% | 49 |
| R1_T15_benign | 100.0% | ±0.0% | 51 |
| R1_T1_adversarial | 47.1% | ±49.9% | 68 |
| R1_T1_benign | 100.0% | ±0.0% | 68 |
| R1_T5_adversarial | 55.9% | ±49.7% | 68 |
| R1_T5_benign | 100.0% | ±0.0% | 68 |
| R3_T10_adversarial | 39.6% | ±26.6% | 45 |
| R3_T10_benign | 83.3% | ±19.2% | 45 |
| R3_T15_adversarial | 45.9% | ±25.1% | 45 |
| R3_T15_benign | 88.9% | ±15.7% | 45 |
| R3_T1_adversarial | 80.6% | ±24.4% | 60 |
| R3_T1_benign | 91.7% | ±14.4% | 60 |
| R3_T5_adversarial | 73.9% | ±32.3% | 60 |
| R3_T5_benign | 84.7% | ±18.6% | 60 |
| R5_T10_adversarial | 66.3% | ±14.7% | 45 |
| R5_T10_benign | 84.3% | ±14.4% | 45 |
| R5_T15_adversarial | 65.6% | ±14.6% | 45 |
| R5_T15_benign | 76.9% | ±20.3% | 45 |
| R5_T1_adversarial | 83.3% | ±19.8% | 60 |
| R5_T1_benign | 81.2% | ±17.1% | 60 |
| R5_T5_adversarial | 75.0% | ±22.0% | 60 |
| R5_T5_benign | 78.5% | ±12.9% | 60 |
| R7_T10_adversarial | 63.3% | ±13.7% | 30 |
| R7_T10_benign | 86.7% | ±9.4% | 30 |
| R7_T15_adversarial | 60.0% | ±16.3% | 30 |
| R7_T15_benign | 76.7% | ±7.5% | 30 |
| R7_T1_adversarial | 80.0% | ±14.1% | 40 |
| R7_T1_benign | 77.5% | ±12.0% | 40 |
| R7_T5_adversarial | 70.0% | ±10.0% | 40 |
| R7_T5_benign | 80.0% | ±0.0% | 40 |

### 2.2 Degradation Onset (DO < 80%) & Collapse Threshold (CT < 50%)

| Condition | DO (mean turn) | DO cases | CT (mean turn) | CT cases |
|-----------|---------------|----------|---------------|----------|
| R1_adversarial | T3.3 | 154 | T3.3 | 154 |
| R1_benign | — | 0 | — | 0 |
| R3_adversarial | T2.8 | 156 | T7.0 | 92 |
| R3_benign | T1.1 | 95 | — | 0 |
| R5_adversarial | T2.4 | 164 | T9.9 | 31 |
| R5_benign | T1.1 | 146 | T3.0 | 20 |
| R7_adversarial | T4.7 | 90 | T7.9 | 30 |
| R7_benign | T3.0 | 33 | T13.0 | 3 |

---

## 3. Visualizations

### 3.1 Q1: Compliance by Rule Count
![Q1](figures/q1_compliance_by_rule_count.png)

### 3.2 Q2: Per-Rule-Type Compliance
![Q2](figures/q2_per_rule_type.png)

### 3.3 Q3: Benign vs Adversarial
![Q3](figures/q3_benign_vs_adversarial.png)

### 3.4 Representative Heatmap
![Heatmap](figures/heatmap_representative.png)

---

## 4. Preliminary Observations

- **Adversarial impact**: 26.4pp lower compliance vs benign (benign: 87.9%, adversarial: 61.5%)

- **R=1**: mean final compliance 72.8%
- **R=3**: mean final compliance 74.9%
- **R=5**: mean final compliance 76.8%
- **R=7**: mean final compliance 74.6%

---

## 5. Status & Next Steps

- Data collection: 1594/1,540 runs (103.5%)
- [ ] Complete remaining repetitions
- [ ] Add DeepSeek R1 model comparison
- [ ] Statistical tests (ANOVA, dose-response fitting)
- [ ] Final report generation