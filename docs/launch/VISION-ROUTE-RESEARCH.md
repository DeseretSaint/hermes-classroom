# Vision route research — who sees the frame, and what it costs

Question: is DeepSeek text-only, does a blind writer plus a vision manager beat a vision-native
writer, and which route should the one-handoff UI program use?

## 1. Capability: DeepSeek is not text-only

`deepseek/deepseek-v4.1-flash-1017` is a multimodal MoE: 552B total, 8B active prefill / 16B decode,
1M context, native image input. The provider metadata declares `modalities.input = ["text",
"image"]` and `attachment: true`; the official release says "native visual understanding"; NVIDIA's
model card says it "accepts text and images".

Its vision is not a bolt-on. The 1017 update reports:

| benchmark | DS-V4.1-Flash-1017 | Opus 5 |
|---|---|---|
| Chartography (w/tools) | 83.0 | 84.0 |
| BabyVision (w/tools) | 92.5 | 94.1 |
| ZeroBench-main (w/tools) | 51.0 | 52.0 |
| MMMU-Pro (base, 4-shot) | 56.5 | — |

Sources: https://www.deepseek.com/en/news/deepseek-v4-1-flash/,
https://build.nvidia.com/deepseek-ai/deepseek-v4.1-flash/modelcard,
https://huggingface.co/deepseek-ai/DeepSeek-V4.1-Flash-1017

The constraint is resolution, not modality: its vision configuration caps an image at **1,024
tokens** with a **minimum area of 295,936 px**. A full 1344×768 frame is 1,032,192 px, so it is
downsampled to the cap; fine type and 1 px rules vanish. Crops of roughly 600×600 or larger are the
unit of review.

## 2. Image economics

Claude estimates an image at `width × height / 750` tokens; 1344×768 is about **1,376 tokens**.
DeepSeek caps at **1,024 tokens**. At live Nous prices (per million tokens, input):

| model | input | output | per full frame | 100 frames |
|---|---|---|---|---|
| DeepSeek V4.1 Flash 1017 | $0.15 | $0.60 | $0.00015 | $0.015 |
| Qwen3-VL-235B | $0.21 | $1.90 | $0.00022 | $0.022 |
| Gemini 3.8 Flash | $0.825 | $4.125 | $0.00084 | $0.084 |
| Sonnet 5.5 | $2 | $10 | $0.00275 | $0.275 |
| Opus 5.5 | $4 | $20 | $0.00551 | $0.551 |
| Fable 5.2 | $8 | $40 | $0.01101 | $1.101 |

Images are not the cost driver. Context re-sends and round trips are.

Illustrative, 36 iterations (six screens × six passes), 12k context and one frame per iteration:

- vision-native DeepSeek writer: about **$0.11**
- Opus writer: about **$3.37**
- Opus as per-iteration oracle (30k context + frame + 1.2k output per call): about **$5.38**;
  **$1.09** with prompt caching

The oracle is 10–50× the cost of the vision-native lane, and it adds a lossy text hop and a
human-latency bottleneck.

## 3. What the evidence says about the loop

- **Self-correction needs sight.** DesignCoder's gain (+37.63% MSE, +9.52% CLIP, +12.82% SSIM) comes
  from a multimodal model seeing the rendered page and correcting it. A blind writer cannot run that
  loop. (https://arxiv.org/abs/2506.13663)
- **Structured state beats raw image feedback.** LiveWorkspace keeps a Target and a Current
  representation in the same schema (hierarchy, attributes, layout), computes a structured diff, and
  beats an image-level control at matched model-call counts: +1.8 on Design2Code, +2.0 on
  ScreenBench, 93% edit success over 100 edits. (https://arxiv.org/abs/2611.12112)
- **Automated visual feedback works.** UICoder filters and scores self-generated UI code with
  compilers and multimodal models; the resulting models approach proprietary quality.
  (https://arxiv.org/abs/2406.07739)
- **Segment-level review catches what whole-frame review misses.** DCGen's failure classes are
  element omission, distortion and misarrangement; segment-aware prompting buys up to 14% visual
  similarity. (https://arxiv.org/abs/2406.16386)
- **A VLM judge is not an oracle.** The best commercial judges score 62.4–62.5% on fine-grained
  visual preference; open models are near chance. Use them for region checks and use mechanical
  measurements for geometry. (https://vl-rewardbench.github.io/)
- **The strong model belongs at decision points, not in every loop.** The advisor pattern measured
  +2.7 points at 11.9% lower cost, and Haiku + Opus advisor doubled BrowseComp at 85% less cost than
  Sonnet. (https://claude.com/resources/articles/the-advisor-strategy)
- **Writes stay single-threaded.** Cognition's parallel-writer failure and Anthropic's warning about
  shared-context work both apply. (https://cognition.com/blog/dont-build-multi-agents,
  https://www.anthropic.com/research/multi-agent-research-system)

## 4. Routes compared

| route | quality | tokens | latency | failure mode |
|---|---|---|---|---|
| A. Vision-native writer + structured visual state + director at gates | high | lowest | lowest | writer's taste, capped by 1,024-token vision |
| B. Blind writer + director as per-iteration oracle | medium | 10–50× A | highest | lossy deltas, director bottleneck, context growth |
| C. Vision-native writer + cheap VLM critic in-loop + director at gates | medium-high | low | low | critic at ~62% fine-grained reliability |
| D. Premium vision writer (Sonnet/Fable) for the whole lane | high | 10–30× A | medium | cost, no added design judgement |

**Recommendation: A, with C's cheap critic for region presence checks only, and D as a one-pass
escalation for a screen that stalls below the rubric after two passes.** The director (Opus) sets the
spec, judges at milestones and owns the verdict; it is not the per-iteration eyes.

## 5. Consequences for the prompt

- The worker may see; do not build a manager-as-oracle loop.
- Give the worker a structured target/current diff and 600×600+ crops, not a paragraph.
- Use the critic for "is the fox present, is the tag in the right quadrant" and the DOM audit for
  "is it at 1088,526, 208×208".
- Reserve Opus for Gate 1, the mid-capture critique and the final verdict; Fable only as tie-break.
- Keep one writer per screen; the program is sequential, not a wave.
