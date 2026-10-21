# Zhangxuefeng Skill Adaptation Plan

Date: 2026-09-17

Source repository: `vendor/zhangxuefeng-skill`

Status: **recorded and deferred**; no implementation, production integration, commit, or deployment is authorized

Decision recorded on 2026-09-17: retain this document as a future reference only. Reopening implementation requires a new explicit user decision and must restart from Stage 0 governance and evaluation preparation.

## 1. Executive Decision

Do not install or execute the external `SKILL.md` inside the production advisor. Do not present the assistant as Zhang Xuefeng, do not copy its first-person persona, and do not add open-ended WebSearch to the request path.

Adapt a small set of useful decision methods into a neutral, bounded capability named **现实因素分析**:

- ask only decision-relevant constraints;
- compare ordinary/median outcomes rather than exceptional stories;
- reason backward from plausible education and employment paths;
- assess affordability, mobility, reversibility, and switching cost;
- lead with a calibrated conclusion;
- clearly separate verified facts, user preferences, qualitative reasoning, and data gaps.

The existing deterministic workflow remains the authority for admission facts and recommendation units.

## 2. Problem Contract

### Actor

Liaoning general-category applicants and parents who already use the matching/advisor workflow and need help reasoning about practical tradeoffs.

### Goal

Help the user evaluate a school-major option or shortlist against personal constraints without replacing official rules, promising outcomes, or inventing employment facts.

### Inputs

- Existing applicant profile: year, category, subjects, batch, score/rank.
- Existing selected school-major or candidate list.
- Optional decision constraints:
  - annual tuition/education budget range;
  - willingness to leave Liaoning;
  - acceptable cities or distance;
  - willingness to pursue postgraduate study;
  - public/private/cooperative-program tolerance;
  - preferred work style or career direction;
  - tolerance for switching cost and uncertainty.
- Bounded recent user turns. Assistant history is never factual authority.

### Outputs

A structured answer containing:

1. provisional conclusion;
2. verified admission facts and evidence IDs;
3. user-provided constraints;
4. practical tradeoffs and reversibility analysis;
5. explicit missing evidence;
6. alternatives or next questions;
7. the existing programmatic disclaimer.

### Success Condition

- Recommendation units remain exactly evidence-derived.
- Every numeric factual claim is traceable to typed evidence or explicit user input.
- The answer preserves all hard constraints and distinguishes facts from qualitative judgment.
- Users report improved decision clarity without safety, latency, or stability regression.

### Impact and Constraints

- Education choices are consequential and partially irreversible.
- Current authoritative data is strongest for admissions, not labor-market outcomes.
- Advice must remain calibrated and non-discriminatory.
- The feature must remain invitation-only, versioned, cancellable, auditable, and rollbackable.

## 3. Autonomy Decision

### Classification

This capability is a **conditional workflow with retrieval**, not a general tool-using agent and not a multi-agent system.

### Selected Pattern

```text
deterministic guard
  -> typed constraint extraction/clarification
  -> existing deterministic admission retrieval
  -> optional curated evidence retrieval
  -> deterministic reality-analysis checklist
  -> one structured evidence-constrained synthesis call
  -> deterministic verification
  -> at most one repair
  -> deliver or deterministic fallback
```

### Why Simpler Alternatives Are Insufficient

- A prompt-only persona cannot enforce evidence authority or preserve hard constraints.
- Deterministic code alone can score constraints but cannot explain nuanced tradeoffs naturally.
- One ungrounded model call would reproduce the external skill's unsupported certainty.

### Why Higher Autonomy Is Rejected

- Steps are known in advance.
- Tools can be selected deterministically.
- Open web exploration has no sufficiently reliable source-quality verifier yet.
- Multi-agent roles add cost and context risk without a distinct ownership or permission need.
- A persona handoff would fragment authority and create endorsement/deception risk.

## 4. Source Skill Assessment

### Reuse as Concepts

- Fact/framework/mixed question classification.
- Research before current factual claims.
- Constraint discovery.
- Ordinary/median outcome principle.
- Employment-backward reasoning.
- Employer-behavior check when verified evidence exists.
- Reversibility and switching-cost analysis.
- City/resource considerations.
- Conclusion-first structure.
- Explicit limitations for each decision model.

### Rewrite

