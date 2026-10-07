# 🔍 Competitive & Community Research — How to Make ScrapeWizard Better

> Deep-dive conducted 2026-09-30 across GitHub, Hacker News, Ministry of Testing (The Club),
> official Playwright docs, vendor docs, and practitioner reviews. Findings are checked against
> the **current** codebase (post-sync, commit `6003e10`).
>
> ⚠️ **Reddit could not be accessed** — reddit.com blocks automated fetching. Ministry of Testing
> and Hacker News were used as the practitioner-sentiment substitute. Recommended manual check:
> r/QualityAssurance and r/softwaretesting, searching "self-healing", "Playwright healer", "mabl".

---

## 1. TL;DR — the five findings that matter most

1. **Playwright now ships its own "Healer" agent (free, official).** `npx playwright init-agents`
   gives Planner / Generator / Healer. Microsoft cites roughly **75%+ success on selector
   failures**. It needs an AI loop (VS Code, Claude Code, Codex or OpenCode) and **edits your
   source files**. This is now the baseline every self-healing tool gets compared against.
2. **A near-identical open-source competitor exists: `qa-core-heal`.** It's a deterministic,
   no-LLM healer that proposes diffs you approve, then re-runs to verify. Its published evals:
   **53/53 healable breaks fixed, 21/21 unhealable refused, 0 wrong heals, deterministic across
   runs.** That number is now the credibility bar for "safe healing." (It's tiny: 6 stars, CLI
   only, with no recorder and no dashboard. Those are your openings.)
3. **Practitioners distrust "self-healing" as a marketing term.** The Ministry of Testing thread
   calls these tools mostly "marketing/propaganda", and one tester sums it up as *"flaky is still
   flaky."* Their number-one fear is a **false heal that masks a real bug**: the tool clicks a
   similar-but-wrong element and the test goes green. Trust comes from **refusal, audit logs and
   human review**, not from heal rates.
4. **Locators are not the main cause of flakiness.** Async **timing accounts for about 45%** of
   flakiness (ContextQA root-cause analysis). Healing only fixes one slice of failures, so a tool
   that **classifies why a test failed** before touching it beats one that heals blindly.
5. **The market has settled on "AI plans once, then cheap deterministic replay, re-plan only on
   change."** Stagehand (action cache keyed by page fingerprint), Midscene (plan + locate cache)
   and Magnitude (planner/executor split with plan caching) all do this. **Your architecture
   already is this pattern.** Say so explicitly and use the fingerprints you already capture as
   the cache key.

---

## 2. Landscape map

| Tool | Type | Approach | Relevance to ScrapeWizard |
|---|---|---|---|
| **Playwright Test Agents** (Planner/Generator/Healer) | Free, official | LLM agents via an IDE loop; Healer replays, inspects UI, patches source, re-runs | **Primary threat.** Free and built-in. Reviewers say the Healer is useful, the Generator is *worse than Codegen*, and the Planner hallucinates steps |
| **Playwright Codegen** | Free, official | Recorder with an **assertion toolbar** (visibility/text/value), a **locator picker**, and role → text/label → testid priority | **Your recorder's real benchmark.** If yours records worse locators than free Codegen, the pitch collapses |
| **qa-core-heal** | OSS (MIT, TS) | Deterministic ladder (role→label→placeholder→text→alt→title→testid→CSS/XPath), kind guard, named refusals, diff approval, verify+revert, `heal-log.jsonl`, published evals | **Closest competitor to your healing pitch.** Copy its safety discipline; beat it on recorder, portal and evidence |
| **Healenium** (EPAM) | OSS | Runtime healing via tree-comparison / **LCS** over the stored DOM; Postgres backend stores locator history plus screenshots | The proven "history-based" model. You already store fingerprint history, so lean on it |
| **Stagehand** (Browserbase) | OSS | NL actions, **action cache keyed by page fingerprint**: replay if it matches, fall back to AI and update the cache if not | Validates your "AI once" economics. Their cache-key idea maps directly onto your fingerprints |
| **Midscene.js** (ByteDance) | OSS | Vision-model automation; caches plans and matched elements (51s → 28s on a cache hit) | Same pattern. Their visual replay report is a UX reference |
| **Magnitude** | OSS | Planner LLM plus a tiny 2B vision executor (Moondream); cached plans | HN critique: pure vision "lets them off the hook" on accessibility. **Your built-in a11y checks are a counter-position** |
| **Stagehand / Browser Use / Skyvern / AgentQL** | OSS agents | General browser agents | Adjacent, not direct competitors. Agents are "slow, expensive, and inconsistent" for regression testing (HN) |
| **mabl / Testim / Functionize / Tosca** | Commercial | Codeless plus AI maintenance | Roughly **$450–500+/month**, quote-only pricing, annual contracts, per-user pricing, lock-in (G2). Your local/free/no-lock-in angle is valid |
| **QA Wolf / Octomind / Momentic / Checksum / Meticulous** | Commercial (AI QA) | Managed or hosted generation plus maintenance | QA Wolf found a single agent "overwhelmed" and moved to a **multi-agent triage that separates intentional change / flake / real bug**, with **history** as the key input |
| **Currents / ReportPortal / Allure** | Reporting | Run history, **flaky detection**, error grouping, trace/video | **Your portal competes here.** Currents is paid and cloud-only; Allure is static with no history; ReportPortal is heavy. A local dashboard with history and flaky detection is a real gap |
| **Argos / Lost Pixel / BackstopJS / Percy** | Visual | Baselines, masking, review UI | The bar for your visual check (see §5) |

