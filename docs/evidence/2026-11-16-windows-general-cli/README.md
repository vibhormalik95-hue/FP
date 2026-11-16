# Windows general CLI combined request, 16 November 2026

One real Claude Code invocation produced a combined proposal for ten fictional items through the general `cli` route on Windows. An AI operator then reviewed the proposal in Opera. The browser report and the retained CLI receipt describe different parts of the run; the receipt alone does not establish Apply or Undo.

## Request and browser report

Request: "I'm not hungry, remove all the stuff that makes me hungry. Show me more music videos."

The browser report says that Preview left the current feed's IDs, order, scores and applied controls unchanged. It reports that the AI operator reviewed the actual proposal, applied it, then reviewed and applied Undo. Apply excluded IDs 61001, 61002, 61003, 61004 and 61009, and boosted 61007 and 61008 by 0.25. Undo restored all ten items in their original order and with their original scores, with zero controls applied.

The selected food evidence included item 61004's caption about a mechanic eating a sandwich, despite its Repair category. The selected music items carried Music category evidence. The scenario uses invented metadata and a deterministic diagnostic scorer; this is an integration check, not a human evaluation, trained-recommender result or accuracy estimate.

## Retained CLI evidence

The private receipt records one logical invocation, started at 08:32:27 UTC and finished at 08:34:30 UTC, with 123.387 seconds elapsed. It reports requested and returned model `claude-fable-5-2`, `success`, one turn, `end_turn`, `is_error=false` and exit 0. The CLI reported 11,920 output tokens and an estimated cost of USD 0.5603058. This estimate is not verified billing; provider-internal request count and effective effort remain unverified.

The recorded input contains the exact request and all ten fictional items, including the sandwich caption. The returned controls name the five exclusions and two boosts above; their quotations match the supplied fields. This checks quotation custody, not semantic correctness by itself.

- Private receipt SHA-256: `1d5b3f445e8794cfe91343883c8492f879d3a6c5adc2a678fd789d1e6bcb6563`.
- Recorded CLI input SHA-256: `12a28c411a15a453b24612ffcfe5caf547017accc796d5c219a639dc4cc4bd6e`.
- Recorded CLI output SHA-256: `20981790b6fd17367b9d7e1ae6f441f0db513551d6c243e5ac13fe936668307a`.

The server used an isolated source candidate based on commit `39c014b4e359a3fd929c314fe81e0289f120dbc7`, with a separately reviewed change to the combined prompt and schema descriptions. Its `feedctrl/combined_grounding.py` SHA-256 was `146b019b39bd97fa8e60dc17b9411a131342eedbb90374e4b146e16b928b69c6`. That prompt change was not part of the base commit. The general route's response checks and process cleanup are distinct from the separate personal Windows CLI runner.

This result does not establish a successful OpenAI route, playable video, production ranking, or universal model reliability. The earlier OpenAI failure and other dated evidence remain separate and unchanged. Raw CLI records, local paths and account details are not published in this note.
