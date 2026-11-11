# Two synthetic validation scenarios

These fixtures address the existing project questions: discovering a new category that feeds the filter, and interpreting indirect wording against supplied metadata. They are development examples, not a new benchmark or a model-comparison dataset.

- Category discovery supplies eight invented records and four opaque existing labels. The model chooses a definition; its meaning and all eight membership decisions are reviewed separately. The 11 November attempt stopped after one failed CLI invocation, before a definition or Apply.
- Hunger continuation preserves the exact request, “I'm not hungry, remove all the stuff that makes me hungry.” The original local-model attempt stopped after two calls without Apply. The hosted continuation has not run. A later result must not replace that failure.

Each scenario contains synthetic app data, metadata JSON and equivalent CSV, an initial logical payload/schema, and reviewer notes. Reviewer illustrations are not model input or prescribed answers. SOURCE-EVIDENCE.json preserves exact transcript excerpts and source hashes. The transcript receipt date is not an independently verified meeting date.

The helper loads supplied data with fixture=False; the data itself explicitly declares is_fixture=true. Local models and the trained recommender remain disabled. Category discovery can use up to three logical calls; indirect interpretation can use up to two. These counts do not authorize execution or retries. Later prompts depend on actual earlier output and are captured at runtime rather than prefilled.

MANIFEST.json binds all input files, including non-model documentation. The driver pins that manifest; incomplete configuration templates pin the driver. Changes to documentation therefore require new manifest and driver pins even when model-bound data is identical. See the repository's current progress and validation guide for observed outcomes and remaining work.
