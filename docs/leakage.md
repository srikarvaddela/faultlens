# Capture-derived function leakage

The Research view keeps **recorded labels** and **capture-derived labels** separate. Choose Label source to filter by either. Derived labels match archived ground-truth function names against the archived error message plus stack trace, using case-insensitive word boundaries. They describe name exposure in a capture, not verified exposure in the original model prompt.

The archive does not retain the exact evidence text/hash for each historical inference. Captures may have changed between experiment passes. This feature therefore **does not reproduce or validate the original leakage-controlled headline result**, even where case identities and archived ground truth match. A no-match label is not proof of leakage-free evidence.

## Eligibility and unknown cases

Only real-bug rows with usable function ground truth and a matched, nonempty, eligible archived capture can receive a derived boolean. Mutants, missing captures/functions, placeholder evidence, unreproduced captures, ambiguous identities, and conflicting ground-truth metadata remain unknown. Recognized missing test runners (such as `tox: command not found`) also remain unknown rather than entering the no-match stratum.

The missing-runner guard came from a six-case inspection of archived traces. It deliberately handles explicit missing runner messages; it is not a general environment-failure classifier. A nonzero test exit alone does not prove a real bug was reproduced.

## Inspection and metrics

Click a Capture-derived match cell to see matching excerpts, the error message, stack trace, eligibility reason, source filename, and capture/evidence hashes. Capture text is rendered as plain text and stays in the local ignored database. Credential patterns are redacted before persistence. Archived original labels and outcome booleans are never changed.

Each file retains descriptive match/no-match/unknown strata with paired denominators. UI filters recompute the current selection's recorded single/chain outcome rates. Repeated passes remain separate; no pooled significance or corrected accuracy is reported. Full historical reproduction still requires frozen per-run inputs and independently validated ground-truth extraction.

![Synthetic capture-derived review](screenshots/capture-leakage.png)
