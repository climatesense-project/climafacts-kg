"""LLM-specific configuration: output contract types, presets, and config dataclass."""

import dataclasses
import os
from typing import Literal, get_args

from .prompts import (
    CARDS_LLM_DEFAULT_SYSTEM_PROMPT,
    CARDS_LLM_DEFAULT_SYSTEM_PROMPT_WITH_CONTEXT,
    CARDS_LLM_DEFAULT_USER_PROMPT,
    CARDS_LLM_DEFAULT_USER_PROMPT_WITH_CONTEXT,
    CARDS_NARRATIVE_SYSTEM_PROMPT,
    CARDS_NARRATIVE_SYSTEM_PROMPT_WITH_CONTEXT,
    CARDS_NARRATIVE_USER_PROMPT,
    CARDS_NARRATIVE_USER_PROMPT_WITH_CONTEXT,
    CARDS_USER_PROMPT_WITH_CONTEXT,
    CLIMATESENSE_NSLP_MODEL,
    CLIMATESENSE_NSLP_PROVIDER,
    CLIMATESENSE_NSLP_SYSTEM_PROMPT,
    CLIMATESENSE_NSLP_SYSTEM_PROMPT_WITH_CONTEXT,
    CLIMATESENSE_NSLP_USER_PROMPT,
    XPLAINNLP_NSLP_MODEL,
    XPLAINNLP_NSLP_PROVIDER,
    XPLAINNLP_NSLP_SYSTEM_PROMPT,
    XPLAINNLP_NSLP_SYSTEM_PROMPT_WITH_CONTEXT,
    XPLAINNLP_NSLP_USER_PROMPT,
    XPLAINNLP_NSLP_USER_PROMPT_WITH_CONTEXT,
)

# ---------------------------------------------------------------------------
# LLM output contract — the 35 codes the LLM is expected to produce.
# Kept here (not in taxonomy.py) because they define the *LLM interface*, not
# the full taxonomy used by the matcher/transformer.
# ---------------------------------------------------------------------------

TaxonomyCode = Literal[
    "0",
    "0_0",
    "1_0",
    "1_1",
    "1_2",
    "1_3",
    "1_4",
    "1_5",
    "1_6",
    "1_7",
    "1_8",
    "2_0",
    "2_1",
    "2_2",
    "2_3",
    "2_4",
    "2_5",
    "3_0",
    "3_1",
    "3_2",
    "3_3",
    "3_4",
    "3_5",
    "3_6",
    "4_0",
    "4_1",
    "4_2",
    "4_3",
    "4_4",
    "4_5",
    "5_0",
    "5_1",
    "5_2",
    "5_3",
]

# Runtime set equivalent of TaxonomyCode for O(1) membership tests, used by
# CARDSOutput.normalise_category(). Derived from the Literal itself via
# get_args() rather than retyped, so the two can't drift out of sync.
_TAXONOMY_CODE_SET: set[str] = set(get_args(TaxonomyCode))

# Ordered label descriptions for the LLM codes, derived from the shared taxonomy.
# Lazy-populated on first access to avoid a circular import with taxonomy.py.
_CARDS_LABEL_DESCRIPTIONS: dict[str, str] | None = None


def get_cards_label_descriptions() -> dict[str, str]:
    """Returns a mapping of LLM taxonomy code → human-readable label."""
    global _CARDS_LABEL_DESCRIPTIONS
    if _CARDS_LABEL_DESCRIPTIONS is None:
        from ..taxonomy import TAXONOMY

        _CARDS_LABEL_DESCRIPTIONS = {
            entry["id"]: entry["label"] for entry in TAXONOMY if entry["id"] in _TAXONOMY_CODE_SET
        }
    return _CARDS_LABEL_DESCRIPTIONS


# ---------------------------------------------------------------------------
# Default provider / model (env-var overridable at process start)
# ---------------------------------------------------------------------------

CARDS_LLM_DEFAULT_PROVIDER: str = os.getenv("CARDS_LLM_PROVIDER", "openai")
CARDS_LLM_DEFAULT_MODEL: str = os.getenv("CARDS_LLM_MODEL", "gpt-4o-mini")


# ---------------------------------------------------------------------------
# Configuration dataclass
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class CARDSLLMConfig:
    """Configuration bundle for a :class:`CARDSLLMClassifier` instance.

    All fields map 1-to-1 to the corresponding ``__init__`` parameters of
    :class:`CARDSLLMClassifier`.  Use :func:`dataclasses.replace` (or
    ``CARDSLLMClassifier.from_preset``) to create variants of an existing config.

    Attributes:
        provider: LLM provider name passed to pydantic-ai (e.g. ``"openai"``).
        model: Model identifier passed to pydantic-ai (e.g. ``"gpt-4o-mini"``).
        system_prompt: System prompt for the LLM agent.
        system_prompt_with_context: System prompt used when fact-check context is
            provided; extends ``system_prompt`` with a usage instruction.
        user_prompt: User prompt template; ``{text}`` is replaced at call time.
        user_prompt_with_context: User prompt template used when fact-check context
            is provided; ``{text}`` and ``{context}`` are replaced at call time.
        max_context_chars: Maximum number of characters to include from the
            fact-check context.  Longer context is silently truncated.  ``None``
            means no truncation.
        use_preclassifier: When True, a ClimateBertClassifier pre-filter is used.
        cache_path: Path to the preserve SQLite cache, or None to disable caching.
        temperature: Sampling temperature. Use 0.0 for greedy/deterministic output.
            Qwen3 thinking mode requires a non-zero value (paper uses 0.6).
        top_p: Nucleus sampling probability. None defers to the provider default.
        max_tokens: Maximum tokens to generate. None defers to the provider default.
        output_mode: Structured-output strategy — ``"tool"`` (default) or
            ``"prompted"``. See :class:`.CARDSLLMClassifier` for when
            ``"prompted"`` is needed (e.g. thinking-mode models that reject a
            forced ``tool_choice``, such as ``qwen/qwen3-8b`` on OpenRouter).
    """

    provider: str = dataclasses.field(default_factory=lambda: CARDS_LLM_DEFAULT_PROVIDER)
    model: str = dataclasses.field(default_factory=lambda: CARDS_LLM_DEFAULT_MODEL)
    system_prompt: str = dataclasses.field(default_factory=lambda: CARDS_LLM_DEFAULT_SYSTEM_PROMPT)
    system_prompt_with_context: str = dataclasses.field(
        default_factory=lambda: CARDS_LLM_DEFAULT_SYSTEM_PROMPT_WITH_CONTEXT
    )
    user_prompt: str = dataclasses.field(default_factory=lambda: CARDS_LLM_DEFAULT_USER_PROMPT)
    user_prompt_with_context: str = dataclasses.field(
        default_factory=lambda: CARDS_LLM_DEFAULT_USER_PROMPT_WITH_CONTEXT
    )
    max_context_chars: int | None = None
    use_preclassifier: bool = True
    cache_path: str | None = None
    default_concurrency: int = 8
    temperature: float = 0.0
    top_p: float | None = None
    max_tokens: int | None = None
    output_mode: str = "tool"


