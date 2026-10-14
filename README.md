# Natural language controls for short video recommendation

## Latest local execution

The [14 October execution record](docs/execution-2026-10-14.md) documents a local Llama 3.1 8B diagnostic on the 100 exposed worked-practice questions. Its AI reference labels cannot establish unseen-test or human-label accuracy. Formal E2 remains pending a prospective supervisor decision, replacement bank and valid annotation route. The original protocol, parser commitment and all 288 frozen E1 files are preserved. See the [plan reconciliation](docs/supervision/2026-10-14-execution-checkpoint.md) and dated October 14 deliverables for the verified update; earlier records below retain their historical dates.

The reviewed practice result is **73/100 validated agreement**, with **23.81% control success** versus rules **8.40%** and item feedback **3.92%**, alongside lower NDCG@10 (**0.02461 versus 0.03128** for item feedback). It does not complete formal E2.

- [Seven-page main paper](deliverables/COMP9500-Research-Paper-2026-10-14.pdf), [ten-page supplementary extended report](deliverables/COMP9500-Supplementary-Extended-Report-2026-10-14.pdf) and [29-page BCIT slide PDF](deliverables/COMP9500-BCIT-Presentation-2026-10-14.pdf)
- [Weekly update](deliverables/COMP9500-Weekly-Progress-Update-2026-10-14.docx), [completion checklist](deliverables/COMP9500-Evidence-and-Completion-Checklist-2026-10-14.docx) and [unsent professor reply](deliverables/COMP9500-Professor-Email-Draft-2026-10-14.txt)
- [Delivery, visual review and rendering limitations](docs/delivery-2026-10-14.md), [public audit evidence](docs/evidence/2026-10-14/) and [prospective formal amendment](docs/formal-e2-prospective-amendment.md)

The main paper has six report pages plus one page of references. Full local evidence is retained separately. The slide PDF uses documented PDF composition because the installed Beamer dependencies are incomplete; no successful Beamer rebuild is claimed.

COMP 9500 research project by Vibhor Malik, supervised by Dr Borna Noureddin. Documentation updated 4 October 2026, Vancouver time.

The project has a working research prototype, a completed first experiment and a prepared follow-up experiment. The clearest result so far is that category rules change the feed as intended, while the simple requests tested show no added ranking benefit from an LLM. The next priority is to test the richer-intent question in Experiment 2 and make the final paper fully traceable to evidence.

This public repository is a **partial code-review copy**. It contains implementation and test source, the frontend, the current paper and BCIT slides, and planning documents. Research data, models, results, caches, reserved language material and original source evidence remain in the separate full research archive. Full experimental replay and full-suite verification require that archive.

## October 13 delivery

The finalized current packet is available as dated files. Earlier reports, plans and historical records are retained.

- [Weekly progress update](deliverables/COMP9500-Weekly-Progress-Update-2026-10-13.docx)
- [Evidence and completion checklist](deliverables/COMP9500-Evidence-and-Completion-Checklist-2026-10-13.docx), including methods and provenance
- [Professor email draft — unsent](deliverables/COMP9500-Professor-Email-Draft-2026-10-13.txt)
- [Practice answer guide](deliverables/COMP9500-Practice-Answer-Guide-2026-10-13.docx)
- [100 worked practice answers](deliverables/COMP9500-Worked-Practice-100-2026-10-11.csv)

The guide and CSV are exposed AI-generated practice, not independent annotations or formal E2 evidence. Formal E2 remains pending. The packet records the engineering baseline at `7ab27c2`; the delivery commit adds the finalized files without rewriting that baseline. [Delivery provenance and checks](docs/delivery-2026-10-13.md) identify exact versions and hashes.

## Current documents

- [Supervisor progress report](docs/final-progress-report.md) and [Word document](deliverables/COMP9500-Supervisor-Progress-Report.docx).
- [135-hour completion plan](docs/135-hour-plan.md) and [Word document](deliverables/COMP9500-135-Hour-Plan.docx).
- [Research status](docs/experiment2-status.md), [paper](deliverables/COMP9500-Research-Paper.pdf) and [BCIT presentation](deliverables/COMP9500-BCIT-Presentation.pdf).
- [Weekly records](docs/supervision/README.md), [supervisor questions](docs/supervisor-decision-packet.md) and [defence guide](docs/defence-guide.md).

