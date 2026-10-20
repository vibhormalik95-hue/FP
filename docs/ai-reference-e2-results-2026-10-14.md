# Fresh synthetic-request Experiment Two results

On the fresh synthetic bank, validated whole-command agreement with model-generated references is 76/100 for Llama and 11/100 for rules. The other 24 Llama requests comprise 23 validation rejections and one accepted but incorrect command. All 23 rejections concern a condition that the request did not explicitly ground. The accepted mismatch reduced category_12 with floor 1 where the reference specified floor 0. Every request remains in the denominator.

User-averaged induced control success is 20.145% for Llama, 3.854% for rules and 3.815% for item feedback. NDCG@10 is 0.02580 for Llama versus 0.03184 for item feedback. Control and next-item ranking quality must be interpreted together.

Two passes using the same model family produced the reference labels and agreed on all 100 initial commands (Cohen kappa 1.000000). Both sets were saved before comparison. No model disagreement needed adjudication; this does not measure independent human accuracy.

The completed run retains 200 parser responses, 41,520 ranking rows, 3,460 assigned user/class requests and 2,595 full score vectors. It covers 865 users and three fixed recommender seeds. A separate calculation checked the saved results; its technical record states the scope and limitations.

Under this revision only, H1_AI is supported and H2_AI is supported by the prespecified directional tests with joint BH correction across 11 contrasts. H3_AI reports predictive quality descriptively. These decisions do not complete the archived human-reference design.

The earlier exposed-practice run at c6ebda06008c92e4141aa2d91991ac2c0328a1de scored 73/100 validated Llama commands, with induced control success 23.81% versus item feedback 3.92%, and NDCG@10 0.02461 versus 0.03128. It is separate from the fresh benchmark. No prompts, validators, thresholds or bands were tuned from either run.

Synthetic requests, opaque category IDs and a historical next-item proxy limit what the result says about human understanding or experience. A human study would need its own design.

The [current review files](../deliverables/2026-10-19/README-2026-10-19.md) contain the updated paper and presentation. Full E1 reproduction on Windows and Colab, and reconciliation of earlier score-file hashes, remain outstanding.
