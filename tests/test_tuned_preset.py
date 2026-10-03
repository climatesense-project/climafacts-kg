"""The experimental xplainnlp-nslp-tuned preset: it changes the system prompt and nothing else."""

import dataclasses

from climafactskg.classifiers.cards.llm.presets import _REGISTRY, registered_presets
from climafactskg.classifiers.cards.llm.prompts import XPLAINNLP_NSLP_SYSTEM_PROMPT, XPLAINNLP_NSLP_TUNED_SYSTEM_PROMPT


def test_the_tuned_preset_is_registered_but_the_default_is_unchanged():
    assert "xplainnlp-nslp-tuned" in registered_presets()
    assert _REGISTRY["xplainnlp-nslp"]().system_prompt == XPLAINNLP_NSLP_SYSTEM_PROMPT


def test_the_tuned_preset_differs_from_xplainnlp_nslp_only_in_the_system_prompt():
    base = dataclasses.asdict(_REGISTRY["xplainnlp-nslp"]())
    tuned = dataclasses.asdict(_REGISTRY["xplainnlp-nslp-tuned"]())

    changed = {key for key in base if base[key] != tuned[key]}

    assert changed == {"system_prompt"}
    assert tuned["system_prompt"] == XPLAINNLP_NSLP_TUNED_SYSTEM_PROMPT


def test_the_tuned_prompt_keeps_the_tested_text_with_its_json_wrapper_and_taxonomy():
    text = XPLAINNLP_NSLP_TUNED_SYSTEM_PROMPT

    assert text.lstrip().startswith('{\n  "instruction":')  # the optimiser's output, kept verbatim on purpose
    assert "0_0" in text
    assert "5_3" in text
    assert "cards_category" in text  # the output contract the classifier parses
