# OPENROUTER_MODELS.md

Updated: 2026-02 (prices/context windows can change; verify on the linked model pages).

## 5 free models (good for quick prototyping)

| Model ID (use in API) | Publisher | Context | Price (input / output) | Best for | Notes |
|---|---|---:|---:|---|---|
| `openrouter/free` | OpenRouter | 200k | $0 / $0 | “Just works” free routing | Imagine a “free pool” router; it picks a compatible free model automatically. |
| `arcee-ai/trinity-large-preview:free` | Arcee | 131k | $0 / $0 | Long-context chat + agent prompts | Frontier-scale open-weight MoE; strong on creative + toolchain prompts. |
| `openrouter/pony-alpha` | OpenRouter | 200k | $0 / $0 | Coding + agentic workflows | Provider logs prompts/completions for improvement. |
| `stepfun/step-3.5-flash:free` | StepFun | 256k | $0 / $0 | Fast reasoning at long context | MoE; designed for speed-efficient reasoning. |
| `tngtech/deepseek-r1t2-chimera:free` | TNG Tech | 163.8k | $0 / $0 | Reasoning-heavy tasks | Assembly/merge of DeepSeek checkpoints; good cost-to-intelligence (free). |

## 10 “top” models (excluding GPT / Claude / Gemini families)

Selection bias: aimed at strong capability *and* broad usefulness (reasoning/coding/agents), not a strict leaderboard.

| Model ID (use in API) | Publisher | Context | Price (input / output) | Best for | Notes |
|---|---|---:|---:|---|---|
| `deepseek/deepseek-v3.2` | DeepSeek | 163.8k | $0.25 / $0.38 | Reasoning + agents at low cost | Reasoning can be toggled via `reasoning.enabled`. |
| `moonshotai/kimi-k2.5` | MoonshotAI | 262.1k | $0.45 / $2.25 | Multimodal + “agent swarm” style workflows | Strong visual coding + tool-calling; higher output cost. |
| `qwen/qwen3-coder-next` | Qwen | 262.1k | $0.07 / $0.30 | Coding agents | Non-thinking mode only (no `<think>`), simpler integration. |
| `z-ai/glm-4.7` | Z.AI | 202.8k | $0.40 / $1.50 | General reasoning + agent execution | Flagship GLM; strong multi-step execution stability. |
| `minimax/minimax-m2.1` | MiniMax | 196.6k | $0.27 / $0.95 | Coding + agentic workflows (fast/cheap) | 10B activated parameters; tuned for low latency. |
| `meta-llama/llama-4-maverick` | Meta | 1,048,576 | $0.15 / $0.60 | Multimodal + huge context | Image+text input; 1M token window. |
| `mistralai/mistral-large-2512` | Mistral AI | 262.1k | $0.50 / $1.50 | General “frontier” quality | Apache 2.0 licensed; MoE (41B active). |
| `deepseek/deepseek-r1` | DeepSeek | 64k | $0.70 / $2.50 | Deep reasoning | Open-sourced with open reasoning tokens; higher cost than V3.2. |
| `x-ai/grok-4.1-fast` | xAI | 2,000,000 | $0.20 / $0.50 (+ optional web search) | Tool calling + deep research | Reasoning can be toggled via `reasoning.enabled`; very large context. |
| `qwen/qwen3-235b-a22b` | Qwen | 131k | $0.22 / $0.88 | Strong reasoning + multilingual | Has thinking + non-thinking modes; agent tool calling. |

## 2 “GPT-5-mini-like” picks (cheap, fast, good enough for many tasks)

| Model ID | Why it’s “mini-like” | Context | Price (input / output) |
|---|---|---:|---:|
| `z-ai/glm-4.7-flash` | Very low input cost; optimized for agentic coding and planning | 202.8k | $0.06 / $0.40 |
| `mistralai/mistral-small-24b-instruct-2501` | Low latency, low cost, solid general capability | 32.8k | $0.05 / $0.08 |

## Quick usage note (OpenRouter is OpenAI-compatible)

- Endpoint: `https://openrouter.ai/api/v1/chat/completions`
- Put the model ID in `model`.
- Pricing is per **1M tokens** (input/output listed separately).

Example (pseudo):
- model: `moonshotai/kimi-k2.5`
- model: `deepseek/deepseek-v3.2`
