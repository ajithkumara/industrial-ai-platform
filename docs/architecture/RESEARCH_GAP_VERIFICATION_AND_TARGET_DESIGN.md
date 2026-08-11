# Research Gap Verification & Target Design

**Method:** Full text of all 10 uploaded IEEE PDFs extracted and read. Every claim in `Research_Gap_Statement_Adaptive_Orchestration.docx` checked against the actual paper text. Quotes below are verbatim from the PDFs.

**Verdict in one line:** The gap is **real and defensible**, but **three claims as currently worded will not survive a rigorous examiner** and must be restated. One newly-discovered citation makes the CloudForest scoping decision non-negotiable.

---

## PART 1 — CORPUS INTEGRITY (fix before submission)

| Issue | Detail | Action |
|---|---|---|
| **Missing paper** | The gap statement cites **Kayan et al., "Edge ML on Robotic Arms," IEEE IoT Journal 2025** three times — including the headline "10 Hz not viable, 3 Hz actual" evidence and the "placeholder threshold" quote. **This PDF is not in the corpus.** | Either add the PDF or remove the citations. Three of your strongest quotes currently rest on a paper not in the reviewed set. |
| **Uncited paper present** | **Feng et al., "Make the Rocket Intelligent at IoT Edge: StepGAN," IEEE IoT-J vol. 9 no. 4, 2022** is uploaded but appears in no table. | Add to the corpus table (it is edge-only AD with cloud used for pre-training — supports the "static assignment" claim) or drop it. |
| **Miscited limitation** | Architecture v1.0 attributes to Hareram et al. (ICICNCT 2025): *"WAN failure causes detection halt... acknowledged in Section V-B as an explicit limitation."* The paper's actual stated limitation is **cross-domain generalisation**: *"such as manufacturing, smart grids, and transportation systems remains to be validated. We acknowledge this as a limitation."* No WAN-failure limitation is stated. | **Remove or re-source this claim.** It is the evidence for Failure Mode 1 and is currently unsupported. |
| **Hareram not in gap table** | Hareram is cited in the architecture doc but absent from the gap statement's 9-paper table. | Reconcile to one canonical corpus list. |

**Note in your favour:** Hareram et al. builds on **Azure Event Hubs + MLflow** — published IEEE precedent for exactly the stack `industrial-ai-platform` uses. Cite it when justifying the Azure substitution.

---

## PART 2 — CLAIM-BY-CLAIM VERIFICATION

### ✅ VERIFIED — quote exactly as written

| Claim | Verbatim evidence |
|---|---|
| Li et al. name task allocation without describing it | Section IV-D-1 in full: *"Task Allocation: The task allocation algorithm determines whether a specific computational task should be executed at the edge or in the cloud."* Next line jumps to knowledge distillation. **One sentence. No algorithm. Confirmed.** |
| Li et al. use a predefined failure threshold | *"the RUL is estimated by extrapolating the trend to a predefined failure threshold."* |
| **Li et al. edge is simulated** | *"The experiments were conducted on a server with Intel Xeon E5-2680 v4 CPU, 128GB RAM, and NVIDIA P5000 GPU. For the edge layer, we simulated 10 edge nodes."* **Stronger than you claimed — worth quoting directly.** |
| Fed-RAM tested only on non-IIoT benchmarks | *"We evaluated the proposed method using two primary datasets: MNIST and CIFAR-10."* |
| Fed-RAM threshold derives from training statistics | *"E = μ + γ·σ where μ and σ represent the mean and variance of the reconstruction error **based on the training data**."* |
| Mahmud et al. on Kubernetes / Mesos | Both quotes verbatim-accurate. |
| Mahmud validated by simulation only | *"within a simulated microservice orchestration environment using the iFogSim2 simulator."* |
| PPLAD replaces one static assignment with another | *"the huge data volume further makes anomaly detection in the cloud result in high latency and high costs"* → then fixes all inference at edge permanently. |
| Survey names orchestration policy design as open | *"The challenge lies in designing orchestration policies that balance responsiveness, energy efficiency, and system resilience in dynamic 5G-IoT environments."* |
| Chandrappa cloud role is periodic sync, no outage handling | *"the system performance may be affected by network partitioning scenarios where fog nodes lose connectivity to the cloud coordination layer"* — named as an unresolved limitation. **Direct support for your H2.** |

### ⚠️ MUST BE RESTATED — will not survive as written

**(A) "Validated on real constrained edge hardware — Kayan et al. is the only paper with real hardware deployment." — FALSE.**

- PPLAD: *"Deployment experiments are performed on two resource-constrained IoT edge devices: Raspberry Pi 4b and NVIDIA Jetson Xavier NX"* (plus a third "Thick PC" tier).
- TinyML: deployed on ESP32-S3-EYE microcontroller — more constrained than your Jetson-class target.

