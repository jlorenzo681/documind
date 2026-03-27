# Bugfix Requirements Document

## Introduction

The chatbot always displays "No answer found." in response to every user question, regardless of the document content or the question asked. This has never worked correctly since the feature was introduced. The root cause is a combination of two issues in the RAG pipeline response handling:

1. The `FullAnalysisResult` API response serializes `qa_results` as `null` (JSON null) when no QA results are present, rather than an empty list.
2. The chatbot frontend uses `data.get("qa_results", [])` which returns `None` (not the fallback `[]`) when the key exists but its value is `null` — because Python's `.get()` only uses the default when the key is **absent**, not when it is `None`. A `None` value is falsy, so the branch always falls through to "No answer found."

Additionally, the `FullAnalysisResult` schema marks `qa_results` as `list[QAResult] | None`, meaning a completed QA task can legitimately serialize as `null` even when results exist but were not populated — masking failures silently.

## Bug Analysis

### Current Behavior (Defect)

1.1 WHEN a user submits any question through the chatbot THEN the system always displays "No answer found." regardless of document content or question validity

1.2 WHEN the analysis task completes with QA results THEN the system returns `"qa_results": null` in the JSON response instead of a populated list, causing the frontend to treat a successful analysis as having no results

1.3 WHEN the chatbot calls `data.get("qa_results", [])` on a response where `"qa_results"` is `null` THEN the system returns `None` instead of the fallback empty list `[]`, because the key is present with a null value

### Expected Behavior (Correct)

2.1 WHEN a user submits a question through the chatbot THEN the system SHALL display the answer retrieved from the document's vector store

2.2 WHEN the analysis task completes with QA results THEN the system SHALL return a populated `qa_results` list in the JSON response

2.3 WHEN the chatbot receives a response where `"qa_results"` is `null` or absent THEN the system SHALL treat it as an empty list and display an appropriate fallback message only when no results genuinely exist

### Unchanged Behavior (Regression Prevention)

3.1 WHEN a user submits a question and the document has no relevant content THEN the system SHALL CONTINUE TO display an appropriate "no answer" message

3.2 WHEN the analysis task fails or is cancelled THEN the system SHALL CONTINUE TO display the appropriate error status message

3.3 WHEN a completed analysis has no QA task (e.g., summarize-only) THEN the system SHALL CONTINUE TO return `qa_results: null` in the response without affecting other result fields

3.4 WHEN the vector store is unreachable during retrieval THEN the system SHALL CONTINUE TO fall back to keyword-based retrieval and return an answer
