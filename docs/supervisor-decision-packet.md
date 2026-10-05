# Questions for the supervisor

Vibhor Malik | Borna Noureddin | Prepared 3 October 2026 UTC

The project now has a completed first experiment, a follow-up protocol, a draft paper and a presentation using the supplied BCIT template. The first experiment shows deterministic feed control and a quality cost. It does not establish an LLM advantage. The reserved follow-up is blocked by the independent student annotation requirement and unavailable Ollama runtime.

The aim of the next meeting is to confirm the remaining decisions and the evidence expected from the student. The supplied proposal copy is unsigned with blank research-path and approval fields. The course email and meeting excerpts document requirements, not approval of the revised methodology.

## Decisions to record

| Question | Proposed treatment | Record after discussion |
|---|---|---|
| Is the implemented scope approved for COMP 9500? | Review the proposal amendment and confirm the course path, title and applicable approval process. | Accepted scope, required changes and approval evidence. |
| How should the existing NI wording be interpreted? | Keep both readings of Experiment 1: the absolute numerical pass is uninformative, and the relative reading is unsupported. Any new margin belongs in a new prospective study. | Original intended reading and reporting requirements. |
| How should annotation exposure be handled? | Record what the student has already seen, including development accuracy summaries. Resolve independence before the student pass; preserve the current reserved bank and parser commitment. | Whether the existing procedure remains valid, or what prospective replacement procedure is required. |
| What student evidence and AI disclosure are required? | Submit the detailed disclosure and keep a real reading, code-review, reproduction and activity log. Never claim that AI work was personally performed. | Applicable policy and specific demonstrations expected. |
| What is the final December deadline? | Use 18 December as a provisional planning endpoint, with 135 future hours spread over the remaining 11 weeks. | Confirmed submission and presentation dates; changes to workload. |
| Are the meeting details correct? | Weekly Wednesday 10:00 am Vancouver, approximately 30 minutes, with an update Tuesday by 10:00 am and minutes afterwards. | Recurring invitation, any time change and preferred document location. |
| How should code access be shared? | Prepare a private repository and provide supervisor access after the repository destination is selected and annotation exposure is considered. | Repository URL, account to invite and access confirmation. |
| Is the final artifact format acceptable? | Use IEEE-format LaTeX for the 6 to 10 page paper and the now-supplied BCIT Beamer presentation template. | Any required formatting changes and delivery mechanism. |

The form provides Supervisor, Program Head and Associate Dean signature blocks. Ask which process applies; do not infer additional institutional requirements or fill signatures and dates on someone else's behalf.

## Evidence for the discussion

- [One-page status](experiment2-status.md) and [progress report](final-progress-report.md).
- [Proposal amendment](proposal-amendment.md) and the supplied [unsigned proposal](sources/COMP9080-Proposal-Unsigned.docx).
- [Course email transcript](sources/course-email-transcript.md) and [meeting excerpts](sources/supervisor-meeting-excerpts-2026-10-02.md). These are supplied transcripts, not independently authenticated messages.
- [Academic-use disclosure](academic-use.md), [annotation handoff](annotation-handoff.md), [protocol](experiment2-protocol.md) and [runbook](experiment2-runbook.md).
- [135-hour plan](135-hour-plan.md) and [weekly supervision records](supervision/README.md).
- [Research paper](../deliverables/COMP9500-Research-Paper.pdf), [BCIT slides](../deliverables/COMP9500-BCIT-Presentation.pdf) and [repository handoff](repository-handoff.md).

## Suggested opening for the meeting

The first experiment is finished. It shows that explicit category rules change the feed as intended, but the LLM gives the same rankings as the rule parser on the templated requests. Broader parsing reaches 79%, below the 85% target, and boosting costs recommendation quality. I have a separate follow-up ready to test richer intents, but I cannot yet report its reserved results. I would like to agree the annotation procedure, the scope and disclosure requirements, and the remaining timetable.

This is preparation text, not a claim that the student has already delivered it or independently verified every result. Use the defence guide and actual evidence before the discussion.

## Draft message for student review

Subject: COMP 9500 progress, remaining experiment and weekly plan

Hi Professor Noureddin,

I have prepared the project report, paper draft, updated slides using the BCIT template, and a proposed plan for the remaining term.

Experiment 1 shows that the fixed category policy controls exposure, but it does not show an advantage from the LLM over the rule parser. The broader language benchmark misses the 85% target, and category boosting reduces historical ranking quality. Experiment 2 is prepared to test richer intents, but its reserved results remain pending. I need to complete the genuine independent annotation requirement, resolve my prior exposure to development summaries, and restore the recorded local Llama runtime before it can run.

The plan allocates 135 future hours to verification, completion and revision. It uses 18 December as a provisional endpoint. Could we confirm the final deadline, revised scope, AI disclosure and annotation procedure at our next meeting?

I understand our check-ins are Wednesdays at 10:00 am, with an update by Tuesday at 10:00 am and notes after each meeting. I am also preparing private repository access and will send the link once it is set up.

Thank you,
Vibhor Malik

This draft has not been sent. Attach current files only after reviewing them. Record the supervisor's actual decisions in the meeting minutes; unanswered questions are not approvals.
