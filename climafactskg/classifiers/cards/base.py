"""Shared interface for CARDS classifiers (matcher, transformer, LLM).

All three engines classify text against the CARDS taxonomy and are meant to be
interchangeable at call sites (``collectors/utils.py``, ``eval.py``, the CLI's
``classify`` command). This module pins down the one contract they share:
``classify``/``classify_batch``, both taking optional per-item ``context``.

Return type stays a plain CARDS code string (not a richer result object) —
that would be a bigger, separately-scoped change (see the
``project_relatedness_vs_category`` note for the deferred ``is_climate_related``
persistence work). Caching is likewise not part of this contract: it differs
too much per engine (see ``CARDSClassifier.cache_path`` vs
``CARDSLLMClassifier.cache_path``'s two-namespace pre-classifier gating) to be
worth forcing into a shared base/trait.
"""

from abc import ABC, abstractmethod
from typing import Optional


class CARDSClassifierBase(ABC):
    """Common interface for CARDS classifiers.

    Subclasses: :class:`~climafactskg.classifiers.cards.matcher.CARDSMatcher`,
    :class:`~climafactskg.classifiers.cards.transformer.CARDSClassifier`,
    :class:`~climafactskg.classifiers.cards.llm.classifier.CARDSLLMClassifier`.
    """

    @abstractmethod
    def classify(self, text: str, context: Optional[str] = None) -> str:
        """Classifies a single text, returning a CARDS taxonomy code.

        Args:
            text: The input text to classify.
            context: Optional fact-check context (e.g. reviewer verdict,
                sources) to inform the classification. Ignored by engines
                that don't use it.

        Returns:
            A CARDS taxonomy code, or the engine's "not relevant" sentinel
            (``"0"`` or ``"0_0"``) if the text isn't climate misinformation.
        """
        raise NotImplementedError

    def classify_batch(self, texts: list[str], contexts: Optional[list[Optional[str]]] = None) -> list[Optional[str]]:
        """Classifies multiple texts, returning one CARDS code per input.

        Default implementation calls :meth:`classify` sequentially — engines
        with a more efficient batch strategy (tensor batching, thread pools,
        concurrent async calls) override this.

        Args:
            texts: Texts to classify.
            contexts: Optional per-item context, same length as *texts* if given.

        Returns:
            CARDS taxonomy codes in the same order as the input. ``None`` for
            an item that failed to classify (only engines with retryable
            failure modes, e.g. the LLM classifier, ever produce ``None``).
        """
        effective_contexts = contexts if contexts is not None else [None] * len(texts)
        return [self.classify(text, context=ctx) for text, ctx in zip(texts, effective_contexts)]
