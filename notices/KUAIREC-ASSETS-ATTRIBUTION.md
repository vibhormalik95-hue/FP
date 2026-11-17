# COMP 9500 KuaiRec assets: attribution and licence

These files let the COMP 9500 Feed Control Lab run on real KuaiRec data. They are derived from KuaiRec.

**Source:** Chongming Gao, Shijun Li, Wenqiang Lei, Jiawei Chen, Biao Li, Peng Jiang, Xiangnan He, Jiaxin Mao and Tat-Seng Chua. *KuaiRec: A Fully-Observed Dataset and Insights for Evaluating Recommender Systems.* CIKM 2022, 540–550. https://doi.org/10.1145/3511808.3557220. Repository: https://github.com/chongminggao/KuaiRec. Release used: https://doi.org/10.5281/zenodo.18164998.

**Licence:** CC BY-SA 4.0, the licence named by the KuaiRec repository and by the `LICENSE` file inside `KuaiRec.zip` (the Zenodo metadata says CC BY 4.0; the stricter notice is kept). Full text: https://creativecommons.org/licenses/by-sa/4.0/legalcode, also in `notices/KuaiRec-LICENSE.txt` of the repository and as `LICENSE-CC-BY-SA-4.0.txt` inside the release archive. These adapted files are shared under CC BY-SA 4.0.

**Changes made (adapted material):**
- `data/raw/kuairec_caption_category.csv`: the official KuaiRec caption and category table, unchanged.
- `data/processed.json`: a research subset of `small_matrix.csv` (865 users, 2,593 items): rows without timestamps excluded, positives defined as watch_ratio > 2, global time splits, opaque category IDs `category_N` from the official item features. Its `metadata` block records every step.
- `data/kuairec_gloss_en.json`: an English machine translation (gpt-5-mini) of the captions, cover texts, tags and category names (input of the English text layer).
- `data/kuairec_text_en-v1.json` (release `comp9500-kuairec-english-v1`, SHA-256 `034f5ac96375175d4bb8c16c7a8aa934ea9b1035e3920c74fe2ddc5ddde1c207`): the English text layer that the application loads, machine translation of KuaiRec (CC BY-SA 4.0), built from the gloss with the remaining Chinese hashtags translated by gpt-5-mini. `data/kuairec_text_en-v1.label-map.json` (same release) maps each original KuaiRec label to its English label; only the evaluation reads it.
- `results/models/seed_{42,43,44}/model.pt`: SASRec-style recommenders trained on `processed.json` (three seeds), with their training metadata.

No warranty. These files are not endorsed by the KuaiRec authors.
