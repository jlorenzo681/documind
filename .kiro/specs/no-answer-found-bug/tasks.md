# Implementation Plan

- [x] 1. Write bug condition exploration test
  - **Property 1: Bug Condition** - Null QA Results Cause "No Answer Found"
  - **CRITICAL**: This test MUST FAIL on unfixed code - failure confirms the bug exists
  - **DO NOT attempt to fix the test or the code when it fails**
  - **NOTE**: This test encodes the expected behavior - it will validate the fix when it passes after implementation
  - **GOAL**: Surface counterexamples that demonstrate the bug exists
  - **Scoped PBT Approach**: Scope the property to the concrete failing case — any dict where `"qa_results"` key is present with value `None`
  - Test that `result.get("qa_results", [])` with `result = {"qa_results": None}` returns `[]`, not `None` (from Bug Condition in design)
  - Test that `data.get("qa_results", [])` with `data = {"qa_results": None}` returns `[]`, not `None`
  - Test that the chatbot handler displays an answer (not "No answer found.") when the API returns `{"qa_results": None}` for a completed QA task
  - Use `hypothesis` to generate dicts where `"qa_results"` key is present with `None` value and assert `or []` normalization always yields a list
  - Run test on UNFIXED code (`results.py` and `chatbot.py` unchanged)
  - **EXPECTED OUTCOME**: Test FAILS (this is correct - it proves the bug exists)
  - Document counterexamples found: e.g., `{"qa_results": None}.get("qa_results", [])` returns `None`; chatbot `if qa_results:` is `False`, falls through to "No answer found."
  - Mark task complete when test is written, run, and failure is documented
  - _Requirements: 1.1, 1.2, 1.3_

- [x] 2. Write preservation property tests (BEFORE implementing fix)
  - **Property 2: Preservation** - Non-Null and Empty QA Results Behavior Unchanged
  - **IMPORTANT**: Follow observation-first methodology
  - Observe: `{"qa_results": []}.get("qa_results", [])` returns `[]` on unfixed code → chatbot shows "No answer found." (correct)
  - Observe: `{}.get("qa_results", [])` returns `[]` on unfixed code → chatbot shows "No answer found." (correct)
  - Observe: `{"qa_results": [{"answer": "...", "confidence": 0.9, "sources": []}]}.get("qa_results", [])` returns the list → chatbot shows the answer (correct)
  - Write property-based test: for all `qa_results` values that are NOT `None` (empty list, absent key, populated list), the `or []` normalization produces the same result as the original `.get()` call (from Preservation Requirements in design)
  - Use `hypothesis` to generate varied `qa_results` values (empty lists, lists of dicts, absent key) and verify behavior is identical before and after normalization
  - Verify tests PASS on UNFIXED code (confirms baseline behavior to preserve)
  - _Requirements: 3.1, 3.2, 3.3_

- [x] 3. Fix the null qa_results bug

  - [x] 3.1 Fix null propagation in `results.py`
    - In `src/documind/api/routes/results.py`, change:
      `qa_data = result.get("qa_results", []) if result else []`
      to:
      `qa_data = (result.get("qa_results") or []) if result else []`
    - This ensures a `None` value (key present, value null) is normalized to `[]` before the `if qa_data:` check
    - _Bug_Condition: `isBugCondition(api_response)` where `api_response["qa_results"] is None`_
    - _Expected_Behavior: `qa_data` is always a list; `qa_results` field in `FullAnalysisResult` is populated when results exist_
    - _Preservation: `result = None` path still returns `[]`; non-None lists pass through unchanged_
    - _Requirements: 2.1, 2.2, 2.3_

  - [x] 3.2 Fix null handling in `chatbot.py`
    - In `src/documind/frontend/chatbot.py`, change:
      `qa_results = data.get("qa_results", [])`
      to:
      `qa_results = data.get("qa_results") or []`
    - This ensures a `None` value in the JSON response is normalized to `[]` so the `if qa_results:` check works correctly
    - _Bug_Condition: `isBugCondition(api_response)` where `api_response["qa_results"] is None`_
    - _Expected_Behavior: chatbot displays the answer from `qa_results[0]` when results are present_
    - _Preservation: empty list `[]` still causes "No answer found."; absent key still causes "No answer found."_
    - _Requirements: 2.1, 2.3, 3.1_

  - [x] 3.3 Verify bug condition exploration test now passes
    - **Property 1: Expected Behavior** - Null QA Results Cause "No Answer Found"
    - **IMPORTANT**: Re-run the SAME test from task 1 - do NOT write a new test
    - The test from task 1 encodes the expected behavior (chatbot displays answer when `qa_results` is null in API response)
    - Run bug condition exploration test from step 1
    - **EXPECTED OUTCOME**: Test PASSES (confirms bug is fixed in both `results.py` and `chatbot.py`)
    - _Requirements: 2.1, 2.2, 2.3_

  - [x] 3.4 Verify preservation tests still pass
    - **Property 2: Preservation** - Non-Null and Empty QA Results Behavior Unchanged
    - **IMPORTANT**: Re-run the SAME tests from task 2 - do NOT write new tests
    - Run preservation property tests from step 2
    - **EXPECTED OUTCOME**: Tests PASS (confirms no regressions — empty list still shows "No answer found.", absent key still shows "No answer found.", populated list still shows the answer)
    - Confirm all tests still pass after fix (no regressions)

- [x] 4. Checkpoint - Ensure all tests pass
  - Run the full test suite to confirm no regressions
  - Ensure all tests pass; ask the user if questions arise