# ---------------------------------------------------------------------------
# Preset registry
# ---------------------------------------------------------------------------

_REGISTRY: dict[str, type["CARDSLLMConfig"]] = {}


def register_preset(name: str):
    """Class decorator that registers a :class:`CARDSLLMConfig` subclass as a named preset.

    The decorated class is stored in ``_REGISTRY`` under *name* and returned
    unchanged, so the name binding stays a class (usable as a type annotation).

    Example::

        @register_preset("openai-gpt4o-mini")
        @dataclasses.dataclass
        class GptMiniCARDSLLMConfig(CARDSLLMConfig):
            provider: str = "openai"
            model: str = "gpt-4o-mini"

    """

    def decorator(cls: type[CARDSLLMConfig]) -> type[CARDSLLMConfig]:
        _REGISTRY[name] = cls
        return cls

    return decorator


def registered_presets() -> tuple[str, ...]:
    """Returns the names of all registered presets in registration order."""
    return tuple(_REGISTRY)


# ---------------------------------------------------------------------------
# Built-in presets
# ---------------------------------------------------------------------------
@register_preset("climatesense-nslp")
@dataclasses.dataclass
class ClimateSenseNSLPCARDSLLMConfig(CARDSLLMConfig):
    """Preset: Adapted ClimateSense submission."""

    provider: str = CLIMATESENSE_NSLP_PROVIDER
    model: str = CLIMATESENSE_NSLP_MODEL
    system_prompt: str = CLIMATESENSE_NSLP_SYSTEM_PROMPT
    system_prompt_with_context: str = CLIMATESENSE_NSLP_SYSTEM_PROMPT_WITH_CONTEXT
    user_prompt: str = CLIMATESENSE_NSLP_USER_PROMPT
    user_prompt_with_context: str = CARDS_USER_PROMPT_WITH_CONTEXT
    use_preclassifier: bool = True
    cache_path: str | None = None


@register_preset("xplainnlp-nslp")
@dataclasses.dataclass
class XplaiNLPNSLPCARDSLLMConfig(CARDSLLMConfig):
    """Preset: Adapted XplaiNLP @ ClimateCheck 2026 submission."""

    # http://lrec-conf.org/proceedings/lrec2026/workshops/nslp/2026.nslp-1.0.pdf
    # https://github.com/Dagobert42/climatecheck2026-task2-hierarchical-approaches
    provider: str = XPLAINNLP_NSLP_PROVIDER
    model: str = XPLAINNLP_NSLP_MODEL
    system_prompt: str = XPLAINNLP_NSLP_SYSTEM_PROMPT
    system_prompt_with_context: str = XPLAINNLP_NSLP_SYSTEM_PROMPT_WITH_CONTEXT
    user_prompt: str = XPLAINNLP_NSLP_USER_PROMPT
    user_prompt_with_context: str = XPLAINNLP_NSLP_USER_PROMPT_WITH_CONTEXT
    use_preclassifier: bool = False
    cache_path: str | None = None
    default_concurrency: int = 1
    # Qwen3 thinking mode requires sampling; greedy (0.0) collapses <think> blocks.
    # Values from inference.py in the paper's repo (thinking=True branch).
    temperature: float = 0.6
    top_p: float | None = 0.95
    max_tokens: int | None = 4096


@register_preset("cards-narrative")
@dataclasses.dataclass
class CARDSNarrativeLLMConfig(CARDSLLMConfig):
    """Preset: narrative-aware CARDS classifier.

    Classifies the underlying sceptical narrative a claim promotes rather than
    the surface claim.  A false or debunked claim is not automatically 0_0 —
    the model infers the narrative from both claim text and optional fact-check
    context.
    """

    system_prompt: str = dataclasses.field(default=CARDS_NARRATIVE_SYSTEM_PROMPT)
    system_prompt_with_context: str = dataclasses.field(default=CARDS_NARRATIVE_SYSTEM_PROMPT_WITH_CONTEXT)
    user_prompt: str = dataclasses.field(default=CARDS_NARRATIVE_USER_PROMPT)
    user_prompt_with_context: str = dataclasses.field(default=CARDS_NARRATIVE_USER_PROMPT_WITH_CONTEXT)
