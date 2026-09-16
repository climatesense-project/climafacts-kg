# ruff: noqa: E501
"""LLM-based CARDS classifier: output schema, provider helpers, and CARDSLLMClassifier."""

import asyncio
import dataclasses
import logging
import os
import random
import re
from typing import Optional

from pydantic import BaseModel, Field, field_validator, model_validator
from pydantic_ai import Agent, PromptedOutput
from pydantic_ai.exceptions import ModelHTTPError

from climafactskg.utils import hash_string

from ..base import CARDSClassifierBase
from ..cache import ClassificationCache
from .presets import (
    _REGISTRY,
    CARDS_LLM_DEFAULT_MODEL,
    CARDS_LLM_DEFAULT_PROVIDER,
    CARDS_LLM_DEFAULT_SYSTEM_PROMPT,
    CARDS_LLM_DEFAULT_SYSTEM_PROMPT_WITH_CONTEXT,
    CARDS_LLM_DEFAULT_USER_PROMPT,
    CARDS_LLM_DEFAULT_USER_PROMPT_WITH_CONTEXT,
    TaxonomyCode,
    registered_presets,
)

logger = logging.getLogger(__name__)

# HTTP status codes worth retrying: rate limits, timeouts, and transient upstream
# errors. OpenRouter in particular falls back across multiple backend providers for
# a single model, and a busy backend can surface as a 400 ("invalid request params")
# even though the actual cause is upstream rate-limiting on other providers in the
# fallback chain — so 400 is included here too.
_RETRYABLE_STATUS_CODES = {400, 408, 429, 500, 502, 503, 504}
_DEFAULT_MAX_RETRIES = 3
_DEFAULT_RETRY_BASE_DELAY = 1.0


# ---------------------------------------------------------------------------
# Output schema
# ---------------------------------------------------------------------------


class CARDSOutput(BaseModel):
    """Structured output from the LLM classifier.

    Attributes:
        is_climate_related: True if the text is related to climate change.
        cards_category: The single most relevant CARDS taxonomy code, or None.
        reasoning: Optional chain-of-thought explanation of the classification.
    """

    @model_validator(mode="before")
    @classmethod
    def unwrap_tool_envelope(cls, data: object) -> object:
        """Unwrap pydantic-ai's final_result tool envelope emitted as plain text.

        Qwen3 in thinking mode sometimes returns the structured output as a text
        JSON blob shaped like {"name": "final_result", "arguments": {...}} rather
        than as a proper tool call. Strip the wrapper so validation sees the fields.
        """
        if isinstance(data, dict) and data.get("name") == "final_result" and "arguments" in data:
            return data["arguments"]
        return data

    is_climate_related: bool = Field(
        description="True if the text is related to climate change, False otherwise.",
    )

    @field_validator("is_climate_related", mode="before")
    @classmethod
    def coerce_bool(cls, v: object) -> bool:
        """Coerces 0/1 integers or 'true'/'false' strings to Python bool."""
        if isinstance(v, str):
            return v.strip().lower() not in ("false", "0", "no", "")
        return bool(v)

    cards_category: TaxonomyCode | None = Field(
        default=None,
        description="The single most relevant CARDS taxonomy code (e.g. '2_1'), or null if not climate misinformation.",
    )

    @field_validator("cards_category", mode="before")
    @classmethod
    def normalise_category(cls, v: object) -> object:
        """Normalises model output to a valid TaxonomyCode.

        Handles:
        - Bare integers / bare category strings: '1' -> '1_0', '2' -> '2_0'
        - Whitespace / case: ' 2_1 ' -> '2_1'
        - Already-valid codes pass through unchanged.
        - Unrecognised values pass through (pydantic raises the error).
        """
        from .presets import _TAXONOMY_CODE_SET

        if v is None:
            return v
        s = str(v).strip()
        if s in _TAXONOMY_CODE_SET:
            return s
        # bare main-category digit: '1' -> '1_0'
        if s.isdigit() and f"{s}_0" in _TAXONOMY_CODE_SET:
            return f"{s}_0"
        return s

    reasoning: str | None = Field(
        default=None,
        description="Brief chain-of-thought explanation of the classification decision.",
    )

    @field_validator("reasoning", mode="after")
    @classmethod
    def strip_think_tags(cls, v: str | None) -> str | None:
        """Removes <think>...</think> wrapper that some models emit around their CoT."""
        if v is None:
            return v
        stripped = re.sub(r"^\s*<think>\s*", "", v, flags=re.DOTALL)
        stripped = re.sub(r"\s*</think>\s*$", "", stripped, flags=re.DOTALL)
        return stripped.strip() or None


