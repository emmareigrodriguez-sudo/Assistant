# QC Revamp — Spike

## Summary (for product discussion)

We looked into the QC code to answer one question for two proposed features: **can we build them, and how big are they?** Short answer: **yes, both are feasible, both are relatively small, and they fit the existing design cleanly.**

### The two features

**1. Automatic rejection of bad QC results**
Today, when a QC result triggers an alarm, the strongest thing the system does is *refuse to auto-accept it* and leave it for someone to review by hand. It never rejects anything on its own — a person always has to step in.

We want the system to be able to **reject certain results automatically**, based on how serious the alarm is.

How it works today is helpful here: every alarm already has a "level" — *Information, Warning, or Error*. We simply **add one more level above Error, called "Reject."** A lab admin can then mark any alarm (or QC rule) as "Reject," and from then on the system handles those automatically instead of queuing them for manual review. Nothing changes for existing customers unless they choose to use the new level.

On top of that, when an admin sets an alarm to "Reject," they can also **type in a comment** (e.g. "Auto-rejected: result outside acceptable range"). That comment is then **automatically attached to every result the system rejects** for that alarm — so a reviewer looking at the result later sees *why* it was rejected, in the lab's own words. The good news is QC results already support comments today, so we're reusing an existing mechanism, not inventing one.

**2. "Switched Levels" alarm**
QC controls often come in multiple levels (e.g. a Level 1 and a Level 2). Today, if an operator accidentally runs the Level 2 control but tells the system it's Level 1, and the value happens to fall inside the Level 1 range, **the system accepts it as a pass** — even though the wrong material was measured. That's a real quality blind spot.

We want a new alarm that catches this: if a result **fails its own level but would have passed a different level**, the system flags it as a likely "switched level" mistake. Combined with feature 1, a lab could even have these auto-rejected.

### What this means in practice

| | Effort | Risk | Customer impact |
|---|---|---|---|
| **1. Auto-reject level** (incl. configurable reject comment) | ~3.5–4.5 weeks | Low — purely additive; off until an admin turns it on | Labs can automate handling of clearly-bad results, less manual review, with a custom explanation attached to each rejection |
| **2. Switched Levels alarm** | ~2–3 weeks | Low — only fires on a specific suspicious pattern | Catches a genuine safety gap that passes silently today |

**Recommended order:** build feature 1 first — it creates the "Reject" capability that feature 2 can then plug into. Feature 2 on its own is just a flag; together they let labs auto-reject mislabelled controls.

**Key points for the discussion:**
- Both features **reuse the existing alarm machinery** — we're extending what's there, not building something new and parallel. That's why the estimates are small and the risk is low.
- Both are **opt-in / configurable** — existing customer behaviour is unchanged until a lab admin chooses to enable them.
- Feature 1 touches a **regulated area** (auto-rejecting a quality record), so we'll need to confirm the audit-trail and any "require confirmation" expectations with regulatory — flagged in the detail below.

> The rest of this document is the technical investigation backing the summary above — the exact code locations, proposed changes, edge cases, and effort breakdown.

---

## Technical Investigation

Deep-dive into the `solutionsuite-foundation` codebase for two QC enhancements:

1. **Automatic rejection rules** — a new "Error and Reject" alarm severity level
2. **Switched Levels alarm** — detect when a multi-level control is run on the wrong level

> **Source:** `Roche-DIA-RIS-PointOfCare/solutionsuite-foundation` (branch `dev`). All QC business logic lives in IRIS/ObjectScript classes exported as XML under `src/DB/Source/Logic/ACB/Classes/`. Paths below are relative to that root unless stated otherwise.

---

## 0. How QC alarms and severity work today (shared foundation)

Understanding the existing model is essential because both features build on it.

### Severity scale ("alarm action")

Defined in `ACB/Routines/MainInclude.xml`:

```objectscript
#Define AlarmActionUndefined   -1
#Define AlarmActionNone         0
#Define AlarmActionInformation  1
#Define AlarmActionWarning      2
#Define AlarmActionError        3
```

This integer is **the "level"** referred to in the requirement. It is stored in three places:

| Table | Field | Role |
|-------|-------|------|
| `Data.alarm.tAlarmTypes` | `DefaultAction` | Factory default severity for an alarm code (e.g. `QCOR`) |
| `Data.alarm.tAlarmsMapping` | `AlarmAction` | Per-instrument-type / per-result-type / per-facility override of severity |
| `Data.QC.tQcResultAlarms` | `AlarmAction` | The severity actually stamped onto a specific QC result |

### How severity is resolved at runtime

`co.val.cAlarmsMapping.GetSystemAlarmAction(AlarmID, InstrumentType, ResultType)`:
1. Looks for a site-specific mapping row in `tAlarmsMapping` → returns its `AlarmAction`.
2. Falls back to `cAlarms.GetDefaultAction(AlarmID)` → the `DefaultAction` on `tAlarmTypes`.
3. Returns `-1` (Undefined) if the alarm is not mapped → alarm is **suppressed** (not raised).

`ResultType`: `1 = Patient`, `2 = QC`, `3 = Proficiency`.

### The auto-accept decision — the single most important piece of logic

`Data.QC.tQcResult.AutomaticValidation()` (lines ~947–1200 of `Data/QC/tQcResult.xml`) is the heart of QC validation. Simplified:

```objectscript
// 1. Range check → raises QCOR (out of range), QCNR (no range), QCQN (qualitative/numeric mismatch)
If ((fltMeasurementValue >= fltMin) && (fltMeasurementValue <= fltMax)) {
    Set ..blnAccepted = $$$YES
} Else {
    Set ..blnAccepted = $$$NO
    // build QCOR alarm, look up its AlarmAction, add to alarm list
}

// 2. Scan all alarms for the highest severity
Set blnErrorAlarmExists = $$$NO
For each alarm in pobjAlarmList {
    If (alarm.AlarmAction = $$$AlarmActionError) {
        Set blnErrorAlarmExists = $$$YES
        Set strTestStatus = $$$InstrumentTestQcStatusError
    }
    ElseIf (alarm.AlarmAction = $$$AlarmActionWarning) && ('blnErrorAlarmExists) {
        Set strTestStatus = $$$InstrumentTestQcStatusWarning
    }
    Do ##class(qc.cQcResultAlarms).Add(...)   // persist the alarm on the result
}

// 3. Auto-validate (only if the global PERFORM_QC_VALIDATION setting is on)
If blnPerformVal {
    If blnErrorAlarmExists {
        Set ..blnAccepted = $$$NO            // ← "Error" blocks auto-accept...
    } Else {
        Set ..blnAccepted = $$$YES           // ← ...but nothing auto-REJECTS
        Set ..ReviewDateTime = $ZDateTime($Horolog,3,1)
        Set ..ReviewerID = "~system~"
    }
}
```

**Key insight that drives Topic 1:** Today the maximum consequence of any alarm — even severity `Error` — is *"do not auto-accept; leave for manual review."* There is **no automatic rejection.** A human must open the result and click Reject.

### QC result state model

`Data.QC.tQcResult` has **no explicit "rejected" status field**. State is expressed through booleans:

| Field | Meaning |
|-------|---------|
| `blnAccepted` | Result accepted (auto or manual) → eligible for host export |
| `blnExcluded` | Result excluded from statistics / LJ chart (this is what "reject" sets) |
| `blnHold` | On hold |
| `blnBlocked` | Blocked |
| `blnAdminReviewed` | Reviewed by admin |

**"Rejecting" a QC result = `qc.cQcRejectHandler.DoAction()`** which sets `blnAccepted=NO`, `blnExcluded=YES`, stamps reviewer/time, recomputes statistics and rolls the instrument-test status back to the previous result's status (`ReturnToPreviousStatus`).

> Note: patient results (`Data.results.tResults`) *do* have explicit status macros — `ResultStatusPending 5`, `ResultStatusHold 10`, `ResultStatusRejected 20`, `ResultStatusValidated 30`. QC uses the boolean model instead.

### The multi-rule (Westgard) engine

`qc.cQcRule.ApplyRules()` runs configured Westgard multi-rules (`1x2s`, `1xKs`, `2of3x2s`, `3x1s`, `4x1s`, `2x2s`, `RxKs`, `Mxbar`, `Mmono`, `LotExp`) against the last 100 results. On violation it raises:
- `MRW` (Multi-Rule Warning) or `MRE` (Multi-Rule Error)

and applies the same "Error blocks auto-accept" rule. This is the natural home for new *rule-derived* alarms.

