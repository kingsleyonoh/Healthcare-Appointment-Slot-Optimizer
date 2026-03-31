# Architect's Journal

> Raw engineering narratives captured during development. This file is consumed by the `architect-theatre` skill to generate website content. It is git-ignored — write freely.
>
> **Only write entries when something genuinely interesting happened:** a real failure, a non-obvious behavior, a trade-off decision, a dead end that taught something. Do not log routine implementations.

---

## Entry Format

```
## [YYYY-MM-DD] [Task/Incident Name]

### Intent
What we were trying to do. One or two sentences.

### Failure / Surprise
What went wrong or was unexpected. Be specific: name the function, the error message, the constant, the behavior. Vague entries are useless to content generation.

### The Fix
How it was resolved. Include the actual approach, not just "fixed it." If there was a code change worth noting, name the file and the function.

### Engineering Trade-offs
What was traded for what. Speed vs. correctness? Simplicity vs. flexibility? Short-term hack vs. long-term solution? Name the alternatives that were rejected and why.

### Impact
Business or technical significance. What would have happened without this fix? What does this enable? Quantify where possible.
```

---

## Example Entry (delete after first real entry)

## [2026-01-15] Batch processor silently dropping records above 10K

### Intent
Implement the nightly sync job to pull supplier catalog updates and merge into the local product database.

### Failure / Surprise
The sync worked perfectly in testing with 500 records. In production with 12,847 records, `process_batch()` in `sync/processor.py` silently dropped everything after record 10,000. No error, no log line. The PostgreSQL `COPY` command has a default buffer that flushes at 10K rows, and our connection wrapper was not handling the continuation.

### The Fix
Split the batch into chunks of 5,000 using `itertools.islice()` and process each chunk in a separate transaction. Added an explicit count assertion: if `inserted_count != expected_count`, raise `BatchIntegrityError` with both numbers.

### Engineering Trade-offs
Could have increased the buffer size to 50K, but that trades memory safety for simplicity. The chunked approach uses ~60% more wall-clock time (7 minutes vs. 4.5 minutes) but guarantees every record is accounted for. Chose correctness over speed because this is a nightly job with a 2-hour window.

### Impact
Without this fix, 22% of catalog updates were silently lost. Pricing decisions downstream were based on stale data. The count assertion has since caught two other edge cases in the first week.
