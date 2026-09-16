"""climafactskg.classifiers.cards.llm — LLM-based CARDS classifier subpackage.

Public symbols
--------------
Prompts:
    CARDS_SYSTEM_PROMPT             — canonical expert system prompt
    CARDS_USER_PROMPT               — canonical user prompt template
    CARDS_LLM_DEFAULT_SYSTEM_PROMPT — env-var-overridable system prompt
    CARDS_LLM_DEFAULT_USER_PROMPT   — env-var-overridable user prompt

Presets / configuration:
    TaxonomyCode                    — Literal type of LLM-level codes
    CARDSLLMConfig                  — configuration dataclass
    register_preset                 — class decorator to register a preset
    registered_presets              — returns all registered preset names
    ClimateSenseNSLPCARDSLLMConfig  — preset: climatesense-nslp
    XplaiNLPNSLPCARDSLLMConfig      — preset: xplainnlp-nslp
    CARDS_LLM_DEFAULT_PROVIDER      — env-var-overridable provider default
    CARDS_LLM_DEFAULT_MODEL         — env-var-overridable model default

Classifier:
    CARDSOutput                     — pydantic-ai structured output model
    CARDSLLMClassifier              — LLM classifier (classify / classify_batch / from_preset)
"""

from .classifier import CARDSLLMClassifier, CARDSOutput
from .presets import (
    CARDS_LLM_DEFAULT_MODEL,
    CARDS_LLM_DEFAULT_PROVIDER,
    CARDSLLMConfig,
    ClimateSenseNSLPCARDSLLMConfig,
    TaxonomyCode,
    XplaiNLPNSLPCARDSLLMConfig,
    register_preset,
    registered_presets,
)
from .prompts import (
    CARDS_LLM_DEFAULT_SYSTEM_PROMPT,
    CARDS_LLM_DEFAULT_USER_PROMPT,
    CARDS_SYSTEM_PROMPT,
    CARDS_USER_PROMPT,
)

__all__ = [
    # prompts
    "CARDS_SYSTEM_PROMPT",
    "CARDS_USER_PROMPT",
    "CARDS_LLM_DEFAULT_SYSTEM_PROMPT",
    "CARDS_LLM_DEFAULT_USER_PROMPT",
    # presets / config
    "TaxonomyCode",
    "CARDSLLMConfig",
    "register_preset",
    "registered_presets",
    "ClimateSenseNSLPCARDSLLMConfig",
    "XplaiNLPNSLPCARDSLLMConfig",
    "CARDS_LLM_DEFAULT_PROVIDER",
    "CARDS_LLM_DEFAULT_MODEL",
    # classifier
    "CARDSOutput",
    "CARDSLLMClassifier",
]
