# Windows CLI existing-category and tag control, 15 November 2026

A real Claude Code call proposed two controls over existing category and tag labels in the ten-item fictional `tags` scenario. An AI operator reviewed the proposal, applied it and reviewed Undo. This was a direct application-route test, not a browser demonstration or human evaluation.

## Request and result

Request: "Show me more music videos, and remove anything about food."

The provider received the existing vocabulary of 28 category/tag entries and their counts, the request and the application schema. This route does not send the item captions for interpretation. It does not create a new category.

- Preview left the baseline feed unchanged.
- Apply removed IDs 61001, 61002, 61003 and 61009, leaving six of ten items.
- Music item 61007 moved from rank 4 to rank 2; item 61008 moved from rank 5 to rank 4.
- Undo restored all ten items in their original order and with their original scores.

**Scope limitation:** item 61004 describes a mechanic eating a sandwich, but its category is Repair and its tags are bicycle and tools. It remained. The result proves the reviewed existing-label controls, not removal of every food-related item across captions. The request explicitly names music and food; this run does not establish the separate nonliteral hunger-to-food interpretation.

The fixture is invented and uses a deterministic diagnostic scorer, not a trained recommender. The operator was an assistant, not a human. The result is software and model-integration evidence, not an accuracy estimate or measured user benefit.

## Evidence and limits

The isolated execution was bound to source commit `e705e0ca636bdf40e452716c02742791483eae09`. It used the published personal adapter with a separately reviewed task-local launcher and transport. This is not a portable public launcher or qualification of the general quickstart route.

The retained result has SHA-256 `acb22d98dec5d1e9e57293edc44e1d0fe76273d92d083c3d45a3a712bf28174f` (28,629 UTF-8 bytes). Independent reconstruction matched that exact hash. The check verified one logical call, the exact removed IDs, unchanged Preview, equal applied and preview feeds, and complete baseline/restored equality, including scores and order.

The CLI reported `claude-fable-5-2`, `success`, one turn, `end_turn`, `is_error=false`, exit 0 and 4,873 output tokens. Adapter elapsed time was 55.581 seconds. Its estimated cost was USD 0.2783348, not verified billing. Requested settings were 16,384 output tokens, 300 seconds and a USD 5 estimated threshold. Actual token-limit enforcement and effective effort were not independently established.

The strict stream projection passed and retained only `end_turn` as an intermediate stop reason. Complete intermediate coverage was not established; unknown rate-information fields were flagged. The owned lifecycle recorded stdin complete, stdout EOF, root exit 0, cleanup complete, I/O and close returned, and last observed job-member count zero. These are owned-process observations, not a global process inventory.

The raw receipt, private paths and hook context are not included in this publication. Hidden managed context and underlying provider-request count remain unverified.

The earlier 4,096-token attempt is separate evidence: it reported `max_tokens` then `end_turn` and two turns. The unchanged one-turn acceptance gate rejected that result before Apply. It must not be counted as a successful lifecycle.

No browser, HTTP/ASGI, new-category discovery, nonliteral hunger mapping, held-out study or portable quickstart acceptance is established here. Existing research evidence remains unchanged.
