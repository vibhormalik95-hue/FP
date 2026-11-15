# Windows CLI indirect feed-control run, 15 November 2026

Two real Claude Code calls completed one existing-item indirect-control flow on an isolated fictional fixture. This is direct application-route evidence, not a browser demonstration or new-category discovery.

## Request and supplied scope

Request: "My early mornings should stay calm, so drop the noisy appliances."

The model received these eight captions from a 36-item deterministic fixture:

1. Wooden spoon set, oiled beech.
2. Countertop blender with a roaring motor.
3. Silicone baking mat, reusable.
4. Cast iron skillet, preseasoned.
5. Electric coffee grinder that shrieks at full speed.
6. Glass storage jars with lids.
7. Manual pasta roller, quiet hand crank.
8. Bamboo cutting board.

The first call interpreted the requested action. The second grounded that action against the supplied records. The model selected IDs 2 and 5, citing "Countertop blender with a roaring motor" and "Electric coffee grinder that shrieks at full speed". It did not create a category.

## Application result

An AI operator reviewed the proposal, supplied scope and cited evidence, then approved Apply. Preview left the full feed unchanged. Apply excluded exactly IDs 2 and 5, changing availability from 36 to 34. The AI operator reviewed and approved Undo; all 36 IDs returned in exactly their original order.

The recorded status is `lifecycle_verified`. The scorer was the deterministic fixture scorer, not a trained recommender. This was assistant review, not a human relevance review. The application checked quotation custody; that alone does not establish semantic correctness.

## Calls and process observations

| Stage | Start UTC | Elapsed seconds | CLI cost estimate, USD |
| --- | --- | ---: | ---: |
| Action interpretation | 2026-11-15 08:07:40.391428 | 11.142 | 0.116024 |
| Evidence grounding | 2026-11-15 08:07:51.540231 | 18.865 | 0.166096 |

Both calls reported `claude-fable-5-2`, `success`, one turn, `is_error=false`, `end_turn`, and runner exit 0. Both strict stream projections passed and retained only `end_turn` as an intermediate stop reason. Both recorded unknown rate-information fields; discarded metadata cannot be interpreted from those flags, and complete intermediate coverage was not established.

Both owned lifecycle records report stdin complete, stdout EOF, root exit 0, termination returned, cleanup complete, I/O completion and close returned. Each last observed job-member count was zero. These are owned-job observations, not a global process inventory. The outer execution session also returned exit 0 according to the execution report.

## Source and evidence identity

The execution report binds this run to commit `87446ce95a6c755a7f9ebdb3a412e1f2f878a4c0`, with the published personal adapter and a separately reviewed task-local launcher, transport and workflow. This does not qualify the general quickstart CLI route or provide a portable public launcher.

- Original local result, 13,359 bytes: SHA-256 `abdc043ee1648a27fd1be9eeec5b21d66cb5490edd1fc021128a2fe0e19511bc`.
- Exact filesystem source inventory: `ea637f361d606ed9cce7d2c3aebbd241dcb098985282699216fc6bc188d0e432`.
- Task-local launcher: `8492b53946f7d2c57f808b0b3f256db394f131d94211d843b4e6cea310713b72`.
- Workflow: `5f4c8525c234e695a19048d28ece238d2533f41bd11d893b0e463a004a42ace0`.

An independent readback reconstructed the result bytes to the original hash and checked the two calls, exact removed set, unchanged preview, restored order and cleanup fields. This note is a factual summary, not the raw provider response. Raw hook configuration and private paths are not published here.

The combined CLI cost estimate was USD 0.28212, not verified billing. Effective effort, hidden managed context and underlying provider-request count remain unverified. No HTTP/ASGI application server, browser, new-category flow, held-out evaluation or model-quality claim is established by this run. Existing frozen research evidence remains unchanged.
