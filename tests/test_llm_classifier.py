"""Offline tests for CARDSLLMClassifier input validation (no API calls, no model loading)."""

import pytest
from climafactskg.classifiers.cards.llm import CARDSLLMClassifier


class TestClassifyBatchContextLength:
    # classify_batch validates before touching any client/cache state, so an
    # uninitialised instance is enough and no network or API key is needed.
    @pytest.mark.parametrize("contexts", [["only one"], ["a", "b", "c"]])
    def test_mismatched_contexts_length_raises(self, contexts):
        clf = CARDSLLMClassifier.__new__(CARDSLLMClassifier)
        with pytest.raises(ValueError, match="contexts has"):
            clf.classify_batch(["one", "two"], contexts=contexts)