# ---------------------------------------------------------------------------
# Provider helpers
# ---------------------------------------------------------------------------


def _build_pydantic_ai_model(provider: str, model: str):
    """Return the correct pydantic-ai model object for *provider* and *model*.

    pydantic-ai natively supports string identifiers like ``"openai:gpt-4o-mini"``
    for first-class providers (openai, anthropic, groq, …).  OpenAI-compatible
    providers that require a custom endpoint or API key must be constructed
    explicitly via their provider class.

    Supported provider strings
    --------------------------
    ``"openai"``, ``"anthropic"``, ``"groq"``, and other natively-supported
    pydantic-ai providers are passed through as ``"{provider}:{model}"``.

    ``"ollama"``
        Uses :class:`~pydantic_ai.providers.ollama.OllamaProvider`.
        Reads ``OLLAMA_BASE_URL`` from the environment (default: the pydantic-ai
        default of ``http://localhost:11434/v1``).

    ``"openrouter"``
        Uses :class:`~pydantic_ai.providers.openrouter.OpenRouterProvider`.
        Reads ``OPENROUTER_API_KEY`` from the environment (picked up automatically
        by the provider).

    ``"lmstudio"``
        Uses an OpenAI-compatible endpoint via
        :class:`~pydantic_ai.providers.openai.OpenAIProvider`.
        Reads ``LMSTUDIO_BASE_URL`` from the environment (default:
        ``http://localhost:1234/v1``).
    """
    if provider == "ollama":
        from pydantic_ai.models.openai import OpenAIChatModel
        from pydantic_ai.providers.ollama import OllamaProvider

        base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
        return OpenAIChatModel(model, provider=OllamaProvider(base_url=base_url))

    if provider == "openrouter":
        from pydantic_ai.models.openai import OpenAIChatModel
        from pydantic_ai.providers.openrouter import OpenRouterProvider

        return OpenAIChatModel(model, provider=OpenRouterProvider())

    if provider == "lmstudio":
        from pydantic_ai.models.openai import OpenAIChatModel
        from pydantic_ai.providers.openai import OpenAIProvider

        base_url = os.getenv("LMSTUDIO_BASE_URL", "http://localhost:1234/v1")
        return OpenAIChatModel(model, provider=OpenAIProvider(base_url=base_url))

    # Native pydantic-ai string providers: openai, anthropic, groq, mistral, …
    return f"{provider}:{model}"


# ---------------------------------------------------------------------------
# Classifier
# ---------------------------------------------------------------------------