---

## 3. What practitioners actually say

- **Skepticism is the default.** "None of these fancy expensive tools are as good as they try to
  make them seem" (MoT). Self-healing helps mainly where "IDs are dynamic or locators are too
  hard to define."
- **Masking bugs is the core objection.** The recommended safeguards (MoT insights, SD Times):
  - Heal **locators only, never assertions.**
  - A healed locator must resolve to **exactly one** displayed, actionable element.
  - Use a **high confidence threshold** for silent heals.
  - **Log every heal:** the original locator, the new locator, the signals used and the outcome.
  - **Fail the build if the heal rate spikes.**
  - Offer graduated autonomy: **runtime-only → human-reviewed PR → auto-merge.**
- **The Playwright Healer in real use** (Bondar Academy, BrowserStack, Currents): about 10 minutes
  per fix. It sometimes **weakens assertions** (e.g. `toHaveText` → `toBeVisible`), which hides
  problems. It "cannot prove the product is correct"; a passing re-run only supports the repair.
  It over-edits when its scope isn't constrained.
- **On determinism (HN, Magnitude thread):** developers want "LLMs as an intermediate workflow
  for producing deterministic Playwright code," not LLMs driving every run.
- **On distribution (HN):** bootstrapped AI-QA teams struggle to choose between SDETs and manual
  testers, and between OSS, SaaS and managed service. Generic tools miss "complex,
  product-specific test cases."

---

## 4. Gap analysis — ScrapeWizard vs. market standard (verified in code)

| Capability | Market standard | ScrapeWizard today | Gap |
|---|---|---|---|
| Locator priority | Role → label → placeholder → text → alt → title → testid → CSS/XPath (Playwright docs, Codegen, qa-core-heal) | testid → `tag[aria-label]` CSS → classes → XPath (`selector_engine.py`) | 🔴 **No `getByRole` / `getByLabel` / `getByText`.** Recorded locators are weaker than free Codegen |
| Recorder events | click, fill (input), select, check, press, hover, upload, dialogs, navigation | `click` and `change` only (`recorder.py:132-142`) | 🔴 Many real flows can't be recorded (Enter key, dropdowns, checkboxes) |
| Recorded assertions | Toolbar: assert visibility / text / value | Auto `visible` plus URL only | 🟠 Users can't express intent while recording |
| Heal confidence + ambiguity | Threshold plus "refuse when ambiguous" | ✅ 0.85 threshold + 0.10 ambiguity margin (`healing.py`) | ✅ Good foundation |
| Kind guard | Candidate must match the expected element kind/role | Filters by same tag only | 🟡 Add role/intent check |
| Named refusals | Explain *why* a heal was refused | Log line only | 🟠 Surface refusal reasons in the report/UI |
| Heal audit + approval | `heal-log`, approve-to-persist, verify, auto-revert | No persisted heal events, no approve/reject flow | 🔴 **The trust mechanism practitioners ask for is missing** |
| Never heal assertions | Rule | Not enforced or documented | 🟠 Make it an explicit invariant with a test |
| Failure classification | Locator / assertion / timing / network / app error / env **before** healing | None | 🔴 Healing runs without knowing *why* the step failed |
| Published evals | Mutation suite with public numbers | Mutation tests exist (`test_demo_app_mutations.py`), no published efficacy/safety numbers | 🟠 Publish them: this is your credibility proof |
| Debug artifacts | **Playwright trace (`trace.zip`) + Trace Viewer** | Screenshots only; no tracing | 🟠 Cheap, large win |
| Timing robustness | Web-first auto-waiting assertions | Fixed sleeps in places (recorder `sleep(0.3)`, navigation 1s waits) | 🟠 About 45% of flakiness is timing |
| Visual regression | Masking dynamic regions, disabled animations, per-OS baselines, anti-aliasing tolerance | Raw PIL pixel diff, 5% threshold | 🟠 Will be flaky across machines/OS |
| Auth / secrets | `storageState`, setup login, secrets from env | Passwords masked as `***MASKED***`, so login flows can't replay | 🔴 Blocks most real apps |
| Run history analytics | Flaky detection (pass/fail flip rate), error grouping, heal-rate trend | Runs listed; no flake/heal analytics | 🟠 Your dashboard differentiator vs Allure/Currents |
| Export targets | Playwright **TS** (the ecosystem default), JUnit XML for CI | Python pytest only | 🟡 Add TS export + JUnit |

