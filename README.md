# GAME-Orca-evaluator
We designed three Evaluators requesting H1 cell interaction matrices for Chr 8/9 (Orca test set) and Chr 10 (validation set). They tile chromosomes in 1Mb steps, extracting hg38 sequences at runtime. Evaluation computes Pearson correlations between predicted and measured Hi-C matrices. These modules also demonstrate msgpack-numpy response support.