At least two papers deploy on real constrained hardware. **Defensible restatement:** *"No paper validates on constrained hardware **under controlled network degradation**. PPLAD and TinyML deploy on real devices but evaluate only accuracy and inference time on a stable network; neither injects latency, jitter, or WAN loss."* — This is true across all 10 and is the claim that actually matters for your thesis.

**(B) "Context-aware escalation is absent from all nine papers." — OVERSTATED.**

Li et al. Section IV-D-3: *"The confidence-based fusion approach prioritizes edge results when they have high confidence, while incorporating cloud predictions for more uncertain cases."* That is confidence-driven cloud involvement.

**The distinction you must draw (and it is a real one):** Li et al. perform **decision fusion** — both edge and cloud results already exist, and confidence weights how they are *combined*. You perform **placement decision** — confidence determines whether the cloud is invoked *at all*. Fusion assumes the cloud is always reachable and always computed; placement treats invocation as the variable. State it this way and the claim holds.

**(C) "No existing paper implements a runtime mechanism that dynamically reallocates computational tasks." — CONTESTABLE.**

Mahmud et al. implement a **Dynamic Rescheduling Mechanism**: *"if the anomaly score St exceeds a pre-defined threshold θ, the microservice is flagged as potentially untrusted... the orchestration layer triggers its Dynamic Rescheduling Mechanism"* and *"the orchestration layer could migrate the billing workload to a backup instance."* That is runtime workload migration.

**Four differentiators that survive** — use all four, not just one:
1. **Trigger:** theirs is security/trust anomaly; yours is network quality, device resource pressure, and model uncertainty.
2. **Topology:** theirs migrates microservice→different edge node (peer relocation); yours reallocates inference across the **edge↔cloud tier boundary**.
3. **Threshold provenance:** theirs is *"a pre-defined threshold θ"*; yours is empirically calibrated per environment (P95 × multiplier).
4. **Validation:** theirs is iFogSim2 simulation; yours is executing software under kernel-level `tc netem` degradation.

### 🔴 CRITICAL FINDING — changes your architecture decision

The survey paper (Section on layered approaches) states:

> *"Shi et al. propose a dual-tiered intrusion detection framework wherein simple classifiers at the edge flag suspicious behavior and escalate to cloud-based deep models for further analysis. This reduces latency while maintaining high detection accuracy."*

**Cascade inference (lightweight edge model escalating to a heavy cloud model) is already published prior art, and it is cited inside your own corpus.**

Consequence: **CloudForest cannot be a novelty claim.** If you present "edge Isolation Forest + cloud LSTM-AE" as the contribution, an examiner holding this survey ends the defence in one question.

What *is* still unclaimed: **the runtime policy that decides when to escalate, under live network and resource pressure, with empirically calibrated thresholds, and with a defined fallback when the cloud tier is unreachable.** Shi et al. escalate on classifier output alone, assuming cloud availability. Nobody governs escalation by *live infrastructure context*. That is your contribution, and it is intact.

**This settles the earlier question definitively: CloudForest is RQ2 supporting evidence, never a co-equal hypothesis.**

---

## PART 3 — THE RESTATED GAP (defensible version)

> Existing Edge–Cloud IIoT systems assign inference roles at design time and govern any inter-tier communication with thresholds that are fixed a priori or derived only from training data. Where runtime reallocation exists, it is triggered by security/trust signals between peer edge nodes (Mahmud et al.) rather than by infrastructure state across the edge–cloud boundary. Where confidence-driven cloud involvement exists, it takes the form of decision fusion over results already computed (Li et al.) or is explicitly deferred to future work (TinyML et al.). Where cascade escalation exists (Shi et al., via survey), it is governed by classifier output alone and presumes cloud availability. No system in the corpus:
>
> - **C1.** adjusts inference placement in response to measured network degradation or WAN loss;
> - **C2.** derives its orchestration thresholds empirically from the deployment environment rather than fixing them a priori;
> - **C3.** guarantees detection continuity and bounded evidence loss for outages of arbitrary duration;
> - **C4.** implements *and measures* confidence-triggered escalation under degraded network conditions.

**Claim strength after verification:** C1 **strong** (zero papers test network degradation) · C2 **strong** (universally fixed thresholds; your CPU-dilution finding is direct empirical support) · C3 **strong** (Chandrappa names partitioning as unsolved) · C4 **moderate** — frame as *implemented and measured within an adaptive policy*, never as *first to do cascade inference*.

**Suggested paper title framing:** *context-calibrated* orchestration. "Adaptive" is claimed by Fed-RAM and Mahmud; "calibrated" is not claimed by anyone and is precisely what C2 delivers.

---

## PART 4 — MODE TAXONOMY (reconciles all four documents)

Four modes. This is the union of Architecture v1.0 (EDGE_ONLY/HYBRID/CLOUD_OPTIMISED) and Sprint Report v3 (which added EDGE_AUTONOMOUS and dropped HYBRID). Both were right about different things.