---

## Topic 1 — Automatic rejection rules ("Error and Reject" level)

### Working hypothesis: introduce a new alarm level above `Error`

This is **the correct instinct and the cleanest design.** The severity scale is already an ordered integer that gates auto-accept. Adding one rung at the top — `Reject = 4` — lets the entire existing pipeline keep working, with one new branch that performs auto-rejection.

```objectscript
#Define AlarmActionUndefined    -1
#Define AlarmActionNone          0
#Define AlarmActionInformation   1
#Define AlarmActionWarning       2
#Define AlarmActionError         3
#Define AlarmActionReject        4   // NEW
```

Semantics:
- `Error (3)` → keep today's behaviour: **do not auto-accept**, hold for manual review.
- `Reject (4)` → **automatically reject** (the system performs the `cQcRejectHandler` action with `ReviewerID = "~system~"`), no human needed.

### Why a new *level* beats a new *flag*

An alternative would be a separate boolean ("auto-reject") on the alarm mapping. The level approach is better because:
1. Severity is already resolved, persisted and compared everywhere as an ordered scalar (`HighestAlarmAction`, `blnErrorAlarmExists`, `strQcStatus`). One extra value reuses all of it.
2. UI already renders a severity dropdown per alarm mapping — adding "Reject" is one list entry, not a new column.
3. The host-export and reporting layers compare severity numerically; a higher number naturally sorts/filters correctly.

### Changes required

**A. Macro + severity constant** — `ACB/Routines/MainInclude.xml`
Add `#Define AlarmActionReject 4`.

**B. Core auto-validation** — `Data/QC/tQcResult.xml`, `AutomaticValidation()`
Extend the severity scan to detect a reject-level alarm, and add a rejection branch:

```objectscript
Set blnRejectAlarmExists = $$$NO
For each alarm {
    If (alarm.AlarmAction = $$$AlarmActionReject) {
        Set blnRejectAlarmExists = $$$YES
        Set strTestStatus = $$$InstrumentTestQcStatusError   // or a new "Rejected" status
    }
    ElseIf (alarm.AlarmAction = $$$AlarmActionError) { ... }   // unchanged
    ...
}

If blnPerformVal {
    If blnRejectAlarmExists {
        // Auto-reject: mirror cQcRejectHandler.DoAction
        Set ..blnAccepted = $$$NO
        Set ..blnExcluded = $$$YES
        Set ..ReviewDateTime = $ZDateTime($Horolog,3,1)
        Set ..ReviewerID = "~system~"
        // statistics + ReturnToPreviousStatus handled after save
    }
    ElseIf blnErrorAlarmExists {
        Set ..blnAccepted = $$$NO            // unchanged
    }
    Else {
        Set ..blnAccepted = $$$YES           // unchanged
    }
}
```

Best practice: **don't duplicate** the rejection side-effects. Refactor `cQcRejectHandler.DoAction` so its core (set excluded, update statistics, `UpdateTestStatusHistory`, `ReturnToPreviousStatus`) is callable as a reusable system-reject method, then call it from `AutomaticValidation`.

**B2. Configurable rejection comment** — attach an admin-defined comment to every auto-rejected result.

*Where the comment is configured (data model):* `Data.alarm.tAlarmsMapping` already carries comment-related config — it has a `SendAlarmAsComment` field — so it is the natural home. Add a new property, e.g. `RejectComment` (`%String`, `MAXLEN 2000`), to `tAlarmsMapping` (and the system-alarm equivalent if system alarms can be set to Reject). It is only meaningful when `AlarmAction = $$$AlarmActionReject (4)`.

*Where the comment is attached (runtime):* QC results already have a dedicated comments table — `Data.QC.tQcComments` (`Type = "RESULT"`, `TextComment`, `UserName`, `IssuerType`, `PrintSendHost`, `DateComment`, `rQcResult`) — written via `qc.cQcComments.Add(...)`. In the auto-reject branch (B above), after the result is rejected:

```objectscript
// Resolve the configured comment for this alarm mapping
Set strRejectComment = ##class(co.val.cAlarmsMapping).GetRejectComment(
                           alarm.AlarmID, instrumentType, $$$AlarmResultTypeQc)
If (strRejectComment '= "") {
    Do ##class(qc.cQcComments).Add(
           "RESULT",              // pstrCommentType
           "SY",                  // pstrIssuerType — NEW system-issuer value (see below)
           strRejectComment,      // pstrText
           0,                     // pintPrtSendHost (0 = don't send to LIS; make configurable)
           ..%Id(),               // pstrIdResult
           , , , ,                // event / LJ review ids — n/a
           ..%Id(),               // resultId
           "~system~")            // pstrUser
}
```

Supporting changes:
- **New `IssuerType` value `"SY"` (System).** Today `tQcComments.IssuerType` allows `OP` (operator) and `ME` (manual entry). Add `SY` so auto-reject comments are distinguishable from human comments in the UI and audit trail. Seed the issuer-type lookup in the migration.
- **New resolver** `co.val.cAlarmsMapping.GetRejectComment(AlarmID, InstrumentType, ResultType)` — mirrors `GetSystemAlarmAction`, returning the configured `RejectComment` for the effective mapping (site-specific → default).
- **Optional "send to LIS" toggle** — `PrintSendHost` controls whether the comment is forwarded to the host. Since rejected results aren't exported anyway, default to `0`; expose a tick-box next to the comment field if needed.

**C. Multi-rule engine** — `qc/cQcRule.xml`, `ApplyRules()`
Currently: `objAlarm.AlarmID = $Case(strStatus, "Warning":"MRW", "Error":"MRE")` and on `Error` it clears accept. Add handling so a rule mapped at `Reject` severity (or a new `MRR` "Multi-Rule Reject" alarm) triggers auto-rejection. This is where "automatic rejection *rules*" literally live — a lab admin marks a Westgard rule (e.g. `1x3s`) as auto-reject.

**D. Instrument-test status (optional but recommended)** — `qc/cQcEngine.xml` + `MainInclude.xml`
Today `strQcStatus` ∈ {`OK`, `Warning`, `Error`}. Consider adding `Rejected` so dashboards/reports can distinguish an auto-rejected test from a manually-flagged error. If added, update `cQcEngine.UpdateTestStatus`, `UpdateTestStatusHistory`, and every consumer of `$$$InstrumentTestQcStatusError`.

**E. Host export gating** — `qc/cQcAcceptHandler.xml` (`ExportQCResult`)
Already gated on `blnAccepted`. Since auto-reject sets `blnAccepted=NO`, rejected results are naturally **not** sent to host. Verify no other export path sends excluded results.

**F. Seed data / migration** — new `CTools/Classes/Update/vXXX.xml`
Follow the existing pattern (see `Update/v206.xml`): the alarm-types list and `tAlarmsMapping` inserts. For each alarm code that should support auto-reject, either raise its `DefaultAction` to `4` or, more safely, leave defaults alone and let admins opt-in per instrument type via mapping.

**G. UI / SOAP services** — `solutionsuite-frontend` + `src/UI/Source/cobasIT1000.GatewayServices/ws/val/wAlarmsMapping.cs`, `wAlarms.cs`
- Add "Reject" (value 4) to the severity dropdown wherever Error/Warning/Information appear (alarm config, system-alarm assignment screens — cf. NPOCO-24711 / NPOCO-24713).
- **Rejection comment field:** when the admin selects severity "Reject", reveal an extra free-text field bound to the new `RejectComment` mapping property (hidden/disabled for other severities). Validate length; allow empty (no comment attached if blank).
- The SOAP contracts pass `AlarmAction` as a plain integer; the mapping save/load services (`wAlarmsMapping`) gain one new string field `RejectComment` — a small contract addition, backward-compatible (older clients simply omit it).
- Result-grid: render auto-rejected results distinctly, show `~system~` as reviewer, and surface the attached `SY` comment (the comments tooltip already exists via `HasResultComments`).

**H. Tests** — `src/DB/Source/Logic/UnitTest/.../qc/`
Existing `cQcRejectHandler`, `cQcAcceptHandler` test folders give the pattern. Add cases: reject-level alarm → result excluded, not exported, statistics excluded, test status rolled back, audit reviewer = `~system~`.

