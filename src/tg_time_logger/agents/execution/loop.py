from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from tg_time_logger.agents.execution.config import ModelConfig, get_int, get_tier_order
from tg_time_logger.agents.execution.llm_client import LlmResponse, call_openrouter, parse_json_object
from tg_time_logger.agents.tools.base import ToolContext
from tg_time_logger.agents.tools.registry import ToolRegistry


@dataclass(frozen=True)
class AgentRequest:
    question: str
    context_text: str
    directive_text: str
    requested_tier: str | None
    allow_tier_escalation: bool


@dataclass(frozen=True)
class AgentRunResult:
    answer: str
    model_used: str
    steps: list[dict[str, Any]]
    prompt_tokens: int
    completion_tokens: int
    status: str


class AgentLoop:
    def __init__(
        self,
        model_config: ModelConfig,
        api_key: str | None,
        registry: ToolRegistry,
        app_config: dict[str, Any],
    ) -> None:
        self.model_config = model_config
        self.api_key = api_key
        self.registry = registry
        self.app_config = app_config

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        return max(1, len(text) // 4)

    @staticmethod
    def _is_json_primitive(value: Any) -> bool:
        return value is None or isinstance(value, (str, int, float, bool))

    def _validate_action(self, payload: dict[str, Any]) -> tuple[str, dict[str, Any]] | tuple[None, str]:
        action = str(payload.get("action", "")).strip().lower()
        if action == "answer":
            answer = payload.get("answer")
            if isinstance(answer, str) and answer.strip():
                return "answer", {"answer": answer.strip()}
            return None, "Invalid answer action: missing non-empty 'answer' string."

        if action == "tool":
            tool = str(payload.get("tool", "")).strip()
            args = payload.get("args", {})
            if not tool:
                return None, "Invalid tool action: missing 'tool' name."
            if self.registry.get(tool) is None:
                return None, f"Invalid tool action: unknown tool '{tool}'."
            if not isinstance(args, dict):
                return None, "Invalid tool action: 'args' must be an object."
            sanitized_args: dict[str, Any] = {}
            for key, value in args.items():
                if not isinstance(key, str):
                    continue
                if self._is_json_primitive(value):
                    sanitized_args[key] = value
            return "tool", {"tool": tool, "args": sanitized_args}

        return None, f"Invalid action '{action}'. Expected 'answer' or 'tool'."

    def _call_models(
        self,
        messages: list[dict[str, str]],
        requested_tier: str | None,
        allow_tier_escalation: bool,
        max_tokens: int,
    ) -> LlmResponse | None:
        if not self.api_key:
            return None
        reasoning_enabled = bool(self.app_config.get("agent.reasoning_enabled", True))
        tier_order = get_tier_order(self.model_config, requested_tier, allow_tier_escalation)
        for tier_name in tier_order:
            tier = self.model_config.get_tier(tier_name)
            if not tier:
                continue
            for model in tier.models:
                if model.provider != "openrouter":
                    continue
                res = call_openrouter(
                    model=model,
                    messages=messages,
                    api_key=self.api_key,
                    max_tokens=max_tokens,
                    reasoning_enabled=reasoning_enabled,
                )
                if res:
                    return res
        return None

    def run(self, req: AgentRequest, ctx: ToolContext) -> AgentRunResult:
        max_steps = get_int(self.app_config, "agent.max_steps", default=6, min_value=1)
        max_tool_calls = get_int(self.app_config, "agent.max_tool_calls", default=4, min_value=0)
        max_step_input_tokens = get_int(self.app_config, "agent.max_step_input_tokens", default=1800, min_value=100)
        max_step_output_tokens = get_int(self.app_config, "agent.max_step_output_tokens", default=420, min_value=64)
        max_total_tokens = get_int(self.app_config, "agent.max_total_tokens", default=6000, min_value=512)
        tool_calls = 0
        steps: list[dict[str, Any]] = []
        observations: list[str] = []
        used_signatures: set[str] = set()
        total_prompt_tokens = 0
        total_completion_tokens = 0

        for _ in range(max_steps):
            tools_json = self.registry.list_specs()
            obs_text = "\n".join(observations[-6:]) if observations else "None yet."
            prompt = (
                f"{req.directive_text}\n\n"
                "You are in an agent loop. Return JSON only with one schema:\n"
                "{\"action\":\"answer\",\"answer\":\"...\"}\n"
                "or\n"
                "{\"action\":\"tool\",\"tool\":\"tool_name\",\"args\":{...},\"reason\":\"...\"}\n\n"
                "Tool list:\n"
                f"{tools_json}\n\n"
                f"User question:\n{req.question}\n\n"
                f"Known context:\n{req.context_text}\n\n"
                f"Observations so far:\n{obs_text}\n"
            )
            messages = [
                {"role": "system", "content": "Return strict JSON only. No markdown."},
                {"role": "user", "content": prompt},
            ]
            step_prompt_tokens = sum(self._estimate_tokens(m.get("content", "")) for m in messages)
            if step_prompt_tokens > max_step_input_tokens:
                steps.append(
                    {
                        "type": "budget_blocked",
                        "reason": "step_input_tokens_exceeded",
                        "value": step_prompt_tokens,
                        "limit": max_step_input_tokens,
                    }
                )
                return AgentRunResult(
                    answer="Agent request is too large for current step budget. Try a shorter question.",
                    model_used="none",
                    steps=steps,
                    prompt_tokens=total_prompt_tokens,
                    completion_tokens=total_completion_tokens,
                    status="budget_blocked",
                )

            remaining_total = max_total_tokens - (total_prompt_tokens + total_completion_tokens)
            if remaining_total <= 64:
                steps.append(
                    {
                        "type": "budget_blocked",
                        "reason": "total_tokens_exceeded",
                        "value": total_prompt_tokens + total_completion_tokens,
                        "limit": max_total_tokens,
                    }
                )
                return AgentRunResult(
                    answer="Agent token budget exhausted for this request. Please ask a narrower question.",
                    model_used="none",
                    steps=steps,
                    prompt_tokens=total_prompt_tokens,
                    completion_tokens=total_completion_tokens,
                    status="budget_blocked",
                )

            output_budget = min(max_step_output_tokens, remaining_total)
            llm = self._call_models(
                messages,
                req.requested_tier,
                req.allow_tier_escalation,
                max_tokens=output_budget,
            )
            total_prompt_tokens += step_prompt_tokens
            if not llm:
                return AgentRunResult(
                    answer="Agent is unavailable right now (model call failed).",
                    model_used="none",
                    steps=steps,
                    prompt_tokens=total_prompt_tokens,
                    completion_tokens=total_completion_tokens,
                    status="model_unavailable",
                )
            total_completion_tokens += self._estimate_tokens(llm.text)

            parsed = parse_json_object(llm.text)
            if not parsed:
                steps.append({"type": "parse_error", "model": llm.model_id, "raw": llm.text[:280]})
                observations.append("Model response was not valid JSON.")
                continue

            validated = self._validate_action(parsed)
            if validated[0] is None:
                err = str(validated[1])
                steps.append({"type": "schema_error", "model": llm.model_id, "error": err})
                observations.append(err)
                continue

            action = str(validated[0])
            payload = validated[1]
            if action == "answer":
                answer = str(payload["answer"]).strip()
                steps.append({"type": "answer", "model": llm.model_id})
                return AgentRunResult(
                    answer=answer,
                    model_used=llm.model_id,
                    steps=steps,
                    prompt_tokens=total_prompt_tokens,
                    completion_tokens=total_completion_tokens,
                    status="ok",
                )

            if action == "tool":
                if tool_calls >= max_tool_calls:
                    observations.append("Tool call budget exhausted.")
                    continue
                tool_name = str(payload["tool"])
                args = dict(payload["args"])
                signature = f"{tool_name}:{args}"
                if signature in used_signatures:
                    observations.append(f"Skipping duplicate tool call: {tool_name}.")
                    continue
                used_signatures.add(signature)
                result = self.registry.run(tool_name, args, ctx)
                tool_calls += 1
                steps.append(
                    {
                        "type": "tool",
                        "model": llm.model_id,
                        "tool": tool_name,
                        "ok": result.ok,
                        "metadata": result.metadata,
                    }
                )
                observations.append(
                    f"Tool {tool_name} ({'ok' if result.ok else 'fail'}): {result.content[:1200]}"
                )
                continue

            observations.append(f"Unknown action '{action}'.")

        fallback_messages = [
            {"role": "system", "content": "Give a concise, practical answer using context and observations."},
            {
                "role": "user",
                "content": (
                    f"Question: {req.question}\n\n"
                    f"Context:\n{req.context_text}\n\n"
                    f"Observations:\n{chr(10).join(observations[-8:])}"
                ),
            },
        ]
        fallback_prompt_tokens = sum(self._estimate_tokens(m.get("content", "")) for m in fallback_messages)
        if fallback_prompt_tokens > max_step_input_tokens:
            return AgentRunResult(
                answer="I could not finish the request within current budgets. Try a shorter question.",
                model_used="none",
                steps=steps,
                prompt_tokens=total_prompt_tokens,
                completion_tokens=total_completion_tokens,
                status="budget_blocked",
            )
        total_prompt_tokens += fallback_prompt_tokens
        remaining_total = max_total_tokens - (total_prompt_tokens + total_completion_tokens)
        if remaining_total <= 64:
            return AgentRunResult(
                answer="I could not finish the request within total token budget. Try a narrower question.",
                model_used="none",
                steps=steps,
                prompt_tokens=total_prompt_tokens,
                completion_tokens=total_completion_tokens,
                status="budget_blocked",
            )
        final = self._call_models(
            fallback_messages,
            req.requested_tier,
            req.allow_tier_escalation,
            max_tokens=min(max_step_output_tokens, remaining_total),
        )
        if final and final.text.strip():
            total_completion_tokens += self._estimate_tokens(final.text)
            steps.append({"type": "fallback_answer", "model": final.model_id})
            return AgentRunResult(
                answer=final.text.strip(),
                model_used=final.model_id,
                steps=steps,
                prompt_tokens=total_prompt_tokens,
                completion_tokens=total_completion_tokens,
                status="fallback",
            )

        return AgentRunResult(
            answer="I could not produce a reliable answer right now.",
            model_used="none",
            steps=steps,
            prompt_tokens=total_prompt_tokens,
            completion_tokens=total_completion_tokens,
            status="failed",
        )
