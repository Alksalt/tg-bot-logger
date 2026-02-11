# MODELS.md — OpenRouter “best” models (30–35) with correct names + pricing + what they’re for (Feb 2026)

**Legend**
- **OpenRouter ID** = the model slug you put in `model: "..."` when calling OpenRouter.
- **Direct alternative** = the closest “same vendor / same family” option when calling the vendor directly (or self-hosting).
- **Prices** are **USD per 1M tokens** (input / output) unless noted.

---

## A) Frontier / flagship (closed-source, best quality)

1) **OpenAI — GPT-5.2 Pro**  
- OpenRouter ID: `openai/gpt-5.2-pro`  [oai_citation:0‡OpenRouter](https://openrouter.ai/openai/gpt-5.2-pro)  
- Price (OR): **$21 / $168**  [oai_citation:1‡OpenRouter](https://openrouter.ai/openai/gpt-5.2-pro)  
- For: hardest reasoning, long-context, high-stakes agentic work.

2) **Anthropic — Claude Opus 4.6**  
- OpenRouter ID: `anthropic/claude-opus-4.6`  [oai_citation:2‡OpenRouter](https://openrouter.ai/anthropic/claude-opus-4.6)  
- Price (OR): **from $5 / $25**  [oai_citation:3‡OpenRouter](https://openrouter.ai/anthropic/claude-opus-4.6)  
- For: large codebases, long-running agents, complex professional tasks.

3) **Google — Gemini 3 Pro Preview**  
- OpenRouter ID: `google/gemini-3-pro-preview`  [oai_citation:4‡OpenRouter](https://openrouter.ai/google/gemini-3-pro-preview)  
- Price (OR): **from $2 / $12** (text), **$2 audio**  [oai_citation:5‡OpenRouter](https://openrouter.ai/google/gemini-3-pro-preview)  
- For: top-tier multimodal reasoning + long context.

4) **OpenAI — GPT-5.2 (base flagship)**  
- OpenRouter ID: `openai/gpt-5.2`  [oai_citation:6‡OpenRouter](https://openrouter.ai/openai/gpt-5.2?utm_source=chatgpt.com)  
- Price (OR): **$1.75 / $14**  [oai_citation:7‡OpenRouter](https://openrouter.ai/openai/gpt-5.2?utm_source=chatgpt.com)  
- For: strong general-purpose frontier model at far lower cost than Pro.

---

## B) Best “coding / dev” picks

5) **OpenAI — GPT-5.2-Codex**  
- OpenRouter ID: `openai/gpt-5.2-codex`  [oai_citation:8‡OpenRouter](https://openrouter.ai/openai/gpt-5.2-codex)  
- Price (OR): **$1.75 / $14**  [oai_citation:9‡OpenRouter](https://openrouter.ai/openai/gpt-5.2-codex)  
- For: feature work, refactors, debugging, code review (Codex-tuned).

6) **Anthropic — Claude Sonnet 4.5**  
- OpenRouter ID: `anthropic/claude-sonnet-4.5`  [oai_citation:10‡OpenRouter](https://openrouter.ai/anthropic/claude-sonnet-4.5)  
- Price (OR): **from $3 / $15**  [oai_citation:11‡OpenRouter](https://openrouter.ai/anthropic/claude-sonnet-4.5)  
- For: real-world agents + coding workflows (excellent reliability).

7) **Mistral — Codestral 2508**  
- OpenRouter ID: `mistralai/codestral-2508`  [oai_citation:12‡OpenRouter](https://openrouter.ai/mistralai/codestral-2508)  
- Price (OR): **$0.30 / $0.90**  [oai_citation:13‡OpenRouter](https://openrouter.ai/mistralai/codestral-2508)  
- For: low-latency coding (FIM, fixes, tests).

---

## C) Fast + good value (closed-source)

8) **Google — Gemini 3 Flash Preview**  
- OpenRouter ID: `google/gemini-3-flash-preview`  [oai_citation:14‡OpenRouter](https://openrouter.ai/google/gemini-3-flash-preview)  
- Price (OR): **$0.50 / $3** (text), **$1 audio**  [oai_citation:15‡OpenRouter](https://openrouter.ai/google/gemini-3-flash-preview)  
- For: agent loops + tool use, strong reasoning at lower latency.

9) **Amazon — Nova Premier 1.0**  
- OpenRouter ID: `amazon/nova-premier-v1`  [oai_citation:16‡OpenRouter](https://openrouter.ai/amazon/nova-premier-v1?utm_source=chatgpt.com)  
- Price (OR): **$2.50 / $12.50**  [oai_citation:17‡OpenRouter](https://openrouter.ai/amazon/nova-premier-v1?utm_source=chatgpt.com)  
- For: multimodal reasoning; also “teacher” model for distillation.

10) **xAI — Grok 4 Fast**  
- OpenRouter ID: `x-ai/grok-4-fast`  [oai_citation:18‡OpenRouter](https://openrouter.ai/x-ai/grok-4-fast?utm_source=chatgpt.com)  
- Price (OR): **from $0.20 / $0.50**  [oai_citation:19‡OpenRouter](https://openrouter.ai/x-ai/grok-4-fast?utm_source=chatgpt.com)  
- For: cost-efficient, huge context (2M), multimodal + tool calling.

11) **xAI — Grok 4.1 Fast**  
- OpenRouter ID: `x-ai/grok-4.1-fast`  [oai_citation:20‡OpenRouter](https://openrouter.ai/x-ai/grok-4.1-fast?utm_source=chatgpt.com)  
- Price (OR): **from $0.20 / $0.50**  [oai_citation:21‡OpenRouter](https://openrouter.ai/x-ai/grok-4.1-fast?utm_source=chatgpt.com)  
- For: tool-calling agents, customer support, “deep research” workflows.

---

## D) “Mini models” (cheap, fast)

12) **OpenAI — GPT-5 Mini**  
- OpenRouter ID: `openai/gpt-5-mini`  [oai_citation:22‡OpenRouter](https://openrouter.ai/openai/gpt-5-mini?utm_source=chatgpt.com)  
- Price (OR): **$0.25 / $2**  [oai_citation:23‡OpenRouter](https://openrouter.ai/openai/gpt-5-mini?utm_source=chatgpt.com)  
- For: general chat + light reasoning, low-latency.

13) **OpenAI — GPT-5 Nano**  
- OpenRouter ID: `openai/gpt-5-nano`  [oai_citation:24‡OpenRouter](https://openrouter.ai/openai/gpt-5-nano?utm_source=chatgpt.com)  
- Price (OR): **$0.05 / $0.40**  [oai_citation:25‡OpenRouter](https://openrouter.ai/openai/gpt-5-nano?utm_source=chatgpt.com)  
- For: high-volume simple tasks (classification, extraction, short replies).

14) **Anthropic — Claude Haiku 4.5**  
- OpenRouter ID: `anthropic/claude-haiku-4.5`  [oai_citation:26‡OpenRouter](https://openrouter.ai/anthropic/claude-haiku-4.5?utm_source=chatgpt.com)  
- Price (OR): **$1 / $5**  [oai_citation:27‡OpenRouter](https://openrouter.ai/anthropic/claude-haiku-4.5?utm_source=chatgpt.com)  
- For: fast “near-frontier” utility model.

---

## E) Top open-source / open-weights (best overall OSS stack)

15) **DeepSeek — R1**  
- OpenRouter ID: `deepseek/deepseek-r1`  [oai_citation:28‡OpenRouter](https://openrouter.ai/deepseek/deepseek-r1?utm_source=chatgpt.com)  
- Price (OR): **$0.70 / $2.50**  [oai_citation:29‡OpenRouter](https://openrouter.ai/deepseek/deepseek-r1?utm_source=chatgpt.com)  
- Direct alternative: self-host DeepSeek-R1 weights (vLLM/TGI)  
- For: strong reasoning (open), research/analysis, math, coding.

16) **Qwen — Qwen3 Max Thinking**  
- OpenRouter ID: `qwen/qwen3-max-thinking`  [oai_citation:30‡OpenRouter](https://openrouter.ai/qwen/qwen3-max-thinking)  
- Price (OR): **from $1.20 / $6**  [oai_citation:31‡OpenRouter](https://openrouter.ai/qwen/qwen3-max-thinking)  
- Direct alternative: self-host Qwen3 Max Thinking weights  
- For: “deep thinking” OSS reasoning + agent behavior.

17) **Qwen — Qwen3 Max**  
- OpenRouter ID: `qwen/qwen3-max`  [oai_citation:32‡OpenRouter](https://openrouter.ai/qwen/qwen3-max)  
- Price (OR): **from $1.20 / $6**  [oai_citation:33‡OpenRouter](https://openrouter.ai/qwen/qwen3-max)  
- Direct alternative: self-host Qwen3 Max weights  
- For: strong general OSS model (no dedicated thinking mode).

18) **Meta — Llama 3.3 70B Instruct**  
- OpenRouter ID: `meta-llama/llama-3.3-70b-instruct`  [oai_citation:34‡OpenRouter](https://openrouter.ai/meta-llama/llama-3.3-70b-instruct?utm_source=chatgpt.com)  
- Price (OR): **$0.10 / $0.32**  [oai_citation:35‡OpenRouter](https://openrouter.ai/meta-llama/llama-3.3-70b-instruct?utm_source=chatgpt.com)  
- Direct alternative: self-host Llama 3.3 70B weights  
- For: multilingual chat + solid baseline reasoning.

19) **Meta — Llama 3.3 70B Instruct (free)**  
- OpenRouter ID: `meta-llama/llama-3.3-70b-instruct:free`  [oai_citation:36‡OpenRouter](https://openrouter.ai/meta-llama/llama-3.3-70b-instruct%3Afree?utm_source=chatgpt.com)  
- Price (OR): **$0 / $0**  [oai_citation:37‡OpenRouter](https://openrouter.ai/meta-llama/llama-3.3-70b-instruct%3Afree?utm_source=chatgpt.com)  
- For: “good enough” free tier testing/prototyping.

---

## F) Strong “budget coding” OSS / community picks

20) **OpenRouter — Aurora Alpha (free)**  
- OpenRouter ID: `openrouter/aurora-alpha`  [oai_citation:38‡OpenRouter](https://openrouter.ai/openrouter/aurora-alpha?utm_source=chatgpt.com)  
- Price (OR): **$0 / $0**  [oai_citation:39‡OpenRouter](https://openrouter.ai/openrouter/aurora-alpha?utm_source=chatgpt.com)  
- For: fast reasoning/coding assistant experimentation.

21) **Cohere — Command R+ (08-2024)**  
- OpenRouter ID: `cohere/command-r-plus-08-2024`  [oai_citation:40‡OpenRouter](https://openrouter.ai/cohere/command-r-plus-08-2024?utm_source=chatgpt.com)  
- Price (OR): **$2.50 / $10**  [oai_citation:41‡OpenRouter](https://openrouter.ai/cohere/command-r-plus-08-2024?utm_source=chatgpt.com)  
- Direct alternative: Cohere API “Command R+”  
- For: RAG + tool use in enterprise-ish pipelines.

---

## G) Multimodal / image generation & editing (practical)

22) **OpenAI — GPT-5 Image Mini**  
- OpenRouter ID: `openai/gpt-5-image-mini`  [oai_citation:42‡OpenRouter](https://openrouter.ai/openai/gpt-5-image-mini)  
- Price (OR): **$2.50 / $2** (plus image token pricing shown on OR page)  [oai_citation:43‡OpenRouter](https://openrouter.ai/openai/gpt-5-image-mini)  
- For: image generation + edits with strong instruction following.

23) **Google — Gemini 3 Pro Image Preview (Nano Banana Pro)**  
- OpenRouter ID: `google/gemini-3-pro-image-preview`  [oai_citation:44‡OpenRouter](https://openrouter.ai/google/gemini-3-pro-image-preview)  
- Price (OR): **$2 / $12** (text), **$2 audio**  [oai_citation:45‡OpenRouter](https://openrouter.ai/google/gemini-3-pro-image-preview)  
- For: high-end image generation/editing + great text-in-image rendering.

---

## H) “Direct vs OpenRouter” naming cheat (corporate models)

> For each corporate model below, you get: **(1) OpenRouter slug** and **(2) Direct vendor option**.

24) OpenAI flagship reasoning  
- OpenRouter: `openai/gpt-5.2-pro`  [oai_citation:46‡OpenRouter](https://openrouter.ai/openai/gpt-5.2-pro)  
- Direct: OpenAI API “GPT-5.2 Pro” (same family name)

25) OpenAI flagship general  
- OpenRouter: `openai/gpt-5.2`  [oai_citation:47‡OpenRouter](https://openrouter.ai/openai/gpt-5.2?utm_source=chatgpt.com)  
- Direct: OpenAI API “GPT-5.2”

26) OpenAI coding  
- OpenRouter: `openai/gpt-5.2-codex`  [oai_citation:48‡OpenRouter](https://openrouter.ai/openai/gpt-5.2-codex)  
- Direct: OpenAI API “GPT-5.2 Codex”

27) OpenAI mini  
- OpenRouter: `openai/gpt-5-mini`  [oai_citation:49‡OpenRouter](https://openrouter.ai/openai/gpt-5-mini?utm_source=chatgpt.com)  
- Direct: OpenAI API “GPT-5 Mini”

28) OpenAI nano  
- OpenRouter: `openai/gpt-5-nano`  [oai_citation:50‡OpenRouter](https://openrouter.ai/openai/gpt-5-nano?utm_source=chatgpt.com)  
- Direct: OpenAI API “GPT-5 Nano”

29) Anthropic best  
- OpenRouter: `anthropic/claude-opus-4.6`  [oai_citation:51‡OpenRouter](https://openrouter.ai/anthropic/claude-opus-4.6)  
- Direct: Anthropic Claude API “Claude Opus 4.6” (pricing page for Claude family)  [oai_citation:52‡Claude](https://platform.claude.com/docs/en/about-claude/pricing?utm_source=chatgpt.com)

30) Anthropic mid-tier  
- OpenRouter: `anthropic/claude-sonnet-4.5`  [oai_citation:53‡OpenRouter](https://openrouter.ai/anthropic/claude-sonnet-4.5)  
- Direct: Anthropic Claude API “Claude Sonnet 4.5” (pricing page for Claude family)  [oai_citation:54‡Claude](https://platform.claude.com/docs/en/about-claude/pricing?utm_source=chatgpt.com)

31) Anthropic fast tier  
- OpenRouter: `anthropic/claude-haiku-4.5`  [oai_citation:55‡OpenRouter](https://openrouter.ai/anthropic/claude-haiku-4.5?utm_source=chatgpt.com)  
- Direct: Anthropic Claude API “Claude Haiku 4.5”  [oai_citation:56‡Claude](https://platform.claude.com/docs/en/about-claude/pricing?utm_source=chatgpt.com)

32) Google flagship  
- OpenRouter: `google/gemini-3-pro-preview`  [oai_citation:57‡OpenRouter](https://openrouter.ai/google/gemini-3-pro-preview)  
- Direct: Google Gemini API “Gemini 3 Pro Preview” (see Gemini pricing)  [oai_citation:58‡Google AI for Developers](https://ai.google.dev/gemini-api/docs/pricing?utm_source=chatgpt.com)

33) Google fast tier  
- OpenRouter: `google/gemini-3-flash-preview`  [oai_citation:59‡OpenRouter](https://openrouter.ai/google/gemini-3-flash-preview)  
- Direct: Google Gemini API “Gemini 3 Flash Preview” (see Gemini pricing)  [oai_citation:60‡Google AI for Developers](https://ai.google.dev/gemini-api/docs/pricing?utm_source=chatgpt.com)

34) Mistral coding  
- OpenRouter: `mistralai/codestral-2508`  [oai_citation:61‡OpenRouter](https://openrouter.ai/mistralai/codestral-2508)  
- Direct: Mistral API “Codestral 2508”

35) Amazon multimodal  
- OpenRouter: `amazon/nova-premier-v1`  [oai_citation:62‡OpenRouter](https://openrouter.ai/amazon/nova-premier-v1?utm_source=chatgpt.com)  
- Direct: AWS (Bedrock) “Nova Premier 1.0”

---

## I) Quick recommendations (pick-by-job)

- **Best overall quality (money no object):** `openai/gpt-5.2-pro`  [oai_citation:63‡OpenRouter](https://openrouter.ai/openai/gpt-5.2-pro)  
- **Best coding agent:** `anthropic/claude-opus-4.6` or `openai/gpt-5.2-codex`  [oai_citation:64‡OpenRouter](https://openrouter.ai/anthropic/claude-opus-4.6)  
- **Best value for agentic workflows:** `google/gemini-3-flash-preview`  [oai_citation:65‡OpenRouter](https://openrouter.ai/google/gemini-3-flash-preview)  
- **Best cheap “do everything”:** `openai/gpt-5-mini`  [oai_citation:66‡OpenRouter](https://openrouter.ai/openai/gpt-5-mini?utm_source=chatgpt.com)  
- **Best ultra-cheap:** `openai/gpt-5-nano`  [oai_citation:67‡OpenRouter](https://openrouter.ai/openai/gpt-5-nano?utm_source=chatgpt.com)  
- **Best open-source reasoning:** `deepseek/deepseek-r1` or `qwen/qwen3-max-thinking`  [oai_citation:68‡OpenRouter](https://openrouter.ai/deepseek/deepseek-r1?utm_source=chatgpt.com)  
- **Best image gen/edit:** `openai/gpt-5-image-mini` or `google/gemini-3-pro-image-preview`  [oai_citation:69‡OpenRouter](https://openrouter.ai/openai/gpt-5-image-mini)

---