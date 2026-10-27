# Code map and contribution worksheet

Code locations were inspected at FP `bec8442dd7fbd43535ded943f886add2cb50cd8d` on 27 October 2026. This records what the code does. It does **not** assign personal authorship from commit ownership, file type or the meeting transcript. The transcript says the student prompted AI to help create Python files and manually reviewed them; it also contains a conflicting broad statement that non-Markdown files were manually created. `docs/academic-use.md` discloses substantial AI assistance. The student should replace the unknown entries below from their own records before speaking in the first person.

| Diagram block | Code to open | Explain from the code | Student's original design/code/adaptation and verification |
| --- | --- | --- | --- |
| D1 | `feedctrl/data.py:91-194` | KuaiRec preprocessing, cohort, chronological train/request/test windows and catalog metadata | **Unknown personal contribution.** Record prompt/AI, own edits, source and checks. |
| M1 | `feedctrl/model.py:26-88,106-237` | SASRec-style embedding/attention network, training examples, checkpoint and score call | **Unknown personal contribution.** It is an independently implemented variant, not a claim of writing the SASRec method. |
| S1 | `feedctrl/api.py:81-95,140-149` | Data/model selection, scoring each candidate from earlier history | **Unknown personal contribution.** Explain why status distinguishes trained versus diagnostic scorer. |
| A1 | `feedctrl/api.py:150-157,295-305`; `feedctrl/evaluation.py:75-84` | Item like is a +0.25 one-item boost; dislike removes one item in A/B | **Unknown personal contribution.** Explain why this is simulated feedback, not an observed KuaiRec thumb. |
| X1/P1/V1 | `feedctrl/controls.py:84-119,179-294`; `feedctrl/api.py:243-293` | Rule or Ollama text parsing, schema/category grounding, profile parsing and state preservation on failure | **Unknown personal contribution.** Name AI-generated sections, manually changed sections, prompt/rubric origin and checks. |
| R1 | `feedctrl/controls.py:297-339` | Normalize, merge latest explicit command with profile, hard-exclude mute, sort | **Unknown personal contribution.** Walk through one boosted and one muted item. |
| O1/E1 | `feedctrl/evaluation.py:23-84,109-374`; `feedctrl/experiment2_evaluation.py:199-455` | Assigned requests, ranking metrics, user-level aggregation, E2 success analysis | **Unknown personal contribution.** Identify any AI-generated arithmetic and personally verified examples. |
| EX1/U1 | `feedctrl/explanations.py:20-86`; `web/src/main.jsx:5-90` | A-E UI, session calls, saved Llama fact selections or template signals, and provenance labels. Explanation display does not rerank. | **Unknown personal contribution.** Show a browser check and describe any third-party frontend library use. |

## Fill in before claiming personal work

For each block, the student should record: (1) the design decision they personally made, (2) code they wrote or changed directly, (3) AI-generated code they accepted or revised, including tool/model if known, (4) third-party source or library used, (5) the test or calculation they personally inspected, and (6) an uncertainty they still need to resolve. A dated git commit can locate the code, but cannot by itself answer who authored or understood it. Leave unknowns blank rather than inferring.

Suggested honest opening, subject to the student's confirmation: "I used AI assistance in developing and reviewing parts of the implementation. I can explain the pipeline and show where the code implements each block. I will identify my own design and review work separately from generated code and third-party methods." Do not say all Python or all non-Markdown files were manually authored unless personal records support that exact claim.

The prototype relies on public KuaiRec data, the SASRec research method, Python/FastAPI/PyTorch and React. Their methods and code dependencies need attribution; the frozen local checkpoint and result files are not proof of personal code authorship. Existing general disclosure: `docs/academic-use.md`. Specific ownership remains a student attestation task.
