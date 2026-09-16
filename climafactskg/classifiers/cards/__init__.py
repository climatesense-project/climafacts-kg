"""climafactskg.classifiers.cards — CARDS taxonomy classifiers.

Public symbols
--------------
Taxonomy data:
    TAXONOMY                    — full CARDS taxonomy list
    TaxonomyCode                — Literal type of LLM-level codes

LLM presets / configuration:
    CARDSLLMConfig              — configuration dataclass
    register_preset             — class decorator to register a preset
    registered_presets          — returns all registered preset names
    ClimateSenseNSLPCARDSLLMConfig — preset: climatesense-nslp
    XplaiNLPNSLPCARDSLLMConfig  — preset: xplainnlp-nslp

LLM classifier defaults (overridable at init):
    CARDS_LLM_DEFAULT_PROVIDER
    CARDS_LLM_DEFAULT_MODEL
    CARDS_LLM_DEFAULT_SYSTEM_PROMPT
    CARDS_LLM_DEFAULT_USER_PROMPT
    CARDS_SYSTEM_PROMPT         — canonical expert system prompt
    CARDS_USER_PROMPT           — canonical user prompt template

Classifiers:
    CARDSClassifierBase         — shared classify/classify_batch interface
    CARDSMatcher                — Jaccard-similarity rule-based classifier
    CARDSClassifier             — Two-stage transformer classifier (binary + taxonomy)
    CARDSLLMClassifier          — LLM-based classifier with pre-filter and Preserve cache
    CARDSOutput                 — Pydantic output schema for CARDSLLMClassifier

Prompt optimisation (requires ``gepa`` package):
    CARDSEvalsAdapter           — GEPA adapter bridging pydantic-ai + pydantic-evals
    optimize_prompt             — run GEPA optimisation for a named preset

Legacy:
    cards_classification        — Single-call helper (loads models on every invocation)
"""

from .base import CARDSClassifierBase
from .llm import (
    CARDS_LLM_DEFAULT_MODEL,
    CARDS_LLM_DEFAULT_PROVIDER,
    CARDS_LLM_DEFAULT_SYSTEM_PROMPT,
    CARDS_LLM_DEFAULT_USER_PROMPT,
    CARDS_SYSTEM_PROMPT,
    CARDS_USER_PROMPT,
    CARDSLLMClassifier,
    CARDSLLMConfig,
    CARDSOutput,
    ClimateSenseNSLPCARDSLLMConfig,
    TaxonomyCode,
    XplaiNLPNSLPCARDSLLMConfig,
    register_preset,
    registered_presets,
)
from .taxonomy import TAXONOMY

# CARDSMatcher (spacy), CARDSClassifier/cards_classification (transformers/torch),
# and CARDSEvalsAdapter/optimize_prompt (gepa/pydantic_evals) pull in heavy
# dependencies. They're loaded lazily on first attribute access so that
# `from climafactskg.classifiers.cards.llm import CARDSLLMClassifier` — which
# must import this package's __init__ first — doesn't pay for or require them.
_LAZY_ATTRS = {
    "CARDSMatcher": ".matcher",
    "CARDSClassifier": ".transformer",
    "cards_classification": ".transformer",
    "CARDSEvalsAdapter": ".optimization",
    "optimize_prompt": ".optimization",
}


def __getattr__(name: str):
    module_name = _LAZY_ATTRS.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    import importlib

    module = importlib.import_module(module_name, __name__)
    return getattr(module, name)


__all__ = [
    "CARDSClassifierBase",
    "TAXONOMY",
    "TaxonomyCode",
    "CARDSLLMConfig",
    "register_preset",
    "registered_presets",
    "ClimateSenseNSLPCARDSLLMConfig",
    "XplaiNLPNSLPCARDSLLMConfig",
    "CARDS_LLM_DEFAULT_PROVIDER",
    "CARDS_LLM_DEFAULT_MODEL",
    "CARDS_LLM_DEFAULT_SYSTEM_PROMPT",
    "CARDS_LLM_DEFAULT_USER_PROMPT",
    "CARDS_SYSTEM_PROMPT",
    "CARDS_USER_PROMPT",
    "CARDSMatcher",
    "CARDSClassifier",
    "CARDSLLMClassifier",
    "CARDSOutput",
    "CARDSEvalsAdapter",
    "optimize_prompt",
    "cards_classification",
]