The proposed plan assigns 135 future active student hours from 5 October to 18 December 2026. It includes a readiness decision on 23 October and a complete paper draft by 27 November. The final submission date remains subject to supervisor confirmation. Proposed check-ins are Wednesdays at 10:00 am Vancouver time, with an update by Tuesday at 10:00 am and minutes after each meeting.

## Experiment 1

On 865 users and 2,593 candidate items, target-category proportion rises from 11.6% to 79.2%, and muted-category exposure falls from 6.1% to zero. Hard exclusion produces zero exposure by construction. Llama parses 120/120 templated inputs, 79/100 broader synthetic inputs and 2/10 adversarial cases. The broader-set score clears the 70% floor but misses the 85% target. All 10/10 recorded explanation cards equal the template, and the rule and LLM parsers produce identical feeds on the templated ranking task.

Steering has a quality cost: boost NDCG@10 falls 45.7%, from about 0.03012 to 0.01637. The non-inferiority check is uninformative at this low baseline. Backbone HR@1 ranges from 0.0% to 0.46% across seeds, versus about 8.0% for recency popularity. Different access to recent aggregate information makes that comparison diagnostic. The study establishes bounded category control and its observed costs. It does not establish improved recommendation accuracy, a more natural user experience or an LLM expressiveness advantage.

Experiment 1 results, models, prompts and gold labels remain frozen in the full archive. The [evaluation protocol](docs/evaluation-protocol.md) explains the analysis and the two readings of the original non-inferiority margin.

## Experiment 2

The follow-up covers compound, graded, nonzero-floor and conditional intents. Its bank contains 48 development and 100 reserved cases, with all 31 category identifiers in each split. Development v2 records 48/48 exact matches for both parsers. This is development fit. The earlier Llama result of 24/48, including ten operational errors, is retained in the full archive.

The reserved evaluation has not run. H1 expressiveness and H2 intended movement per interaction are not assessed, and H3 quality-cost analysis has not run. Execution depends on the student annotation and exposure procedure, agreement and blinded adjudication, the existing parser commitment, the full freeze and a verified Llama 3.1 8B runtime. The recorded 3 October runtime check found no available Ollama service in that environment. It does not establish the state of the student's laptop today.

Read the [protocol](docs/experiment2-protocol.md), [annotation handoff](docs/annotation-handoff.md) and [runbook](docs/experiment2-runbook.md). Preserve the committed procedure, report parser accuracy before ranking results and do not tune on reserved outcomes. If H1 or H2 fails, report that natural-language feedback did not demonstrate an expressiveness advantage under this protocol and explain why.

## Verification status

The recovery records include recomputation of 51,900 Experiment 1 metric rows. The October engineering review records 271 passing tests plus 44 passing subtests, 17 Chromium checks and a byte-identical frontend rebuild. A later numerical audit reproduced all 25,950 top-10 lists but found 2,009 full-ranking hash differences and 5,190 request-score hash differences with an unresolved cause. These are recorded project checks, not new checks of this documentation update.

Full research execution on Windows 11 and Google Colab remains unverified. The [13 October Windows engineering check](docs/verification-2026-10-13.md) records synthetic tests and preservation of all 288 E1 file hashes. See the [progress report](docs/final-progress-report.md) for historical evidence and the [methods and provenance note](docs/academic-use.md) for assistance and activity records.

## Repository contents

| Path | Contents |
| --- | --- |
| `feedctrl/` | Recommender, parser, deterministic controls, API and evaluation source |
| `web/` | React source, dependency lockfile and frontend build |
| `tests/` | Test source; many tests require omitted research artifacts |
| `scripts/` | Research, packaging and document-generation utilities |
| `paper/` | LaTeX manuscript, bibliography and IEEE template |
| `presentation-bcit/` | BCIT Beamer source and speaker notes |
| `deliverables/` | Current paper, slides, reports and plan |
| `docs/` | Protocols, handoff instructions, progress and supervision records |

[README-CODE-REVIEW.md](README-CODE-REVIEW.md) describes the scope of this copy. [Windows and Colab instructions](docs/windows-and-colab.md) describe the full-archive workflow; do not treat this partial repository as the full evidence package. The application uses research metadata cards, not licensed video playback.

## Repository handoff

The first public commit is [a9a9c4d](https://github.com/vibhormalik95-hue/FP/commit/a9a9c4d46c7c59a00be3bd986338a222a855d090). Supervisor access has not yet been confirmed. The [handoff record](docs/repository-handoff.md) identifies the archive and sharing scope. Keep actual hours, meetings, reading and personal verification in the weekly records as they occur.