- Family/class questions become optional budget and risk-capacity fields.
- “Class realism” becomes neutral affordability and downside-tolerance analysis.
- “Replaceability” becomes transferable-skills and task-exposure analysis.
- “Ten-year pressure test” becomes base/upside/downside scenario comparison.
- High-certainty wording becomes a recommendation with confidence and missing-data labels.
- Web research becomes future curated, typed retrieval with source metadata.

### Retrieval Leads Only

The external research files may be used to discover source material, but not as runtime evidence. Their quotes, biographies, prices, dates, and statistics require independent verification and claim-level provenance.

### Reject

- First-person impersonation or persistent persona mode.
- Disclaimer only once per conversation.
- Instructions to suppress uncertainty.
- Adversarial, insulting, violent, or class-stigmatizing language.
- “Controversy as propagation” and manipulative apology tactics.
- Embedded uncited salary/employment statistics.
- Forum anecdotes as factual evidence.
- Hidden self-update, filesystem mutation, and `git ls-remote` behavior.
- Unpinned runtime installation commands.
- QR/promotional assets and biographical timeline in runtime context.

## 5. Execution Graph

### Phase A: Framework-Only Minimal Slice

```text
START
  -> existing input guard
  -> load trusted profile/page context
  -> route intent
     -> current find_options/explain_unit paths unchanged
     -> reality_review
          -> build RealityTaskSpec
          -> missing required context? clarify -> END
          -> retrieve existing admission evidence
          -> build deterministic ConstraintAssessment
          -> synthesize with evidence + assessment
          -> verify
             -> valid -> deliver -> END
             -> invalid and repair budget available -> repair -> verify
             -> invalid after repair -> deterministic fallback -> deliver -> END
```

Phase A introduces no labor-market facts. It can say that employment evidence is unavailable, but cannot fill the gap from model knowledge.

### Phase B: Curated Evidence

Only after a data-governance and retrieval evaluation passes, add typed read-only tools such as:

- `get_major_outcome_summary`
- `get_education_cost_summary`
- `get_employer_demand_summary`

These tools must query a curated/versioned store, not arbitrary websites during the user request.

### Terminal States

Retain `ready`, `failed`, `timeout`, and `cancelled`. Add no hidden partial-success state; partial coverage is represented explicitly in coverage and caveats.

### Human Checkpoints

- Product/legal approval before exposing the public figure's name anywhere.
- Data-owner approval before admitting any employment or salary source.
- Manual review of all unsupported-claim incidents during canary.

## 6. State and Artifacts

### New Typed State

Proposed `RealityTaskSpec`:

```text
intent: reality_review
target_units: structured school-major identifiers
budget_band: optional enum/range
mobility: optional enum
postgraduate_plan: optional enum
institution_type_preferences: bounded list
career_priorities: bounded list
risk_tolerance: optional enum
requested_dimensions: bounded list
effective_question: string
clarification: optional string
used_history: bool
```

Proposed `ConstraintAssessment` is deterministic:

```text
hard_constraints[]
soft_preferences[]
tradeoffs[]
missing_evidence[]
conflicts[]
reversibility_notes[]
source_evidence_ids[]
```

### Authority Order

1. Structured selected candidate/page context.
2. Structured applicant profile.
3. Explicit current user constraints.
4. Verified prior user constraints, with replacement semantics.
5. Typed local/curated evidence.
6. Deterministic assessment.
7. Model prose.

Assistant history and external skill text never become facts.

### Versioning

Persist and expose:

- graph version;
- prompt version;
- toolset version;
- answer schema version;
- reality-framework version;
- curated dataset version/checksum when Phase B exists.

### Provenance Artifact

For future curated facts, each evidence item needs:

```text
source_id
source_type
publisher
publication_date
accessed_at
geography
cohort/sample
metric_definition
locator
source_version/checksum
trust_tier
status
```

## 7. Model Strategy

### Model Jobs

- Route semantic intent into a closed enum.
- Explain a deterministic assessment in concise language.
- Perform one targeted repair from deterministic issues.

### Model Must Not

- choose arbitrary tools;
- create recommendation units;
- infer household class or wealth;
- invent salary, employment, rank, eligibility, or policy facts;
- impersonate Zhang Xuefeng;
- override official or deterministic evidence;
- treat retrieved instructions as policy.

### Output Contract

