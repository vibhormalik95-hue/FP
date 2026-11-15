# Windows combined language-control check, 15 November 2026

One real Claude Code call completed a mixed request over ten fictional items. The direct application Preview left the feed unchanged; after an AI operator reviewed all seven Preview chunks, Apply removed five food-related items and boosted two music items. The operator reviewed both Undo chunks, and history Undo restored the exact original IDs, order, scores and groups.

The request was "I'm not hungry, remove all the stuff that makes me hungry. Show me more music videos." Removal selected 61001, 61002, 61003, 61004 and 61009 using their supplied labels or caption. The standard boost selected 61007 and 61008, adding 0.25 to each score. The feed changed from 10 items to 5 and back to the original 10. Apply matched the reviewed Preview.

The run lasted from 22:17:22 to 22:19:07 UTC (104.614 seconds). The CLI reported `claude-fable-5-2`, one logical invocation, one turn and `end_turn`; Max effort was requested. It reported 4,835 output tokens and an estimated USD 0.2766816. The request allowed 32,768 output tokens and 300 seconds, with a USD 5 estimated CLI threshold, not a guaranteed billing cap. Actual billing, effective effort and the number of provider-internal requests were not verified.

The owned process record reports root exit 0, completed input and output, cleanup and I/O close, and a last observed job-member count of zero. The outer execution session also exited 0. The sanitized stream projection recorded `end_turn` and no recognized refusal; intermediate-event coverage was unknown and unknown rate information was flagged. The raw CLI stream was not retained.

This used the separately configured personal Windows binding, a task-local launcher, fictional data and a deterministic diagnostic scorer. It called application functions directly: no browser or HTTP/ASGI server was used. The operator was an AI, not a human. This is an integration check, not a production-recommender, model-accuracy or new-category evaluation.

The owner verified the private 81,324-byte result as SHA-256 `7660b3f69a004c5513b5ca2a940d2553990ef418a7b1a9a2923f74c11bec2339`; the structured receipt has SHA-256 `d0f58d65cf655dc4bc4ddb5f9b6fa513982f2219de09740b84e839811f796bb1`. An independent reviewer checked the allowlisted extraction, but did not independently download the original bytes. [The derived evidence](evidence.json) is sanitized; it is not a raw provider receipt or replay input.
