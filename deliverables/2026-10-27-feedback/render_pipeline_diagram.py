"""Render the editable Markdown block IDs as a compact, printable lane diagram."""

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import landscape, letter
from reportlab.pdfgen import canvas
from reportlab.pdfbase.pdfmetrics import stringWidth


HERE = Path(__file__).resolve().parent
OUTPUT = HERE / "PIPELINE-DIAGRAM.pdf"
W, H = landscape(letter)


def box(pdf, x, y, w, title, lines, color):
    h = 66
    pdf.setFillColor(color)
    pdf.setStrokeColor(colors.HexColor("#3b4854"))
    pdf.roundRect(x, y, w, h, 7, fill=1, stroke=1)
    pdf.setFillColor(colors.HexColor("#17222e"))
    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawCentredString(x + w / 2, y + 43, title)
    pdf.setFont("Helvetica", 8)
    for n, line in enumerate(lines):
        pdf.drawCentredString(x + w / 2, y + 28 - 11 * n, line)


def arrow(pdf, left, right, y):
    pdf.setStrokeColor(colors.HexColor("#415362"))
    pdf.setFillColor(colors.HexColor("#415362"))
    pdf.line(left, y, right - 6, y)
    p = pdf.beginPath()
    p.moveTo(right, y)
    p.lineTo(right - 7, y + 4)
    p.lineTo(right - 7, y - 4)
    p.close()
    pdf.drawPath(p, fill=1, stroke=0)


def row(pdf, y, label, specs, tint):
    pdf.setFont("Helvetica-Bold", 9)
    pdf.setFillColor(colors.HexColor("#34495e"))
    pdf.drawString(36, y + 74, label)
    count = len(specs)
    x0, x1, width = 36, 756, 104
    gap = (x1 - x0 - count * width) / (count - 1)
    xs = [x0 + n * (width + gap) for n in range(count)]
    for x, (title, lines) in zip(xs, specs):
        box(pdf, x, y, width, title, lines, tint)
    for index in range(count - 1):
        arrow(pdf, xs[index] + width + 4, xs[index + 1] - 4, y + 33)


def wrapped(pdf, value, x, y, width=720, size=9, leading=13, bold=False):
    """Draw bounded body text and return the next baseline."""
    font = "Helvetica-Bold" if bold else "Helvetica"
    pdf.setFont(font, size)
    words = value.split()
    line = ""
    for word in words:
        candidate = f"{line} {word}".strip()
        if line and stringWidth(candidate, font, size) > width:
            pdf.drawString(x, y, line)
            y -= leading
            line = word
        else:
            line = candidate
    if line:
        pdf.drawString(x, y, line)
        y -= leading
    return y


def detail_page(pdf, number, title, subtitle, sections):
    pdf.showPage()
    pdf.setFillColor(colors.HexColor("#17222e"))
    pdf.setFont("Helvetica-Bold", 17)
    pdf.drawString(36, 570, title)
    pdf.setFont("Helvetica", 9)
    pdf.drawString(36, 552, subtitle)
    pdf.setStrokeColor(colors.HexColor("#b5c2ca"))
    pdf.line(36, 542, 756, 542)
    y = 523
    for heading, body in sections:
        pdf.setFillColor(colors.HexColor("#284c63"))
        y = wrapped(pdf, heading, 36, y, size=10, leading=14, bold=True) - 2
        pdf.setFillColor(colors.HexColor("#17222e"))
        y = wrapped(pdf, body, 44, y, width=704, size=9, leading=13) - 11
        if y < 48:
            raise ValueError(f"Page {number} overflows after {heading}")
    pdf.setStrokeColor(colors.HexColor("#b5c2ca"))
    pdf.line(36, 39, 756, 39)
    pdf.setFont("Helvetica", 8)
    pdf.drawString(36, 26, "COMP 9500 | 27 Oct 2026 | source and detailed evidence in the companion Markdown packet")
    pdf.drawRightString(756, 26, f"{number} / 4")


