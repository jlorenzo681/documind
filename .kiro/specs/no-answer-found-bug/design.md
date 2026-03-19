# No Answer Found Bug - Bugfix Design

## Overview

The chatbot always displays "No answer found." for every user question. Two bugs combine to cause this:

1. `results.py` initializes `qa_results = None` and only populates it when `qa_data` is truthy — but `qa_data` comes from `result.get("qa_results", [])`, which returns `None` (not `[]`) when the key exists with a `null` value. So `qa_results` stays `None` and the `FullAnalysisResult` serializes `"qa_results": null`.
2. `chatbot.py` calls `data.get("qa_results", [])` on the JSON response. Because the key `"qa_results"` is present (with value `null`), Python's `.get()` returns `None` — not the fallback `[]`. The `if qa_results:` check then fails and the chatbot falls through to "No answer found."

The fix is minimal: normalize `null` to `[]` in both places.

## Glossary

- **Bug_Condition (C)**: The condition that triggers the bug — a completed QA task whose API response contains `"qa_results": null`, causing the chatbot to display "No answer found." despite valid results existing
- **Property (P)**: The desired behavior — when a QA task completes with results, the chatbot SHALL display the answer
- **Preservation**: Existing behaviors that must remain unchanged — error states, summarize-only tasks, and genuine empty-result scenarios
- **`get_results`**: The function in `src/documind/api/routes/results.py` that builds and returns the `FullAnalysisResult` response
- **`qa_data`**: The intermediate variable in `get_results` that holds the raw QA list from the task store; can be `None` when the key exists with a null value
- **`data.get("qa_results", [])`**: The chatbot expression in `src/documind/frontend/chatbot.py` that retrieves QA results from the API JSON; returns `None` (not `[]`) when the key is present but null

## Bug Details

### Bug Condition

The bug manifests when a QA analysis task completes and the task store contains a `qa_results` key with a non-null list, but the API serializes it as `null` and the chatbot mishandles that null. The `get_results` function uses a falsy check (`if qa_data`) that fails when `qa_data` is `None`, and the chatbot's `.get()` fallback is bypassed because the key is present.

**Formal Specification:**
```
FUNCTION isBugCondition(api_response)
  INPUT: api_response — dict parsed from GET /results/{task_id} JSON
  OUTPUT: boolean

  qa_value = api_response["qa_results"]   // key is present
  RETURN qa_value IS NULL                 // value is null (not absent, not a list)
END FUNCTION
```

### Examples

- User asks "What is the contract duration?" → API returns `{"qa_results": null}` → chatbot gets `None` from `.get()` → displays "No answer found." (BUG: should display the answer)
- User asks any question on any document → same result regardless of content (BUG: always fails)
- Summarize-only task completes → API returns `{"qa_results": null}` → chatbot is not invoked for this path (NOT a bug — null is correct here per requirement 3.3)
- QA task completes but document has no relevant content → `qa_results` is `[]` (empty list, not null) → chatbot correctly shows "No answer found." (CORRECT behavior, must be preserved)

## Expected Behavior

### Preservation Requirements

**Unchanged Behaviors:**
- When a document has no relevant content for a question, the chatbot SHALL continue to display an appropriate "no answer" message (requirement 3.1)
- When an analysis task fails or is cancelled, the chatbot SHALL continue to display the appropriate error status message (requirement 3.2)
- When a completed analysis has no QA task (summarize-only), the API SHALL continue to return `qa_results: null` without affecting other result fields (requirement 3.3)
- When the vector store is unreachable, the system SHALL continue to fall back to keyword-based retrieval (requirement 3.4)

**Scope:**
All inputs that do NOT involve a completed QA task with actual results are unaffected by this fix. This includes:
- Summarize-only or compliance-only analysis tasks
- Failed or cancelled tasks
- Tasks where QA ran but found no relevant content (genuinely empty results)

## Hypothesized Root Cause

Two independent bugs compound each other:

1. **`results.py` — null propagation from task store**: `qa_data = result.get("qa_results", [])` returns `None` when the task store has `{"qa_results": null}` (key present, value null). The default `[]` is only used when the key is absent. The subsequent `if qa_data:` check treats `None` as falsy, so `qa_results` stays `None` and serializes as `null` in the response.

2. **`chatbot.py` — same `.get()` misuse**: `data.get("qa_results", [])` on the API JSON has the same flaw. When the response contains `"qa_results": null`, `.get()` returns `None`. The `if qa_results:` check fails and the chatbot always falls through to "No answer found."

Either bug alone would cause the symptom. Together they form a two-layer failure: the API produces null, and the chatbot mishandles null even if it were produced by a different code path.

## Correctness Properties

Property 1: Bug Condition - Completed QA Results Are Displayed

_For any_ API response where `"qa_results"` is `null` but the underlying task completed a QA analysis with results, the fixed chatbot SHALL display the answer from the first QA result rather than "No answer found."

**Validates: Requirements 2.1, 2.2, 2.3**

Property 2: Preservation - Genuine Empty Results Still Show Fallback