| Mode | Trigger | Edge | Cloud | Evidence for |
|---|---|---|---|---|
| `CLOUD_OPTIMISED` | RTT & CPU below calibrated thresholds; edge confident | infers (authoritative) | full telemetry streamed, analytics | H1 baseline, H3 denominator |
| `HYBRID` | edge confidence low **OR** severity critical; cloud reachable | infers (authoritative) | **re-scores event — CloudForest lives here** | **C4 / RQ2** |
| `EDGE_ONLY` | RTT > threshold **OR** CPU > threshold; cloud still reachable | infers, local alerts | offload suspended, tiered buffering | C1, H3 |
| `EDGE_AUTONOMOUS` | cloud unreachable (probe fails) | infers, local alerts | none until recovery | C3 / H2 |

**Invariant that protects every latency claim:** the edge model is the sole real-time decision authority in all four modes. Cloud never gates, delays, or overrides a live decision. HYBRID adds a *second opinion recorded afterwards*, not a second decision-maker.

---

## PART 5 — EVENT CONTRACTS (platform alignment)

Existing, live and verified: `bearing_sensor.yml`, `bearing_inference.yml`.

**Modify `bearing_inference.yml`:** rename target `label` → `ground_truth_label` (prediction/ground-truth conflation is a research-integrity risk); add `edge_confidence`, `model_version`, `policy_version`, `calibration_tag`, `cloud_reachable`, `latency_ms`, `cpu_pct`. The schema-aware null fallback in `flatten_payloads.py` means these can ship before the orchestrator emits them.

**Three new asset types:**

| Asset type | Volume | Key fields | Serves |
|---|---|---|---|
| `orchestrator_mode` | per transition (rare) | `from_mode`, `to_mode`, **`trigger`** (network\|cpu\|confidence\|severity\|recovery), `rtt_ms`, `cpu_pct`, `edge_confidence`, `breach_count`, `policy_version` | C1, C2, mode-switch latency — **the primary thesis evidence** |
| `context_snapshot` | 1 Hz → **bridge breach samples + 1-per-30s heartbeat only** | `rtt_ms`, `cpu_pct`, `ram_pct`, `cloud_reachable` | C2 calibration, autonomy windows |
| `cloud_validation` | per HYBRID escalation | `event_id` (correlation), `cloud_score`, `cloud_decision`, `cloud_model_version`, `agrees_with_edge`, `validation_latency_ms` | **C4** |

`trigger` is the single most important new field: it is the direct evidence that the policy is context-driven rather than fixed, which is claim C1/C2 in one column.

---

## PART 6 — GOLD LAYER (build order)

Dependency-ordered. Each table maps to a hypothesis; none are generic.

1. **`gold.mode_history`** ← `orchestrator_mode`. Per transition: time-in-mode (LEAD window), switch latency (breach→transition), trigger breakdown. **Serves:** mode-switch latency < 5s, H3 denominator, C1.
2. **`gold.detection_performance`** ← `bearing_inference`. Per mode × model_version × scenario window: TP/FP/FN/TN from `anomaly` vs `ground_truth_label != 'normal'`, precision/recall/F1, P50/P99 `infer_ms`. **Serves:** H1, RQ3. *(Requires the rename first — refresh is cheap now, expensive after a real evaluation run.)*
3. **`gold.edge_autonomy`** ← `bearing_inference` + `context_snapshot`. Inference counts within `cloud_reachable = false` windows; continuity %; gap detection. **Serves:** H2, C3.
4. **`gold.cloud_egress`** ← `mode_history` + inference counts. Events transmitted vs generated per mode; cross-check against Event Hub `IncomingMessages`. **Serves:** H3.
5. **`gold.escalation_efficacy`** ← `bearing_inference` ⋈ `cloud_validation` on `event_id`. Agreement rate sliced by `edge_confidence` bucket × network condition × severity. **Serves:** C4/RQ2 — **this is the novel result table.**

`asset_health_summary` remains as the domain-agnostic layer above these.

---

## PART 7 — WHAT THIS MEANS FOR EACH ROLE

**Thesis supervisor:** the gap holds after verification, but fix the three restatements and the missing Kayan citation *before* the next supervisor meeting. The restated C1–C4 are narrower and much harder to attack. Retitle around "context-calibrated."

**Research architect:** your strongest single asset is the CPU-dilution finding from Sprint R1 — it is empirical proof that a threshold is environment-specific and non-transferable, published nowhere in the corpus. Lead C2 with it.

**Lakehouse / platform architect:** two YAML files, one rename, one join. The entire research evidence layer is config, not code — which is itself the platform's thesis.

**ML platform architect:** the cloud validation model belongs in a triggered Databricks job over Silver, registered in Databricks MLflow. Do not build a serving endpoint; nothing in the design requires synchronous cloud inference.

**CTO / commercial:** cascade inference being prior art is good news commercially — you are not betting the product on an unproven ML idea. The moat is the orchestration policy and the offline guarantee, exactly as the roadmap's competitive table already argues.