### Risk / compliance notes
- **IVD / 21 CFR Part 11:** auto-rejection is a system action on a quality record. The audit trail must record *who/what/when/why* — set `ReviewerID = "~system~"` and persist the triggering alarm code + rule. Confirm with regulatory whether auto-reject needs a configurable "require confirmation" safety toggle.
- **Backwards compatibility:** because `Reject` is strictly above `Error`, existing mappings (all ≤3) are unaffected. The feature is dormant until an admin assigns severity 4.
- **Global switch:** behaviour is already gated by `PERFORM_QC_VALIDATION`. Consider a second setting `PERFORM_QC_AUTO_REJECTION` so sites can enable auto-accept without auto-reject.

### Effort estimate
~3.5–4.5 weeks (1 backend + 1 frontend dev): macro + validation branch + reject refactor (1w), rule-engine integration (0.5w), status model + consumers (0.5–1w), configurable reject comment — `RejectComment` field + `SY` issuer + resolver + `cQcComments.Add` wiring (0.5w), UI severity option + conditional comment field (0.5–1w), migration + tests (1w).

---

## Topic 2 — "Switched Levels" alarm

### The problem, precisely
A control material has N levels (e.g. AcquaCheck Inform 2: Level 1 + Level 2). The operator runs **Level 2 material but the device/operator labels it Level 1** (or vice-versa). Because the measured value lands inside the *other* level's range, today's range check (`AutomaticValidation`) sees "in range" → **auto-accepts a mislabelled control.** This is a real patient-safety gap: QC passes for the wrong reason.

### Does anything like this exist today? — No
There is no level-cross-check. `AutomaticValidation` validates a result **only against the range for the level it was reported under** (`ProcessControl.OriginalRange`, found via `cQcApi.FindMaterialRange(..., pintLevel)`). It never asks "would this value fit a *different* level better?"

### Data model — everything needed already exists
- `Data.QC.tQcMaterial.intNoOfLevels` and `.strLevelName` — material declares how many levels it has.
- `Data.QC.tQcRange` — one row **per level** (`intLevel`) per material-lot + system-test, holding `fltTargetMean`, `fltTargetSD`, `fltMin`, `fltMax`, `fltkSD`. Indexed by `intLevelIdx`.
- `Data.QC.tQcOrder.QcLevel` and the result's `ProcessControl` carry the reported level.
- `cQcApi.FindMaterialRange(controlLot, testLot, systemTest, level)` already resolves a range **for any given level** — so we can cheaply fetch the *sibling* level's range.

### Proposed solution

**Detection rule:** When validating a QC result reported at level `L`, also evaluate it against the ranges of the *other* levels of the same control lot + system test. If the value is **out of range for the reported level `L`** but **in range for some other level `L'`**, raise a new `QCSL` ("QC Switched Level") alarm.

This is deliberately conservative — it only fires on the suspicious combination (fails own level, fits a sibling), avoiding false positives when a value happens to fall in an overlap.

**A. New alarm code** — `QCSL`
Seed in `tAlarmTypes` (migration `vXXX.xml`), description "QC result matches a different control level". Default severity: recommend `Error (3)` so it blocks auto-accept; with Topic 1 shipped, a site could escalate it to `Reject (4)`.

**B. Detection logic** — `Data/QC/tQcResult.xml` `AutomaticValidation()`, *inside the numeric out-of-range else-branch* (right where `QCOR` is raised today):

```objectscript
// value failed its own level → before/alongside QCOR, test sibling levels
Set intLevels = ..ProcessControl.ControlLot.Material.intNoOfLevels
If (intLevels > 1) {
    For l = 1:1:intLevels {
        Continue:(l = reportedLevel)
        Set objSiblingRange = ##class(qc.cQcApi).FindMaterialRange(
                                  controlLot, testLot, systemTest, l, .err)
        Continue:(objSiblingRange = "")
        Set sMin = objSiblingRange.fltMin, sMax = objSiblingRange.fltMax
        If ((..fltMeasurementValue >= sMin) && (..fltMeasurementValue <= sMax)) {
            // build QCSL alarm; AlarmAction = GetSystemAlarmAction("QCSL", instType, $$$AlarmResultTypeQc)
            // (optionally record matched level l in alarm code/description)
            Do pobjAlarmList.Insert(objSwitchedAlarm)
            Quit   // first matching sibling is enough
        }
    }
}
```

The standard severity-scan below then picks up `QCSL`: if mapped to `Error` it blocks auto-accept; if `Reject` (post Topic 1) it auto-rejects. **No new accept/reject plumbing needed — it rides the Topic 1/0 machinery.**

