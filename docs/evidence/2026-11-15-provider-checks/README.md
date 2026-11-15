# Provider checks, 15 November 2026

These are small integration checks on invented data. They are separate from the research experiments and the browser demonstrations of 14 November.

## Ollama: fictional-item lifecycle completed on Windows

One request used the OpenAI-compatible route to a local Ollama server with `llama3.1:8b`. The server reported the same model and returned HTTP 200 in 7.137 seconds. It reported 240 input tokens and 56 output tokens.

The request asked for a fictional 40-second clip about repairing a kite. An AI operator read the draft and approved it. The application kept the draft outside the dataset. Preview left the separate feed empty; admission added one item; removal cleared it; restoration returned the same item and content; the final clear left it empty. The catalogue did not change.

The check ran from 05:15:45 to 05:16:09 UTC. The provider connection was real HTTP. The application endpoint functions were called directly in Python, not through an application HTTP server, ASGI client or browser.

Source fingerprint: `6eb7a161b003d086eafadca1123fa75e0a0a00574e58a2ff607f965d1c61fe5c`. The exact source commit was not verified for this run. The original local receipt has SHA-256 `d2292b219672148dc79456f0de0b37d8280108b6e0fde10d692fb654ab30d422`. The owned tree-stop command returned exit code 0; the owned service exited with code 1. These are distinct recorded outcomes, not a clean service exit of 0. The raw local request and response are not included here.

This check covers one fictional-item lifecycle. It does not establish category discovery, indirect intent, browser operation, macOS support or model quality. The draft did not use the literal word “fictional” in its description; the item's synthetic flag, origin and provenance identify it as invented. There is no new playable media.

## OpenAI: connectivity blocked by quota

The existing credential could list models, including `gpt-5.4-mini-2026-03-17`. Configuration validation passed. One connectivity inference attempt then returned HTTP 429 with a quota error. There was no retry, successful inference or lifecycle call. This does not establish the state of any other account or project. A charge was not reported.

A manually saved, sanitized outcome summary has SHA-256 `7c7c20c624e7a069408c5183b736290bb36ab54899ad1f0db837c2a87727b38a`. This is not a raw provider receipt. No key, account identifier, private path or billing amount is included here.

## Evidence boundary

This summary is prepared from the two accountable execution reports and their retained artifact hashes. It does not replace the underlying execution evidence or retrospectively identify an unverified source commit. Existing frozen studies and dated browser records stay unchanged.
