# Compliance Decay Experiment — Interim Report

> **Generated**: 2026-04-01 00:57
> **Runs analyzed**: 1540 / 1,540 (target)
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

### 2.2 Degradation Onset (DO < 80%) & Collapse Threshold (CT < 50%)

| Condition | DO (mean turn) | DO cases | CT (mean turn) | CT cases |
|-----------|---------------|----------|---------------|----------|
| R1_adversarial | T4.2 | 165 | T4.2 | 165 |
| R1_benign | — | 0 | — | 0 |
| R3_adversarial | T2.8 | 175 | T7.2 | 122 |
| R3_benign | T1.1 | 95 | — | 0 |
| R5_adversarial | T2.5 | 169 | T10.0 | 32 |
| R5_benign | T1.1 | 146 | T3.0 | 20 |
| R7_adversarial | T4.1 | 96 | T7.5 | 37 |
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

- **Adversarial impact**: 28.1pp lower compliance vs benign (benign: 87.4%, adversarial: 59.3%)

- **R=1**: mean final compliance 68.8%
- **R=3**: mean final compliance 73.4%
- **R=5**: mean final compliance 76.7%
- **R=7**: mean final compliance 74.9%

---

## 5. Status & Next Steps

- Data collection: 1540/1,540 runs (100.0%)
- [ ] Complete remaining repetitions
- [ ] Add DeepSeek R1 model comparison
- [ ] Statistical tests (ANOVA, dose-response fitting)
- [ ] Final report generation