class CARDSLLMClassifier(CARDSClassifierBase):
    """CARDSLLMClassifier: classifies text using the CARDS taxonomy via an LLM.

    Uses a two-stage relevance gate:
    1. An optional pre-classifier (default: ClimateBertClassifier) filters clearly
       unrelated text *before* the LLM is called — no LLM cost, no cache write.
    2. The LLM's own ``is_climate_related`` field acts as a fallback gate when no
       pre-classifier is active.

    Results are cached in a ``preserve`` SQLite database keyed by
    ``hash(provider|model|system_prompt_hash|text)`` so repeated calls with the
    same configuration return immediately without hitting the LLM.

    Supports single classification via ``classify()`` and async-concurrent batch
    classification via ``classify_batch()``.

    Args:
        provider (str): LLM provider name passed to pydantic-ai (e.g. ``"openai"``,
            ``"ollama"``, ``"openrouter"``).
        model (str): Model name passed to pydantic-ai (e.g. ``"gpt-4o-mini"``).
        preclassifier: Any object with a ``.classify(text: str) -> str`` method.
            Takes priority over ``use_preclassifier``.
        use_preclassifier (bool): When True and no ``preclassifier`` is provided,
            instantiates a ``ClimateBertClassifier`` as the default gate.
        system_prompt (str): System prompt for the LLM agent.
        user_prompt (str): User prompt template; ``{text}`` is replaced at call time.
        cache_path (str | None): Path to the preserve SQLite cache. Created
            automatically if it does not exist. Set to None to disable caching.
        temperature (float): Sampling temperature. 0.0 = greedy/deterministic.
        top_p (float | None): Nucleus sampling probability. None = provider default.
        max_tokens (int | None): Maximum tokens to generate. None = provider default.
        output_mode ("tool" | "prompted"): Structured-output strategy passed to
            pydantic-ai. ``"tool"`` (default) uses tool-calling with a forced
            ``tool_choice`` — works with most providers, but some reject a
            forced ``tool_choice`` while a "thinking" / reasoning mode is
            active (e.g. ``qwen/qwen3-8b`` on OpenRouter: "The tool_choice
            parameter does not support being set to required or object in
            thinking mode"). ``"prompted"`` asks the model for matching JSON
            in plain text instead (pydantic-ai's ``PromptedOutput``) — no
            ``tool_choice`` or provider-specific response-format support
            required, so it works with any completion endpoint. (Pydantic-ai's
            native JSON-schema response-format mode was also tried but is
            unusable through OpenRouter: it requires pydantic-ai to recognise
            the specific model as supporting it, which it does not for
            OpenRouter's proxied catalog — hence "prompted" as the fallback.)
    """

    def __init__(
        self,
        provider: str = CARDS_LLM_DEFAULT_PROVIDER,
        model: str = CARDS_LLM_DEFAULT_MODEL,
        preclassifier=None,
        use_preclassifier: bool = True,
        system_prompt: str = CARDS_LLM_DEFAULT_SYSTEM_PROMPT,
        system_prompt_with_context: str = CARDS_LLM_DEFAULT_SYSTEM_PROMPT_WITH_CONTEXT,
        user_prompt: str = CARDS_LLM_DEFAULT_USER_PROMPT,
        user_prompt_with_context: str = CARDS_LLM_DEFAULT_USER_PROMPT_WITH_CONTEXT,
        max_context_chars: int | None = None,
        cache_path: str | None = None,
        default_concurrency: int = 8,
        temperature: float = 0.0,
        top_p: float | None = None,
        max_tokens: int | None = None,
        output_mode: str = "tool",
    ):
        if output_mode not in ("tool", "prompted"):
            raise ValueError(f"output_mode must be 'tool' or 'prompted', got {output_mode!r}")
        self._provider = provider
        self._model = model
        self._output_mode = output_mode
        self._system_prompt = system_prompt
        self._system_prompt_with_context = system_prompt_with_context
        self._user_prompt = user_prompt
        self._user_prompt_with_context = user_prompt_with_context
        self._max_context_chars = max_context_chars
        self._default_concurrency = default_concurrency
        self._model_settings: dict = {"temperature": temperature}
        if top_p is not None:
            self._model_settings["top_p"] = top_p
        if max_tokens is not None:
            self._model_settings["max_tokens"] = max_tokens
        settings_key = f"t={temperature}"
        if top_p is not None:
            settings_key += f"|p={top_p}"
        if max_tokens is not None:
            settings_key += f"|m={max_tokens}"
        if output_mode != "tool":
            settings_key += f"|out={output_mode}"
        self._run_prefix = f"{provider}|{model}|{hash_string(system_prompt)}|{settings_key}"

        if preclassifier is not None:
            self._preclassifier = preclassifier
        elif use_preclassifier:
            from ...climate import ClimateBertClassifier  # lazy — avoids loading transformers at import time

            self._preclassifier = ClimateBertClassifier()
        else:
            self._preclassifier = None

        if self._preclassifier is not None:
            pre_id = type(self._preclassifier).__name__
            if model_name := getattr(self._preclassifier, "model_name", None):
                pre_id = f"{pre_id}|{model_name}"
            pre_prefix = f"preclassifier|{pre_id}"
        else:
            pre_prefix = None
        self._preclassifier_cache = ClassificationCache(cache_path, fingerprint=pre_prefix or "")
        self._output_cache = ClassificationCache(
            cache_path,
            fingerprint=self._run_prefix,
            serialize=lambda output: output.model_dump(),
            deserialize=lambda data: CARDSOutput.model_validate(data),
        )

        agent_output_type = PromptedOutput(CARDSOutput) if output_mode == "prompted" else CARDSOutput
        self._agent: Agent[None, CARDSOutput] = Agent(
            _build_pydantic_ai_model(provider, model),
            output_type=agent_output_type,
            instructions=system_prompt,
            retries=3,
            output_retries=3,
        )

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def from_preset(cls, name: str, preclassifier=None, **overrides) -> "CARDSLLMClassifier":
        """Instantiate from a named preset.

        Args:
            name: Preset name — see :func:`.registered_presets` for available names.
            preclassifier: Optional runtime preclassifier object.  Not stored in
                :class:`CARDSLLMConfig` because it is a live object, not a value.
            **overrides: :class:`CARDSLLMConfig` field values to apply on top of
                the named preset (e.g. ``cache_path="/tmp/cards.db"``).

        Returns:
            A new :class:`CARDSLLMClassifier` configured from the preset.

        Raises:
            KeyError: If *name* is not in the preset registry.
        """
        if name not in _REGISTRY:
            available = ", ".join(registered_presets())
            raise KeyError(f"Unknown preset {name!r}. Available presets: {available}")
        preset_cls = _REGISTRY[name]
        if overrides:
            valid = {f.name for f in dataclasses.fields(preset_cls())}
            bad = set(overrides) - valid
            if bad:
                raise TypeError(
                    f"Invalid override(s) for preset {name!r}: {sorted(bad)}. Valid fields: {sorted(valid)}"
                )
        cfg = dataclasses.replace(preset_cls(), **overrides)
        return cls(
            provider=cfg.provider,
            model=cfg.model,
            preclassifier=preclassifier,
            use_preclassifier=cfg.use_preclassifier,
            system_prompt=cfg.system_prompt,
            system_prompt_with_context=cfg.system_prompt_with_context,
            user_prompt=cfg.user_prompt,
            user_prompt_with_context=cfg.user_prompt_with_context,
            max_context_chars=cfg.max_context_chars,
            cache_path=cfg.cache_path,
            default_concurrency=cfg.default_concurrency,
            temperature=cfg.temperature,
            top_p=cfg.top_p,
            max_tokens=cfg.max_tokens,
            output_mode=cfg.output_mode,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _label_from_output(self, output: CARDSOutput) -> str:
        """Converts agent output to a single CARDS code string.

        TODO: this collapses `is_climate_related` into the "0_0" code, discarding
        the relatedness/category distinction the annotation data (see
        climatesense_dataset_v1/v2 in datasets.py) tracks separately. Fine for
        KG-building (builders/climafactskg.py only checks the final code either
        way), but it means eval/optimization can't distinguish a relatedness-gate
        miss from a category miss. Consider persisting `is_climate_related` as
        its own field (see collectors/utils.py's entry dict) instead of
        collapsing here, once there's a clean baseline to build it on.
        """
        if not output.is_climate_related or output.cards_category is None:
            return "0_0"
        return output.cards_category

    def _call_llm(self, text: str, context: str | None = None) -> CARDSOutput:
        """Runs a synchronous LLM call and returns the full agent output."""
        if context:
            if self._max_context_chars is not None:
                context = context[: self._max_context_chars]
            user_msg = self._user_prompt_with_context.format(text=text, context=context)
            with self._agent.override(instructions=self._system_prompt_with_context):
                return self._agent.run_sync(user_msg, model_settings=self._model_settings).output
        return self._agent.run_sync(self._user_prompt.format(text=text), model_settings=self._model_settings).output

    async def _call_llm_async(self, text: str, semaphore: asyncio.Semaphore, context: str | None = None) -> CARDSOutput:
        """Runs one async LLM call, bounded by the provided semaphore.

        Retries with exponential backoff on transient HTTP errors (rate limits,
        timeouts, upstream provider fallback failures — see
        :data:`_RETRYABLE_STATUS_CODES`), up to :data:`_DEFAULT_MAX_RETRIES` times.
        """
        if context:
            if self._max_context_chars is not None:
                context = context[: self._max_context_chars]
            user_msg = self._user_prompt_with_context.format(text=text, context=context)
        else:
            user_msg = self._user_prompt.format(text=text)

        for attempt in range(_DEFAULT_MAX_RETRIES + 1):
            try:
                async with semaphore:
                    if context:
                        with self._agent.override(instructions=self._system_prompt_with_context):
                            result = await self._agent.run(user_msg, model_settings=self._model_settings)
                    else:
                        result = await self._agent.run(user_msg, model_settings=self._model_settings)
                return result.output
            except ModelHTTPError as exc:
                if exc.status_code not in _RETRYABLE_STATUS_CODES or attempt == _DEFAULT_MAX_RETRIES:
                    raise
                delay = _DEFAULT_RETRY_BASE_DELAY * (2**attempt) + random.uniform(0, _DEFAULT_RETRY_BASE_DELAY)
                logger.warning(
                    "Retryable error (status=%s) on attempt %d/%d, retrying in %.1fs: %s",
                    exc.status_code,
                    attempt + 1,
                    _DEFAULT_MAX_RETRIES + 1,
                    delay,
                    exc,
                )
                # Sleep outside the semaphore so a backing-off task doesn't hold
                # its concurrency slot idle while other pending items wait.
                await asyncio.sleep(delay)

    async def _classify_batch_async(
        self,
        texts: list[str],
        contexts: list[str | None],
        concurrency: int,
        progress=None,
        task_id=None,
    ) -> list[CARDSOutput | Exception]:
        """Runs concurrent LLM calls for a list of texts with optional per-item context.

        Returns one result per input, in the same order. A call that still fails
        after retries has its exception placed in that slot instead of being
        raised, so that other successful results in the same batch are not lost.
        """
        semaphore = asyncio.Semaphore(concurrency)

        async def _tracked(coro):
            result = await coro
            if progress is not None and task_id is not None:
                progress.advance(task_id)
            return result

        return list(
            await asyncio.gather(
                *[_tracked(self._call_llm_async(t, semaphore, ctx)) for t, ctx in zip(texts, contexts)],
                return_exceptions=True,
            )
        )

    def _preclassify(self, text: str) -> Optional[str]:
        """Returns the preclassifier label for *text*, using the cache when available.

        Returns ``None`` when no preclassifier is configured.
        """
        if self._preclassifier is None:
            return None
        return self._preclassifier_cache.get_or_compute(
            [text],
            key_fn=lambda t: t,
            compute_fn=lambda pending: [self._preclassifier.classify(t) for t in pending],
        )[0]

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def classify(self, text: str, context: str | None = None, skip_preclassifier: bool = False) -> str:
        """Classifies a single text using the configured LLM.

        Gate 1 — pre-classifier: if active and the text is unrelated, returns
        ``"0"`` immediately without an LLM call or cache write.

        Gate 2 — LLM relevance: ``is_climate_related=False`` or an empty
        ``cards_categories`` field acts as a fallback gate when no
        pre-classifier is active.

        Cache: results are stored and retrieved by
        ``hash(provider|model|system_prompt_hash|settings|text[|context])``.

        Args:
            text: The input text to classify.
            context: Optional fact-check context (e.g. reviewer verdict). When
                provided, both system and user prompts switch to their
                ``*_with_context`` variants. Truncated to ``max_context_chars``
                if configured.
            skip_preclassifier: Bypass Gate 1 and go directly to the LLM.

        Returns:
            A CARDS taxonomy code or ``"0_0"`` if not climate misinformation.
        """
        if not skip_preclassifier and self._preclassify(text) == "unrelated":
            return "0"

        output = self._output_cache.get_or_compute(
            [(text, context)],
            key_fn=lambda pair: f"{pair[0]}|{pair[1]}" if pair[1] else pair[0],
            compute_fn=lambda pending: [self._call_llm(t, ctx) for t, ctx in pending],
        )[0]
        return self._label_from_output(output)

    def classify_batch(
        self,
        texts: list[str],
        contexts: list[str | None] | None = None,
        concurrency: int | None = None,
        skip_preclassifier: bool = False,
    ) -> list[Optional[str]]:
        """Classifies multiple texts with concurrent LLM calls and batch cache I/O.

        Processing order:
        1. **Pre-classifier pass** (sync, sequential): texts flagged as unrelated
           are resolved to ``"0"`` immediately — no LLM call, no cache write.
        2. **Cache batch-read** (sync): remaining texts are looked up in a single
           preserve open; hits are resolved without an LLM call.
        3. **Async concurrent LLM** (bounded by ``concurrency``): cache misses are
           sent to the LLM concurrently via ``asyncio.run()``.
        4. **Cache batch-write** (sync): all new results are persisted in a single
           preserve open.

        Note: ``asyncio.run()`` creates a new event loop and must be called from a
        synchronous context. In async contexts (e.g. Jupyter), call
        ``await classifier._classify_batch_async(texts, contexts, concurrency)`` directly.

        Args:
            texts: Texts to classify.
            contexts: Optional per-item fact-check context. Must be ``None`` (no
                context for any item) or a list of the same length as ``texts``.
            concurrency: Maximum number of concurrent LLM calls. Defaults to
                ``self._default_concurrency``.
            skip_preclassifier: Bypass the pre-classifier for all texts.

        Returns:
            CARDS taxonomy codes in the same order as the input. An item whose
            LLM call still fails after retries gets ``None`` instead of raising
            — this preserves every other successful result in the batch.
        """
        from rich.progress import (
            BarColumn,
            MofNCompleteColumn,
            Progress,
            SpinnerColumn,
            TimeElapsedColumn,
            TimeRemainingColumn,
        )

        effective_contexts: list[str | None] = contexts if contexts is not None else [None] * len(texts)
        results: list[Optional[str]] = [None] * len(texts)
        pending_indices: list[int] = []

        with Progress(
            SpinnerColumn(),
            "[progress.description]{task.description}",
            BarColumn(),
            MofNCompleteColumn(),
            TimeElapsedColumn(),
            TimeRemainingColumn(),
        ) as progress:
            task_id = progress.add_task(f"Classifying [{self._model}]", total=len(texts))

            # Gate 1: pre-classifier — resolve unrelated texts without LLM
            if not skip_preclassifier and self._preclassifier is not None:

                def _compute_pre(pending: list[str]) -> list[str]:
                    return [self._preclassifier.classify(t) for t in pending]

                def _advance_on_hit(_text: str, _label: str) -> None:
                    progress.advance(task_id)

                pre_labels = self._preclassifier_cache.get_or_compute(
                    texts, key_fn=lambda t: t, compute_fn=_compute_pre, on_hit=_advance_on_hit
                )
                for i, label in enumerate(pre_labels):
                    if label == "unrelated":
                        results[i] = "0"
                        progress.advance(task_id)
                    else:
                        pending_indices.append(i)
            else:
                pending_indices = list(range(len(texts)))

            if not pending_indices:
                return results  # type: ignore[return-value]

            pending_pairs = [(texts[i], effective_contexts[i]) for i in pending_indices]

            def _compute_llm(pending: list[tuple[str, str | None]]) -> list[CARDSOutput | Exception]:
                effective_concurrency = concurrency if concurrency is not None else self._default_concurrency
                pending_texts = [t for t, _ in pending]
                pending_contexts = [ctx for _, ctx in pending]
                return asyncio.run(
                    self._classify_batch_async(
                        pending_texts, pending_contexts, effective_concurrency, progress, task_id
                    )
                )

            def _advance_output_hit(_pair: tuple[str, str | None], _output: CARDSOutput) -> None:
                progress.advance(task_id)

            outputs = self._output_cache.get_or_compute(
                pending_pairs,
                key_fn=lambda pair: f"{pair[0]}|{pair[1]}" if pair[1] else pair[0],
                compute_fn=_compute_llm,
                should_cache=lambda output: not isinstance(output, Exception),
                on_hit=_advance_output_hit,
            )

        failures: list[tuple[int, Exception]] = [
            (orig_idx, output) for orig_idx, output in zip(pending_indices, outputs) if isinstance(output, Exception)
        ]
        for orig_idx, output in zip(pending_indices, outputs):
            if not isinstance(output, Exception):
                results[orig_idx] = self._label_from_output(output)

        if failures:
            logger.error(
                "%d/%d LLM classification(s) failed after retries (%d succeeded); "
                "failed items are left as None. First failure at text index %d: %r",
                len(failures),
                len(outputs),
                len(outputs) - len(failures),
                failures[0][0],
                failures[0][1],
            )

        return results
