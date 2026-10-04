# Choosing a Model for CARDS Classification

This report evaluates 32 classifiers for labelling claims against the CARDS climate misinformation taxonomy. Benchmark data, results, and evaluation scripts are available in [model-selection/results.csv](model-selection/results.csv) and [model-selection/make_plots.py](model-selection/make_plots.py).

---

## Executive Summary

- **Statistical Parity Across Top Models:** Performance among the top ten LLMs is statistically indistinguishable within 95% confidence intervals. Selection should prioritise cost, inference latency, licence openness, and error profile tolerance.
- **Precision/Recall Trade-Off:** Classifiers face an intrinsic trade-off between false alarms (incorrectly assigning categories to non-misinforming claims) and missed narratives. Adjustments to prompts, the ClimateBERT gate, and model choice shift positions along this Pareto front rather than advancing both simultaneously.
- **Diminishing Returns with Model Size:** Parameter scaling plateaus around 14B parameters. Between 14B and 1.6T, performance remains flat within statistical noise; below 10B parameters, accuracy degrades markedly.
- **Review Context Degrades Accuracy:** Supplying full fact-check review text lowered the balanced score across six of seven finalist models by introducing additional false alarms. Standalone claim classification is recommended.
- **Discrepancy Between List and Realised Costs:** Measured cost per call varies up to 20-fold among models with comparable accuracy. Published token list prices do not reflect actual costs for reasoning models that generate hidden chain-of-thought tokens.
- **Limited Benefit from Prompt Optimisation:** GEPA prompt tuning yielded inconsistent gains across architectures, lowering or failing to improve the balanced score for all five tested models.

### Recommended Models by Requirement

