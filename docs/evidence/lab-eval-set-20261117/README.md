# lab-eval-set-20261117 (DRAFT)

**Status: draft. All cases, reference labels, definitions and member judgements were written by an AI agent (Claude, Anthropic)
and have NOT yet been reviewed by a human.** They must be reviewed row by row in `review.csv` (fill `reviewer_agrees` /
`reviewer_correction`) before the set is frozen and used to score models.

**Bias risk:** the drafter is a Claude-family model. Its reading of the requests, its choice of required/acceptable labels and its
membership judgements may line up more closely with how Claude-family models behave than with how other models behave. That could
favour Claude-family models when they are scored. Human review should look for this in particular, for example by checking whether
the "acceptable" sets are wide enough for other defensible readings.

## Files
- `review.csv`: one row per judgement (UTF-8 with BOM so Excel shows Chinese). The reviewer columns are left empty.
- `cases.json`: the machine-readable draft (`version: lab-eval-set-20261117-draft`) with all 40 cases and the shared 150-item pool.
- `README.md`: this file.
A copy of `review.csv` and `README.md` is placed in `C:\Users\vs981\comp9500\FINAL2\eval-review\`.

## Counts
| group | English | Chinese | total |
|---|---|---|---|
| NL | 10 | 10 | 20 |
| NC | 3 | 3 | 6 |
| AB | 7 | 7 | 14 |
| all | 20 | 20 | 40 |

Judgement rows in `review.csv`: **1211**. By type: action = 20, label = 271, definition = 6, member = 900, expected_status = 14.
- NL label rows: required = 38, acceptable = 140, not relevant = 93. NL actions: boost = 7, hide = 4, only = 3, reduce = 6.
- NC draft members per case (out of 150): NC01 = 17, NC02 = 16, NC03 = 13, NC04 = 20, NC05 = 17, NC06 = 16.
- AB expected statuses: ambiguous = 7, no_match = 2, unsupported = 5.

## How the set was built
**Label vocabulary.** The catalogue was loaded with `feedctrl.kuairec_catalog` (`read_caption_table`, `build_catalog`, `load_gloss`,
`label_vocabulary`). The models see only every `kind=="category"` term (266) plus every `kind=="tag"` term with `item_count>=3` (201),
467 terms in total. Every reference label was checked against that list by script.

**NL (nonliteral requests, 20).** Each request expresses one preference indirectly, through a personal situation, slang, a metaphor
or an example (e.g. a golden retriever arriving, a team knocked out of the playoffs, a brother on deployment, 楼下大妈的音响,
纸片人, 海绵笔蘸水写大字). Each has exactly one action (boost / reduce / hide / only). Domains: pets, sports, comedy, military,
beauty, travel, kids, cars, health, relationships, rural life, celebrity gossip, square dance, gaokao/education, anime,
disaster news, fashion, singing, fitness, calligraphy. For each case the CSV lists the REQUIRED labels (a careful annotator
would definitely select them), the ACCEPTABLE labels (defensible but optional) and 3-6 near-miss distractors marked "not relevant".
Any label not listed counts as wrong. A script checked that no ZH request contains a vocabulary value as a substring and that no
EN request uses a label's name or a key word from its English gloss. Several wordings were changed after this check (for example
"运动裤" became "卫裤", and "doctor" and "start a family" were removed). The remaining hits are incidental words such as "years",
"every" and "today".

**NC (new-category descriptions, 6).** Each case has a user-style description, a reference label (≤60 chars) and an operational
definition (≤600 chars) with explicit inclusion and exclusion conditions. The cases cover concepts that KuaiRec has no single label
for: first responders on duty, set abroad / foreigners, before-and-after transformations, rain/storm/flood scenes (雨雪风暴或洪涝),
explicit money amounts (具体金额) and grassroots workers at work (基层劳动者). **Pool construction:** the six cases share one pool of
150 items, all with `has_text=True`. 125 items were picked on purpose: likely members and hard negatives (topically close
items that fail a condition, such as a Chinese lake that "looks like abroad", "2块鸡块", a welder used as a pick-up line, career
"逆袭" stories, firefighters playing tug-of-war). They were found with regex searches over title, caption, tags, categories and
the English gloss. The other 25 items were drawn at random (seed 20261117) from the remaining has_text items. The drafter
read every pool item and judged each of the 6x150 pairs from the item text alone, applying the definition strictly: if the text
does not establish every condition, the item is not a member. Borderline calls are explained in the `notes` column. 92
pool items are a draft member of at least one case.

**AB (abstain cases, 14).** These are cases where the correct behaviour is to propose no control:
ambiguous requests (competing subject readings, an unclear action, a polysemous word),
unsupported operations (an hourly quota, a weekday time window, an ordering, a fixed ratio, a skip-triggered time-limited rule),
no_match subjects (tarot/horoscopes and lottery number-picking, checked against the vocabulary), and hypothetical, negated or
non-request statements (drafted as "ambiguous"). Each has a short reason.

## Overlap / leakage check
Compared against: `tools/demo_examples.json`, `scenarios/categories-and-tags/requests.json`, `data/parser_test.jsonl`,
`data/parser_dev.jsonl`, and every JSON/JSONL file in the exposed 4 Nov bank
(`...\experiment2\comp9500-reviewed-topic-20261104-v1`, including `study/inputs/*.jsonl` inside the v2 zip). Those files were
read only for this check. Every request, description and definition was compared with every sentence segment of those sources
(3,404 segments) using character-3-gram Jaccard similarity. **Result: no exact or near-paraphrase overlap.** The highest
score was 0.222 (AB03 vs. "Do not hide the cooking videos." from scenario_requests). All other scores were lower, and all Chinese items were below 0.04.
The 4 Nov bank consists of literal requests about quoted topic names, which this set does not use. The demo topics were avoided
on purpose: there is nothing about being hungry or full, a cat at the vet, marathon motivation, or a break from negative news.
NL16 (fewer accident/disaster clips on a father's tablet) is the closest in theme, but it is about an elderly relative's sleep,
names a different news subtype, and asks to reduce rather than to take a break. The NC concepts do not reuse the demo concepts
(outdoors in nature, teaching a practical skill) or the examples given in the task brief.

## Known limitations / reviewer attention
- Required sets are deliberately tight. Several obvious upgrades are flagged in the notes (e.g. NL11 种植业/养殖业).
- NC03 has the fewest members (13). Several of them rest only on a trend hashtag such as 变装/变身.
  NC01, NC04 and NC06 have several flagged borderline calls.
- KuaiRec texts are short. Some members (e.g. NC02 item 745, which is only "没有黑夜的冰岛") rest on a single phrase.
- Tag semantics vs. tag contents: some tags have a name that does not match their items (e.g. tag:快手广场舞 is on Latin-dance
  items, and tag:关注我带你看天下 is on world-news items). Reference labels were chosen by what the label name means.

## Human review and freeze (17 November 2026)

- Reviewer: **Vibhor Malik**. All 1,211 rows were read and judged individually (not a sample). Reviewed file: `review_human.csv`.
- Result: 1,187 rows agreed, 24 disagreed. Corrections applied by type: label 9, member 10, definition 2, expected_status 3.
- Tiered-protocol stop rule ("3 or more sampled 'no' rows wrong"): met formally, because 3 of the 796 unflagged draft-"no" member rows were marked wrong (NC02 8518 → member; NC02 8563 and NC06 5656 → dropped from scoring). Resolved by the reviewer: every row was reviewed in full, so these 3 errors (3/796) were found and corrected; no unreviewed draft row remains.
- Handling accepted by the reviewer:
  - Items marked "either (drop from scoring)" are excluded from scoring for every model (NC01: 8382, 4518, 2871, 8874, 3913, 3970; NC02: 8563; NC04: 833; NC06: 5656). They stay in the pool, so models still classify them.
  - Same-name tag twins of a required category are "acceptable", not "required", in every case (NL02 tag:篮球, NL17 tag:穿搭, NL20 tag:书法 changed; NL03, NL09, NL19 already were). Other label changes: NL03 tag:迷惑行为大赏 → acceptable; NL05 category:美妆 → acceptable; NL06 tag:关注我带你看天下 → acceptable; NL13 tag:快手广场舞 → acceptable; NL14 category:学业教育 → acceptable; NL19 category:瑜伽 → acceptable.
  - NC01 definition: condition (2) also accepts a text that states the person is on duty in the events shown (e.g. 执勤, 出警, 抗洪); soldiers are named in the description ("police, firefighters, soldiers, medics and other first responders"), as the reviewer allowed ("drop soldiers or name them in the description").
  - NC06 definition: the occupation list ends with "及同类一线体力或服务劳动者" (and similar front-line manual or service workers).
  - AB12, AB13, AB14: correct when no control is proposed, whatever status word the model returns (`expected_status: any_abstain`).
- Chinese requests were judged through the English gloss (machine translation) shown beside them; the requests were not rewritten after the review.
- The reference set was AI-drafted (Claude, Opus 5.5) and human-reviewed. Claude is both the drafter's family and a measured model (Claude Sonnet 5.5 through the CLI); this is a disclosed risk of bias toward Claude-family readings.
- No prompt, threshold or code that affects predictions is changed after the hashes below are committed.