**C. Helper (recommended):** add `Data.QC.tQcResult.FindMatchingLevel()` returning the sibling level the value fits (or 0). Keeps `AutomaticValidation` readable and gives the UI the matched level to display ("looks like Level 2").

**D. Alphanumeric controls:** the same idea applies using `AlphanumTargetMean` comparison, but value-overlap across qualitative levels is rare — scope to numeric levels first.

**E. Edge cases / config**
- Materials with `intNoOfLevels = 1` → skip entirely (no siblings).
- Overlapping ranges (sibling ranges that legitimately overlap the reported one) → only raise when the reported level **fails** and a sibling **passes**, which already excludes the benign overlap case.
- Consider a per-material toggle `blnSwitchedLevelDetection` (new boolean on `tQcMaterial`) so labs can disable it for controls where levels are intentionally close.

**F. UI:** show `QCSL` in result grid/flags with the matched level; add to alarm-config screens like any other QC alarm. Documentation/training note for operators.

**G. Tests:** two-level material; value out-of-range for L1 + in-range for L2 → `QCSL` raised, not auto-accepted. Plus negatives (single-level, in-range-own-level, out-of-range-for-all-levels → plain `QCOR`).

### Effort estimate
~2–3 weeks: detection logic + helper (1w), alarm seed + config + UI (0.5–1w), tests + edge cases (0.5–1w). Lower if Topic 1 lands first (reuse of reject path).

---

## Cross-cutting summary

| | Topic 1 — Auto-reject level | Topic 2 — Switched levels |
|---|---|---|
| **Exists today?** | No auto-reject (Error only blocks accept) | No |
| **Scope (confirmed)** | QC | QC |
| **Core hook** | `tQcResult.AutomaticValidation` severity scan | `tQcResult.AutomaticValidation` out-of-range branch |
| **New alarm code** | (reuse existing, raise to sev 4) | `QCSL` |
| **Data model change** | `+AlarmActionReject 4`; `+RejectComment` on `tAlarmsMapping`; `+SY` issuer on `tQcComments`; optional `Rejected` test status | none (reuse `tQcRange`/`intLevel`) |
| **Migration** | `tAlarmsMapping` severity + comment; `SY` issuer-type seed | seed `QCSL` |
| **UI** | "Reject" in severity dropdown + conditional comment field | show `QCSL` + matched level |
| **Effort** | 3.5–4.5 wk | 2–3 wk |

### Recommended sequencing
1. **Topic 1 first — hard prerequisite.** It introduces the `Reject (4)` severity that Topic 2 depends on.
2. **Topic 2 second.** Small, self-contained; `QCSL` becomes a one-line severity choice once Topic 1 exists.

### Key files to touch (quick reference)
```
ACB/Routines/MainInclude.xml                          # severity + status macros, settings
ACB/Classes/Data/QC/tQcResult.xml                     # AutomaticValidation (Topics 1,2)
ACB/Classes/qc/cQcRule.xml                            # multi-rule auto-reject (Topic 1)
ACB/Classes/qc/cQcRejectHandler.xml                   # refactor reusable system-reject (Topic 1)
ACB/Classes/qc/cQcApi.xml                             # FindMaterialRange (Topic 2)
ACB/Classes/qc/cQcEngine.xml                          # test status model (Topic 1)
ACB/Classes/qc/cQcComments.xml                        # Add() — attach reject comment (Topic 1)
ACB/Classes/Data/QC/tQcComments.xml                   # +SY issuer type (Topic 1)
ACB/Classes/co/val/cAlarmsMapping.xml                 # +GetRejectComment resolver (Topic 1)
ACB/Classes/Data/alarm/tAlarmTypes.xml                # alarm definitions
ACB/Classes/Data/alarm/tAlarmsMapping.xml             # severity mapping + RejectComment
CTools/Classes/Update/vXXX.xml                        # NEW migration (both topics)
src/UI/.../ws/val/wAlarmsMapping.cs, wAlarms.cs       # SOAP services (severity option)
solutionsuite-frontend                                # alarm config UI, result grid
```

---

*Investigation by Amelia, 2026-06-24. Source: `solutionsuite-foundation` @ `dev`.*