| Requirement | Recommended Model | Characteristics |
| :---------- | :---------------- | :-------------- |
| Lowest inference cost | `glm-5.3-flash` | Balanced score 0.645, ~\$0.00009 per call. MIT licence, MoE architecture (320B total / 18B active parameters). |
| Highest balanced score | `qwen3.8-flash` | Balanced score 0.654 (tied with `deepseek-v4-flash`), ~\$0.00033 per call. |
| Highest category accuracy | `deepseek-v4-flash` | 0.604 category accuracy on narrative claims, 19.9% false-alarm rate, ~\$0.0017 per call. |
| Lowest latency | `gemma-4-31b` or `ministral-14b-2512` | ~5 s latency per call via hosted providers; 17–19% false alarms. |
| Local deployment (16–24 GB VRAM) | `ministral-14b-2512` (16 GB) or `gemma-4-31b` (24 GB+) | Balanced score 0.616 / 0.620; see [Running Locally](#running-locally). |
| Compact local model | `ministral-14b-2512` | 14B parameters, balanced score 0.616; runs on 16 GB Apple Silicon or GPU at 4-bit quantisation. |

---

## Experimental Setup

### Datasets
Evaluations pooled 847 claims across three benchmarks evaluated without context:
- `climatesense_v1` (398 documents)
- `climatesense_v2` (277 documents)
- `nslp_test` (ClimateCheck test split, 172 documents)

Of these, 503 documents (59%) contain no misinformation narrative (coded as `0_0`), while 316 carry a specific CARDS category. 28 documents with ambiguous annotations linking `0_0` to a category were excluded from comparative metrics.

### Models and Inference Configuration
- 30 LLMs evaluated via OpenRouter, benchmarked alongside the local `transformer` and `matcher` baselines.
- Standardised prompt configuration (`xplainnlp-nslp` preset), temperature 0, ClimateBERT gate disabled, and structured JSON output. Detailed configurations are provided in [`eval.suite.toml`](../eval.suite.toml).

### Evaluation Metrics
CARDS taxonomy code `0_0` signifies the absence of a climate-denial narrative. Evaluations therefore track two complementary axes:
1. **False-Alarm Rate:** The proportion of negative documents (`0_0`) incorrectly assigned a misinformation category.
2. **Category Accuracy:** The exact-match accuracy evaluated exclusively on documents possessing an established narrative (treating missed narratives as incorrect).

The primary ranking metric is the **balanced score**, defined as:

$$\text{Balanced Score} = 0.75 \times \text{Category Accuracy} + 0.25 \times (1 - \text{False-Alarm Rate})$$

Because the target application prioritises identifying claims within known misinformation datasets, missed narratives are penalised more heavily than false alarms.

---

## Benchmark Results

![Balanced score by model](model-selection/balanced_ranking.svg)

The top ten models achieve balanced scores between 0.616 and 0.654, with 95% bootstrap intervals spanning approximately $\pm 0.04$. The rule-based `matcher` and local `transformer` baselines achieve balanced scores of 0.27.

| Model | Balanced Score | Category Accuracy | False-Alarm Rate | Failed Items |
| :---- | :------------- | :---------------- | :--------------- | :----------- |
| `qwen3.8-flash` | 0.654 | 0.589 | 15.1% | 0 |
| `deepseek-v4-flash` | 0.654 | 0.604 | 19.9% | 0 |
| `glm-5.3-flash` | 0.645 | 0.582 | 16.5% | 0 |
| `deepseek-v4-pro` | 0.638 | 0.567 | 14.7% | 0 |
| `nemotron-3-super-120b` | 0.630 | 0.560 | 16.1% | 0 |
| `gemma-4-31b` | 0.620 | 0.557 | 19.1% | 0 |
| `qwen3.6-35b` | 0.619 | 0.538 | 13.7% | 0 |
| `mistral-small-3.2-24b` | 0.619 | 0.570 | 23.5% | 1 |
| `minimax-m2.7` | 0.618 | 0.538 | 14.1% | 0 |
| `ministral-14b-2512` | 0.616 | 0.544 | 17.1% | 0 |

### Precision / Accuracy Trade-Off

![Category accuracy against false-alarm rate](model-selection/tradeoff.svg)

Architectures align along an empirical Pareto frontier: models with conservative false-alarm rates (such as `gpt-oss-20b` and `glm-4.7-flash`) achieve lower category recall, whereas models such as `deepseek-v4-flash` maximize category accuracy at the expense of higher false-alarm rates.

### Model Parameter Size

![Balanced score against model size](model-selection/balanced_vs_size.svg)

Beyond approximately 14B parameters, the performance frontier plateaus. The 1.6T-parameter `deepseek-v4-pro` scores within noise margins of the 14B `ministral-14b-2512`.

### Inference Cost and Latency

Costs represent measured account charges over 24 queries per model:

![Balanced score against measured cost per call](model-selection/cost_vs_score.svg)

| Model | Cost per Call | Median Latency | Entire Graph (Gate Enabled, ~21k calls) | Entire Graph (Gate Disabled, ~263k calls) |
| :---- | :------------ | :------------- | :-------------------------------------- | :---------------------------------------- |
| `glm-5.3-flash` | \$0.00009 | 14 s | ~\$2 | ~\$24 |
| `ministral-14b-2512` | \$0.00010 | 5 s | ~\$2 | ~\$26 |
| `glm-4.7-flash` | \$0.00030 | 28 s | ~\$6 | ~\$79 |
| `qwen3.8-flash` | \$0.00033 | 26 s | ~\$7 | ~\$87 |
| `gemma-4-31b` | \$0.00039 | 5 s | ~\$8 | ~\$103 |
| `deepseek-v4-flash` | \$0.00170 | 34 s | ~\$36 | ~\$450 |

Estimated end-to-end processing times for the knowledge graph with the ClimateBERT pre-filter gate enabled (~21,000 calls) range from ~2 hours (`gemma-4-31b` and `ministral-14b-2512` at concurrency 24) to ~18 hours (`deepseek-v4-flash` with extended chain-of-thought generation).

---

## Sensitivity to Metric Weighting

Because 59% of benchmark claims lack misinformation narratives, evaluating models strictly by overall accuracy favours architectures that predict `0_0` conservatively. The table below illustrates how model rankings shift across category weightings:

| Weight on Category Accuracy | Top-Ranked Models |
| :-------------------------- | :---------------- |
| **0.3** (prioritises low false alarms) | `gpt-oss-20b` (0.790), `glm-4.7-flash` (0.780), `qwen3.8-flash` (0.771) |
| **0.5** (balanced objective) | `qwen3.8-flash` (0.719), `deepseek-v4-pro` (0.710), `glm-5.3-flash` (0.709) |
| **0.75** (default objective) | `qwen3.8-flash` (0.654), `deepseek-v4-flash` (0.654), `glm-5.3-flash` (0.645) |

`qwen3.8-flash` maintains leading positions across all weighting schemes, while `glm-5.3-flash` remains in the top four across balanced and recall-focused weights.

---

## Impact of the ClimateBERT Pre-Filter Gate

The optional pre-classifier gate (`climatebert/distilroberta-base-climate-detector`) filters out claims identified as non-climate-related before invocation of the LLM:

- **Filter Efficiency:** Eliminates approximately 92% of candidate texts in full-graph corpora.
- **Precision vs Recall:** On `climatesense_v1`, the gate reduced false alarms by ~30% (improving precision by 3–6 points) while incurring a 3.5-point drop in recall (filtering ~3% of narrative-bearing claims).
- **Recommendation:** Enabling `--preclassifier` is strongly recommended for full graph builds to reduce computational and financial overhead.

---

## Prompt Optimisation and Formatting

### Comparison of Built-in Presets

| Model | `xplainnlp-nslp` (Default) | `climatesense-nslp` | `cards-narrative` |
| :---- | :------------------------- | :------------------ | :---------------- |
| `gemma-4-31b` | 0.614 / 21.7% | 0.566 / 15.7% | 0.627 / 28.5% |
| `deepseek-v4-flash` | 0.646 / 22.5% | 0.611 / 14.9% | 0.644 / 32.4% |
| `ministral-14b-2512` | 0.598 / 18.6% | 0.513 / 17.7% | 0.560 / 54.5% |

*(Values indicate exact category match / false-alarm rate).* The default `xplainnlp-nslp` preset consistently provides the best trade-off between category precision and narrative coverage.

### GEPA Prompt Optimisation
Tuning system prompts using GEPA on `gemma-4-31b` resulted in reduced false alarms at the cost of lower narrative recall and reduced category accuracy. Across balanced scores, prompt tuning did not yield statistically significant gains and degraded performance for `ministral-14b-2512`. The default prompt remains the recommended baseline.

---

## Effect of Fact-Check Review Context

Testing models on `climatesense_v2` with accompanying review context demonstrated consistent degradation across six of seven architectures:

| Model | Balanced Score (Without $\rightarrow$ With Context) | Delta (95% CI) | Category Accuracy | False-Alarm Rate |
| :---- | :------------------------------------------------- | :------------- | :---------------- | :--------------- |
| `glm-5.3-flash` | 0.603 $\rightarrow$ 0.540 | -0.064 (-0.118 to -0.016) | 61.3% $\rightarrow$ 54.0% | 42.5% $\rightarrow$ 46.3% |
| `qwen3.8-flash` | 0.596 $\rightarrow$ 0.577 | -0.019 (-0.058 to +0.025) | 58.9% $\rightarrow$ 58.1% | 38.1% $\rightarrow$ 43.3% |
| `gemma-4-31b` | 0.522 $\rightarrow$ 0.561 | +0.040 (-0.013 to +0.093) | 52.4% $\rightarrow$ 56.5% | 48.5% $\rightarrow$ 44.8% |
| `ministral-14b-2512` | 0.554 $\rightarrow$ 0.479 | -0.075 (-0.129 to -0.022) | 52.4% $\rightarrow$ 49.2% | 35.8% $\rightarrow$ 56.0% |
| `deepseek-v4-flash` | 0.590 $\rightarrow$ 0.557 | -0.033 (-0.079 to +0.010) | 60.5% $\rightarrow 58.1% | 45.5% $\rightarrow$ 51.5% |

**Root Cause:** Including debunking text causes models to latch onto quoted myths within the rebuttal, artificially inflating false alarms. Standalone claim text classification is therefore strongly recommended.

---

## Running Locally

Hardware specifications for local deployment:

| Hardware Configuration | Recommended Model | Quantisation | VRAM Requirement | Balanced Score |
| :--------------------- | :---------------- | :----------- | :--------------- | :------------- |
| GPU (16 GB), 16 GB Apple Silicon | `ministral-14b-2512` | 4-bit | ~9 GB | 0.616 |
| GPU (24 GB), 32 GB Apple Silicon | `gemma-4-31b` | 4-bit | ~18 GB | 0.620 |
| GPU (80 GB), Multi-GPU cluster | `nemotron-3-super-120b` | 4-bit | ~65 GB | 0.630 |

### Local Serving Recommendations
- **Inference Engines:** Use `vLLM` or `Ollama` for batched concurrency on CUDA GPUs; use `LM Studio` or `Ollama` on Apple Silicon.
- **Precision:** On older hardware without native bfloat16 support (e.g. Nvidia T4), employ fp16 with AWQ or GGUF quantised checkpoints.
- **CLI Options:** Pass `--provider ollama` or `--provider lmstudio` with the target `--model` name directly to `climafactskg process`.

---

## Reproducing Benchmarks

```bash
# Install evaluation dependencies
pip install "climafactskg[eval] @ git+https://github.com/climatesense-project/climafacts-kg.git"

# Dry run to audit required and cached queries
climafactskg eval run eval.suite.toml --dry-run

# Run benchmark suite and generate HTML report
climafactskg eval run eval.suite.toml --yes --report

# Regenerate figures and summary CSV
python docs/model-selection/make_plots.py data/eval_runs/<run_directory>
```