---

## 5. Recommendations (prioritized)

### P0 — Credibility (without these, reviewers dismiss the tool)

1. **Adopt Playwright's locator ladder in the selector engine and recorder.**
   - Generate `role+name` (the accessible name), `label`, `placeholder`, `text`, `alt`, `title`
     and `testid` candidates **before** CSS/XPath.
   - Verify each candidate is **strict** (exactly one match) at record time, and chain/filter to
     make it unique, the way Codegen does.
   - Store the ladder in the fingerprint as it's stored today. Only the ordering and the kinds change.
   - Acceptance: on the demo app, the primary recorded locator is `getByRole`/`getByLabel` for
     every interactive element that has an accessible name.
2. **Ship the safety model practitioners are asking for.**
   - **Invariant:** heal locators only, never assertions (enforced plus a regression test).
   - **Kind guard:** a candidate must match the expected role/tag intent.
   - **Named refusals:** "ambiguous: 2 candidates within 0.10", "element removed", "closed
     shadow root" and similar, shown in the run report.
   - **HealEvent persistence:** original locator, healed locator, tier, score, signals, verified,
     approved/rejected, reverted.
   - **Graduated autonomy setting:** `runtime-only` (default) → `approve-to-persist` →
     `auto-persist ≥ X`.
   - **Heal-rate spike guard:** mark the run ⚠️ or failed if heals exceed N% of steps.
3. **Classify failures before acting.** For each failed step, classify it as
   `locator_not_found` / `assertion_failed` / `timeout` / `network_error` (4xx/5xx on the critical
   request) / `app_error` (console error) / `navigation_mismatch`. **Only `locator_not_found`
   enters healing.** Everything else is reported with evidence. (This is how QA Wolf and
   qa-core-heal avoid masking bugs.)
4. **Publish your eval numbers.** Extend the mutation suite to the qa-core-heal format: counts of
   healable fixed, unhealable refused, valid locators wrongly touched, and wrong heals, plus a
   determinism check across two runs. Put the table in the README. That's the single strongest
   trust signal available.

### P1 — Recorder parity with free Codegen

5. **Record more event types.** Use `input` (not only `change`), plus `select`, `check`/uncheck,
   `press` (Enter/Tab/Escape), hover (opt-in), file upload, dialogs, and new-tab/navigation.
6. **Assertion recording.** Add a floating toolbar in the recorded page to assert visible / text /
   value on a clicked element, matching Codegen's UX.
7. **Auth that replays.** Support a login setup step or captured `storageState`; resolve masked
   values from env/keyring at run time (`${LOGIN_PASSWORD}`). Never persist the secret.
8. **Remove fixed sleeps.** Replace them with Playwright auto-waiting / web-first assertions
   (`expect(locator).toBeVisible()` style). This targets the ~45% timing class.
9. **Capture Playwright traces.** Call `context.tracing.start(screenshots=True, snapshots=True)`
   per run, save `trace.zip` in run artifacts, and add an "Open in Trace Viewer" action in the
   portal (`npx playwright show-trace` or trace.playwright.dev).

### P1 — Visual checks that don't flake

10. **Masking plus stability.** Allow mask selectors per step, inject CSS to disable animations
    and caret, wait for fonts/images, keep baselines per OS/viewport/browser, and use an
    anti-aliasing-aware comparator (pixelmatch-style) with a per-step threshold. In exported
    tests, use Playwright's native `toHaveScreenshot` with `mask`.

### P2 — Dashboard differentiation (vs Currents / Allure / ReportPortal)

11. **Flaky detection:** a per-test flip rate across the last N runs, "flaky" badges, and optional
    retry-on-failure that marks results as *flaky* rather than *passed*.
12. **Error grouping:** cluster failures by normalized error plus step, so one broken button shows
    as one issue, not 40 red runs.
13. **Heal analytics:** heal rate over time, per-tier distribution, and pending approvals. These
    turn "self-healing" from a claim into a visible, auditable metric.
14. **CI outputs:** JUnit XML plus exit codes, and a **Playwright TypeScript export** alongside
    pytest (the Playwright ecosystem is TS-first).

### P2 — AI layer, positioned against Playwright's Healer