_For any_ API response where `"qa_results"` is an empty list `[]` (QA ran but found nothing), the fixed chatbot SHALL still display "No answer found." — preserving the correct fallback behavior for genuinely unanswered questions.

**Validates: Requirements 3.1**

Property 3: Preservation - Non-QA Paths Are Unaffected

_For any_ API response where `"qa_results"` is `null` because no QA task was run (summarize-only), the fixed API SHALL continue to serialize `qa_results: null` and the chatbot SHALL not be invoked for that path, preserving all non-QA behavior.

**Validates: Requirements 3.2, 3.3**

## Fix Implementation

### Changes Required

**File 1**: `src/documind/api/routes/results.py`

**Function**: `get_results`

**Specific Changes**:
1. **Normalize null to empty list**: Change `result.get("qa_results", []) if result else []` to use `or []` to handle the case where the key exists with a null value:
   ```python
   # Before
   qa_data = result.get("qa_results", []) if result else []
   
   # After
   qa_data = (result.get("qa_results") or []) if result else []
   ```

---

**File 2**: `src/documind/frontend/chatbot.py`

**Function**: chat input handler (inline, line ~115)

**Specific Changes**:
1. **Normalize null to empty list**: Change `data.get("qa_results", [])` to handle null values:
   ```python
   # Before
   qa_results = data.get("qa_results", [])
   
   # After
   qa_results = data.get("qa_results") or []
   ```

## Testing Strategy

### Validation Approach

Two-phase approach: first run exploratory tests on unfixed code to confirm the root cause, then verify the fix works and preserves existing behavior.

### Exploratory Bug Condition Checking

**Goal**: Surface counterexamples that demonstrate the bug BEFORE implementing the fix. Confirm the root cause analysis.

**Test Plan**: Write unit tests that simulate the exact data flow — pass a dict with `{"qa_results": null}` through both the `get_results` logic and the chatbot's result-handling logic, and assert that answers are displayed. Run on UNFIXED code to observe failures.

**Test Cases**:
1. **results.py null propagation**: Call `result.get("qa_results", [])` with `result = {"qa_results": None}` — assert result is `[]` (will fail on unfixed code, returns `None`)
2. **chatbot null handling**: Simulate `data = {"qa_results": None}` and call `data.get("qa_results", [])` — assert result is `[]` (will fail on unfixed code, returns `None`)
3. **End-to-end chatbot flow**: Mock the API to return `{"qa_results": null}` for a completed task — assert chatbot displays an answer, not "No answer found." (will fail on unfixed code)
4. **Absent key still works**: Call `.get("qa_results", [])` with `data = {}` — assert result is `[]` (should pass on both unfixed and fixed code)

**Expected Counterexamples**:
- `{"qa_results": None}.get("qa_results", [])` returns `None`, not `[]`
- Chatbot `if qa_results:` evaluates to `False` for `None`, falling through to "No answer found."

### Fix Checking

**Goal**: Verify that for all inputs where the bug condition holds, the fixed code produces the expected behavior.

**Pseudocode:**
```
FOR ALL api_response WHERE isBugCondition(api_response) DO
  qa_results := fixed_chatbot_handler(api_response)
  ASSERT qa_results IS NOT NULL
  ASSERT qa_results IS NOT EMPTY
  ASSERT displayed_message != "No answer found."
END FOR
```

### Preservation Checking

**Goal**: Verify that for all inputs where the bug condition does NOT hold, the fixed code produces the same result as the original code.

**Pseudocode:**
```
FOR ALL api_response WHERE NOT isBugCondition(api_response) DO
  ASSERT original_handler(api_response) == fixed_handler(api_response)
END FOR
```

**Testing Approach**: Property-based testing is well-suited here because:
- It generates many varied `qa_results` values (empty lists, lists with items, absent keys) automatically
- It catches edge cases like `qa_results: []` vs `qa_results: null` vs key absent
- It provides strong guarantees that the `or []` normalization doesn't change behavior for non-null inputs

**Test Cases**:
1. **Empty list preservation**: `{"qa_results": []}` → chatbot still shows "No answer found." (genuine empty result)
2. **Absent key preservation**: `{}` → chatbot still shows "No answer found."
3. **Populated list preservation**: `{"qa_results": [{"answer": "...", ...}]}` → chatbot shows the answer (this already worked; must continue to work)
4. **Error status preservation**: Failed/cancelled task status → chatbot shows error message, not answer

### Unit Tests

- Test `result.get("qa_results") or []` with `None`, `[]`, absent key, and populated list values
- Test `data.get("qa_results") or []` in chatbot with same input variants
- Test `get_results` endpoint with a task store entry where `qa_results` is `None`

### Property-Based Tests

- Generate random `qa_results` values (None, [], list of dicts) and verify `or []` normalization always produces a list
- Generate random completed task responses and verify the chatbot handler never returns "No answer found." when results are present
- Generate random non-QA responses and verify behavior is identical before and after fix

### Integration Tests

- Full flow: upload document → run QA analysis → poll until complete → fetch results → verify chatbot displays answer
- Summarize-only flow: run summary-only analysis → verify `qa_results: null` in response does not cause errors
- Failed task flow: simulate task failure → verify chatbot shows error message