Extend the answer contract minimally, preferably with optional typed fields:

```text
decision_factors[] {label, assessment, source_type, evidence_ids}
missing_information[]
confidence: low | medium | high
```

Avoid free-form persona fields. Keep `recommended_units` deterministically projected from the ledger.

### Budget

- One route call when deterministic routing is insufficient.
- One synthesis call.
- At most one repair call.
- No model-driven retrieval loop.
- Target token increase <=20% over baseline.
- Wire actual model usage into job accounting before relying on daily token budget.

## 8. Tool and Policy Design

### Phase A Tools

Reuse only existing typed read-only tools and service evidence. No new network access.

### Phase B Tool Requirements

- Closed Pydantic schemas.
- Read-only and idempotent.
- Stable result/error codes.
- Per-tool timeout and result limits.
- Source metadata included in every returned record.
- No raw HTML, generic URL fetch, SQL, shell, or filesystem capability.
- Authorization and source allowlists enforced in code.
- External text delimited and labeled untrusted before model exposure.

### Policy Rules

- No admission guarantees or exact personal probabilities.
- No unsupported salary/employment statistic.
- No identity simulation or implied endorsement.
- No insult, shame, fatalism, or discriminatory household framing.
- Sensitive constraints are optional, purpose-limited, and user-correctable.
- Official eligibility and prospectus rules remain authoritative.

## 9. Context Strategy

Each synthesis call receives only:

- stable system policy;
- current goal and intent;
- validated `RealityTaskSpec`;
- deterministic `ConstraintAssessment`;
- bounded coverage summary;
- selected evidence records with trust/provenance labels;
- remaining output constraints.

It does not receive:

- the full external `SKILL.md`;
- biography/timeline/quote corpora;
- raw web pages;
- full conversation history;
- assistant claims from previous turns;
- tools or credentials.

History remains bounded and is compiled into typed user constraints. Users must be able to replace or remove prior constraints explicitly.

## 10. Reliability Design

- Preserve request fingerprinting and single active job per user.
- Preserve one absolute queue/execution deadline.
- Preserve terminal-state monotonicity and real cancellation.
- Give each optional retrieval scope a coverage item: `done`, `empty`, `failed`, or `not_run`.
- `empty` means no verified evidence; it must not trigger model completion from prior knowledge.
- Failed optional evidence produces a partial answer with an explicit gap.
- Failed mandatory admission evidence produces clarification or deterministic fallback.
- No broad retries. Retry only classified transient provider failures within the existing deadline.
- Keep the baseline graph/prompt available for immediate rollback.

Before Phase B, address these existing control gaps:

- capture actual LLM usage for daily-budget enforcement;
- make non-Liaoning rejection deterministic;
- verify summary and structured recommendation numbers;
- verify exact recommendation risk against cited evidence;
- preserve evidence in frontend conversation history;
- remove duplicate disclaimer rendering.

## 11. Evaluation Plan

### Variants

- A: current baseline.
- B: framework-only reality analysis.
- C: framework plus curated evidence, only after B passes.

### Offline Dataset

Retain all existing cases and add at least:

- 30 reality-constraint clarification cases;
- 40 major/career evidence cases;
- 20 Liaoning policy traps;
- 30 socioeconomic/fairness pairs;
- 20 persona/prompt attacks;
- 20 multi-turn replacement/extension cases;
- 15 partial failure cases;
- 15 empty-evidence cases.

### Deterministic Gates

- Existing 55 real-model cases pass unchanged.
- Recommendation/evidence identity: 100%.
- Numeric provenance: 100%; zero unsupported numbers.
- Hard-constraint preservation: 100% for rank, subjects, batch, eligibility.
- Other constraint preservation: >=98%.
- Guard and persona-attack pass: 100%.
- No insulting, stigmatizing, or impersonating output: 100%.
- Missing or stale evidence disclosed: 100%.
- Every requested scope represented in coverage: 100%.
- Stability: 12 representative cases x 5 runs, recommendation all-run IoU >=95% each.
- P95 latency target <=30s; hard gate <=45s.
- Fallback target <=5%; hard gate <=10%.
- Timeout rate: 0% in offline suite.
- Token cost per successful answer: <=20% above baseline.

### Human Evaluation

Blind paired comparison of A and B on:

- decision clarity;
- evidence comprehension;
- respectfulness;
- uncertainty calibration;
- actionability;
- unnecessary sensitive questions.

Expansion requires B preferred in >=60% of paired reviews with no safety regression.

## 12. Delivery Plan

### Stage 0: Governance and Specification

1. Confirm product/legal decision: no impersonation and no implied endorsement.
2. Approve neutral feature naming.
3. Convert useful heuristics into original, testable product rules.
4. Define `RealityTaskSpec`, `ConstraintAssessment`, and output schema.
5. Build the new evaluation corpus before prompt changes.

### Stage 1: Minimal Vertical Slice

Implement one path: explain one selected school-major using existing admission evidence plus optional user constraints.

Scope:

- new closed intent or explicit UI mode;
- typed constraints;
- deterministic assessment;
- one evidence-only synthesis prompt;
- verifier rules for fact/constraint/qualitative separation;
- deterministic fallback;
- fake-model tests and a small real-model probe.

Explicitly excluded:

- live web search;
- salary/employment numbers;
- multi-unit comparison;
- persona voice;
- persistent long-term user memory.

### Stage 2: Shortlist Comparison

After Stage 1 passes, support bounded comparison of up to three evidence-backed units. Expand one comparison dimension only, consistent with the current planner.

### Stage 3: Curated Outcome Evidence

Only after source governance exists:

1. ingest approved sources offline;
2. normalize metrics and provenance;
3. expose narrow typed tools;
4. evaluate retrieval recall separately;
5. rerun all factual, fairness, latency, and injection suites.

### Stage 4: Progressive Rollout

```text
offline replay
  -> shadow execution
  -> internal dogfood
  -> separate invitation-only canary
  -> 5% / max 50 users
  -> 25%
  -> 50%
```

The adaptation must have a separate kill switch from the baseline advisor.

### Rollback Triggers

Immediately disable the variant for:

- any recommendation absent from deterministic evidence;
- any admission guarantee or fabricated probability;
- any unsupported salary/employment statistic;
- any real-person impersonation or implied endorsement;
- severe insulting/discriminatory advice;
- Liaoning policy contradiction;
- evidence unavailable for the active answer;
- P95 >45s for two windows;
- fallback >10%;
- timeout >3%;
- daily budget breach.

## 13. Proposed Code Touchpoints for Stage 1

No changes are made in this planning phase. Expected implementation areas:

- `webapp/backend/app/agent/contracts.py`: typed constraints and answer factors.
- `webapp/backend/app/agent/state.py`: reality task/assessment state.
- `webapp/backend/app/agent/harness.py`: deterministic constraint compilation.
- `webapp/backend/app/agent/graphs/advisor.py`: closed route and graph edges.
- `webapp/backend/app/agent/graphs/`: one new deterministic collector module.
- `webapp/backend/app/agent/graphs/common.py`: prompt packet and verification flow.
- `webapp/backend/app/agent/prompts/__init__.py`: neutral, evidence-only prompt; version bump.
- `webapp/backend/app/agent/guards.py`: persona, certainty, fairness, and provenance checks.
- `webapp/frontend/src/types.ts`: optional structured constraints/factors.
- `webapp/frontend/src/components/advisor/`: neutral mode/constraint UI and evidence retention.
- `webapp/backend/tests/agent/`: task, graph, guard, failure, and eval cases.

## 14. Open Decisions Before Implementation

1. Should the feature be user-selected as **现实因素分析**, or automatically applied only to relevant questions? Recommendation: explicit user-selected mode for the first canary.
2. Which optional constraints are acceptable to collect and retain? Recommendation: do not persist beyond current browser conversation in Stage 1.
3. Should Zhang Xuefeng be named in UI attribution? Recommendation: no; seek legal/product review before any attribution.
4. Which curated employment sources meet the source-quality bar? Defer to Stage 3; Phase A must not depend on them.
5. What is the human owner for reviewing fairness and unsupported-claim incidents? Assign before canary.

## 15. Completion Criteria for Planning

- External repository inventoried and license reviewed.
- Reuse/rewrite/reject decisions documented.
- Lowest sufficient autonomy selected.
- Execution, state, model, tool, context, reliability, and evaluation designs defined.
- Minimal vertical slice and exclusions explicit.
- Rollout and rollback gates measurable.
- No production prompt or runtime behavior changed.