def main():
    pdf = canvas.Canvas(str(OUTPUT), pagesize=(W, H))
    pdf.setTitle("COMP 9500 pipeline: history, item feedback, manual reference, LLM")
    pdf.setFont("Helvetica-Bold", 16)
    pdf.setFillColor(colors.HexColor("#17222e"))
    pdf.drawString(36, 570, "COMP 9500 pipeline and LLM boundary")
    pdf.setFont("Helvetica", 9)
    pdf.drawString(36, 553, "Code mapping and precise limits: PIPELINE-AND-CODE-WALKTHROUGH.md | FP bec8442 | 27 Oct 2026")

    row(pdf, 450, "1  Uncontrolled history-only reference (not Condition A after feedback)", [
        ("D1", ["KuaiRec split", "and catalog"]),
        ("M1", ["frozen SASRec", "checkpoint"]),
        ("S1", ["score from", "earlier history"]),
        ("N1", ["normalize", "base scores"]),
        ("R0", ["neutral", "rank sort"]),
        ("O1", ["top 10 and", "metrics"]),
    ], colors.HexColor("#e7f0f5"))
    row(pdf, 337, "2  A/B item feedback (one item; B adds display-only explanations)", [
        ("N1", ["same frozen", "base scores"]),
        ("A1", ["like +0.25 or", "dislike one item"]),
        ("R1", ["shared", "ranking policy"]),
        ("O1", ["top 10 and", "metrics"]),
    ], colors.HexColor("#edf0e5"))
    row(pdf, 224, "3  Independently established human intent: conceptual reference, not a live backend", [
        ("H0", ["person records", "intended action"]),
        ("V1", ["canonical/allowed", "category check"]),
        ("R1", ["same scores and", "ranking policy"]),
        ("O1", ["top 10 and", "metrics"]),
    ], colors.HexColor("#f5eedf"))
    row(pdf, 111, "4  Implemented control language path: rule or local Llama parsing enters at P1", [
        ("X1", ["explicit text or", "saved profile"]),
        ("P1", ["rule / Ollama", "interpretation"]),
        ("V1", ["schema and", "grounding check"]),
        ("R1", ["same scores and", "ranking policy"]),
        ("O1", ["top 10 and", "metrics"]),
    ], colors.HexColor("#eee8f3"))
    pdf.setFont("Helvetica", 8)
    pdf.setFillColor(colors.HexColor("#34495e"))
    pdf.drawString(36, 73, "E1 reads O1. U1 displays O1; EX1 can use earlier cached Llama fact selection or a template, without reranking.")
    pdf.drawString(36, 61, "A rule-mode feed change proves shared control enforcement, not unique LLM benefit or human satisfaction.")
    pdf.setFont("Helvetica", 8)
    pdf.drawRightString(756, 26, "1 / 4")

    detail_page(pdf, 2, "Data, score and comparison paths", "Follow the block IDs on page 1; these are implementation paths, not independent experiments.", [
        ("D1  KuaiRec input and split", "feedctrl/data.py:91-194 builds the processed catalog, user histories and split metadata. Training, request-history and final-test windows are separate. Synthetic E1 requests use earlier history; the held-out outcomes do not become real user intent. Check the saved manifest before reproducing an evaluation."),
        ("M1 and S1  Frozen model and base scores", "feedctrl/model.py:26-88 embeds item IDs and positions, passes histories through two causal attention/pointwise blocks (hidden 32, one head, last 50 items), then scores each candidate by dot product with the final history state (model.py:203-223). Saved seed-42 trained model was used for the worked example. Diagnostic scoring is a separately labelled fallback."),
        ("How M1 was trained", "_training_examples at model.py:89-103 uses train transitions only. train_model at 106-190 fits one uniform negative per valid step with positive/negative softplus loss, Adam and gradient clipping, then stores checkpoint and metadata. Saved seed-42 metadata records 20 fixed epochs, batch 64, learning rate 0.001; seeds 42-44 are used in the study. No request-history or test item enters gradients; this is an exploratory backbone, not a convergence claim."),
        ("N1 and R0  Untouched history-only reference", "controls.normalize_scores at feedctrl/controls.py:297-305 normalizes base scores. Empty command and profile produce a neutral sort through rerank at lines 326-339. R0 is the history-only calculation; current Condition A is a different comparator once item feedback is applied."),
        ("A1  Manual UI feedback proxy", "The A/B path adds 0.25 to one liked item and excludes a disliked item from the returned ranking (api.py:150-157). /api/feedback at 295-305 stores the latest direction; clear removes that stored choice. evaluation.item_feedback_ranking at 75-84 is the offline proxy. KuaiRec has no observed thumbs labels."),
        ("H0  Manual known-intent example versus study", "The packet already demonstrates explicit category_1 boost and category_28 mute with known specified actions; they can enter V1 and the same R1 policy. H0 is not a separate live human-parser backend. The completed student worksheet, 99/100 comparison and exposed-practice 73/100 versus 18/100 parser check are descriptive, not a fresh held-out human ranking evaluation."),
    ])
    detail_page(pdf, 3, "From language to a changed feed", "Only P1 is the candidate language-understanding advantage; the recommender and enforcement are shared.", [
        ("X1 and P1  Text, profile, rule or Ollama", "api.py:243-293 accepts control text and editable profile text. controls.parse_control at 243-254 and parse_profile at 257-294 select rule or local Ollama. One free-text control requires exactly one explicit category_N ID; a profile can contain multiple allowed explicit IDs. Named topics are not inferred. Parsed JSON is a proposed action, not a feed change by itself."),
        ("V1  Validate before state changes", "controls._validate_control at 104-119 checks keys, operation, fixed strength and allowed category. Textual grounding to exactly one explicit ID occurs in parse_control at 250-253; profile grounding occurs in parse_profile at 291-292. Invalid or ambiguous language fails or clarifies. Ollama error returns HTTP 502 and preserves prior state, with no silent rule fallback."),
        ("R1 and O1  Shared policy, rank and response", "controls.apply_to_profile at 308-323 gives an explicit same-category command precedence. rerank at 326-339 adds category boost weights and hard-excludes muted-category items before sorting. The top 10, scores, preference counts and notices are returned through feedctrl/api.py. The rule and LLM paths use the same scoring and policy after validation."),
        ("A-E conditions and explanation boundary", "A: one-item feedback. B: A plus display-only explanations, so order stays equal. C: parsed free-text category control. D: saved explicit profile preference. E: profile plus explicit control; the later same-category command wins rather than double-counting. EX1 in feedctrl/explanations.py:20-86 selects constrained saved facts or a labelled template; an earlier cached Llama selection may be present, but display does not rerank and human response was not measured."),
        ("One executed rule-mode example, not a new science result", "With saved processed data, user 14 and seed-42 model: neutral top three 8958, 7383, 1116. Like item 1116 makes it first in A and B. Explicit category_1 boost yields nine of ten target items in matched C/D/E; muting category_1 in E removes them. The receipt and reproducer are in the companion packet. No fresh LLM call or browser action is implied."),
        ("Current language limit", "The rule and Ollama prompts map less/fewer to HARD mute because this UI has no quantitative soft decrease. category_N identifiers are opaque and must be explicit. A successful parse therefore demonstrates a narrow grounded command, not universal free-language understanding or satisfaction."),
        ("Visible UI route", "web/src/main.jsx gets session and status, selects user and A-E condition, calls GET /api/feed, POST /api/feedback or /api/control or /api/profile/text, then refreshes feed/notice/count. GET /api/compare requests A-E views; POST /api/reset clears this user's controls and item feedback. Read data/model/parser badges before describing a live result."),
    ])
    detail_page(pdf, 4, "Evaluation and what the result means", "Use the numbers with their protocol and denominator; avoid treating an exposure metric as human satisfaction.", [
        ("E1  Metric calculation", "evaluation.ranking_metrics at 51-72 evaluates fixed top K=10: TCP is target-category item count divided by ten for positive requests; TCER is the same exposure fraction for mutes. Fill reports how many slots remain occupied. HR@1 and NDCG@10 compare against historical next-item relevance. User-level paired summaries average three fixed seeds; request-seed rows are not independent users."),
        ("Hand-worked top-ten count", "For an independently specified boost of category_1, six matching items among ten gives TCP=6/10=0.6 and fill=10/10=1. For a category_28 mute, two matches among ten gives TCER=2/10=0.2, a failure of full removal. Count the REQUESTED category even if a parser returns a different category; otherwise parsing errors disappear from the metric. E2's induced-movement/success measures use a separate reference and protocol."),
        ("Frozen Experiment 1", "Canonical rule and Llama rankings are identical, so E1 feed changes show shared category-policy enforcement, not an LLM-specific gain. TCP rose 11.6% to 79.2% and TCER fell 6.1% to zero under their assigned requests; boost NDCG@10 fell 45.7%. Broader synthetic parser accuracy was Llama 79/100 versus rules 81/100, below the proposal's 85% target."),
        ("Revised AI-reference Experiment 2 and separate student check", "The completed fresh AI-reference E2 reports whole-command agreement Llama 76/100 versus rules 11/100 and induced success 20.145% versus item-feedback 3.815%; NDCG was 0.02580 versus 0.03184 and conditional success was zero. References are model-generated. The separately dated student-label exposed-practice parser result is 73/100 versus 18/100; it is not the same fresh evaluation."),
        ("Validity boundary and professor's decision", "Offline TCP/TCER can verify exposure under an assigned category command. They do not establish that a person wanted that command, found the result useful, or remained satisfied. The original archived human-reference route was not executed; the revised AI-reference study is complete. A new independently specified human-intent protocol is a proposed next study only if the supervisor requests it."),
    ])
    pdf.save()
    print(OUTPUT)


if __name__ == "__main__":
    main()