15. **Make fingerprints the cache key (the Stagehand pattern).** If the page/element fingerprint
    matches, replay deterministically. If it drifted, run deterministic tiers. Call AI only when
    those fail, then update the ladder. This is already your design; name it and measure it
    (cache-hit rate, AI calls per run).
16. **Don't rebuild what Playwright gives away.** Consider "export to Playwright project + agent
    definitions" so teams already using `init-agents` can adopt you, while your moat stays in
    **safe deterministic healing, the recorder, and the evidence dashboard.**

---

## 6. Positioning — what to say (and what to stop saying)

- **Stop leading with "AI self-healing."** It triggers the practitioner skepticism documented
  above, and Playwright now gives it away.
- **Lead with safety and evidence:** *"Record a flow. Get Playwright tests with accessible
  locators. When the UI drifts, ScrapeWizard heals locators deterministically, **refuses rather
  than guesses**, and logs every heal for review. Zero AI calls by default. Runs locally, no
  subscription."*
- **Own the differentiators competitors lack together:**
  1. Recorder **plus** portal **plus** run history (qa-core-heal and Playwright's Healer have none of these).
  2. A11y, console and network checks **in the same run** (vision agents skip accessibility).
  3. Published safety evals (0 wrong heals).
  4. Local-first with no seat pricing (vs mabl/Testim at $450–500+/month).
- **The honest threat:** if Playwright's Healer becomes deterministic and qa-core-heal adds a
  UI, the window narrows. Speed on P0 matters more than breadth on Wave 2 features.

---

## 7. How this changes the existing plans

- **MARKET_READY_PLAN.md:** insert P0 items 1–4 **before** the frontend refactor phases. They
  change the product's core value, while the UI refactor changes its polish.
- **PLATFORM_PLAN.md §9 (healing):** add the kind guard, never-heal-assertions invariant, failure
  classification, and graduated autonomy. Replace the "tiers 0–6" pitch language with
  "safe healing + refusals."
- **FRONTEND_PLAN.md:** add a Heal Review queue, flaky badges, error grouping, and an
  "Open trace" action to Run Detail.

---

## Sources

- Playwright Test Agents (official): https://playwright.dev/docs/test-agents
- Playwright locators (official priority order): https://playwright.dev/docs/locators
- Playwright Codegen (assertion toolbar, locator picker): https://playwright.dev/docs/codegen
- Playwright agents review (Bondar Academy): https://bondaracademy.com/blog/playwright-ai-agents-review
- Playwright agents limitations (BrowserStack): https://www.browserstack.com/guide/playwright-agent
- Playwright agents strategies (Currents): https://currents.dev/posts/9-strategies-to-get-the-most-out-of-playwright-test-agents
- qa-core-heal (GitHub): https://github.com/sardar-usman/qa-core-heal
- qa-core-heal launch thread (Ministry of Testing): https://club.ministryoftesting.com/t/looking-for-5-testers-open-source-self-healing-tool-for-broken-playwright-locators/87557
- "Self-healing locators: useful or marketing?" (MoT): https://club.ministryoftesting.com/t/ai-ml-self-healing-locators-useful-or-just-marketing/52681
- Designing safe self-healing automation (MoT): https://www.ministryoftesting.com/insights/when-ai-maintains-your-tests-designing-safe-self-healing-automation
- Hidden risk in self-healing (SD Times): https://sdtimes.com/software-testing/the-hidden-risk-in-self-healing-test-automation-a-governance-blueprint-for-digital-banking/
- Stagehand caching: https://docs.stagehand.dev/examples/caching · https://github.com/browserbase/stagehand
- Midscene caching: https://midscenejs.com/caching
- Magnitude (Show HN): https://news.ycombinator.com/item?id=43796003
- Octomind (Show HN): https://news.ycombinator.com/item?id=37645376
- AI-native QA growth question (HN): https://news.ycombinator.com/item?id=43898735
- Ask HN: agent-driven QA: https://news.ycombinator.com/item?id=48069781
- QA Wolf multi-agent maintenance: https://www.qawolf.com/blog/three-principles-for-building-multi-agent-ai-systems
- Healenium (LCS / tree comparison): https://www.happiestminds.com/wp-content/uploads/2024/02/Adaptive-Automation-Empowering-Seamless-Testing-Through-Self-Healing-Locators-and-LCS-Algorithm.pdf
- awesome-ai-testing (landscape): https://github.com/tugkanboz/awesome-ai-testing
- Flaky test root causes (ContextQA): https://contextqa.com/blog/flaky-tests-automated-testing/
- Visual regression production guide: https://testquality.com/playwright-visual-regression-guide/
- Reporting tools comparison: https://testdino.com/blog/flaky-test-detection
- mabl vs Testim pricing (G2 / Bug0): https://www.g2.com/compare/testim-io-vs-mabl · https://bug0.com/knowledge-base/mabl-pricing
