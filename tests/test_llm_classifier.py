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


class TestCountCached:
    def _classifier(self, tmp_path):
        from climafactskg.classifiers.cards.cache import ClassificationCache

        clf = CARDSLLMClassifier.__new__(CARDSLLMClassifier)
        clf._output_cache = ClassificationCache(str(tmp_path / "c.db"), fingerprint="fp")
        return clf

    def test_counts_the_items_the_batch_call_would_find_in_the_cache(self, tmp_path):
        clf = self._classifier(tmp_path)
        clf._output_cache.get_or_compute(
            [("a", None), ("b", "ctx")], key_fn=clf._output_key, compute_fn=lambda pending: ["x"] * len(pending)
        )

        assert clf.count_cached(["a", "b", "c"], contexts=[None, "ctx", None]) == 2
        assert clf.count_cached(["a", "b"], contexts=[None, None]) == 1  # "b" without its context is another entry
        assert clf.count_cached(["a", "b"]) == 1

    def test_mismatched_contexts_length_raises(self, tmp_path):
        with pytest.raises(ValueError, match="contexts has"):
            self._classifier(tmp_path).count_cached(["a"], contexts=["x", "y"])


class TestCacheKeyCoversEveryPrompt:
    def _prefix(self, **overrides):
        clf = CARDSLLMClassifier(provider="ollama", model="m", use_preclassifier=False, **overrides)
        return clf._run_prefix

    def test_identical_prompts_share_a_key(self):
        assert self._prefix() == self._prefix()

    @pytest.mark.parametrize(
        "field", ["system_prompt", "user_prompt", "system_prompt_with_context", "user_prompt_with_context"]
    )
    def test_changing_any_prompt_template_changes_the_key(self, field):
        # Editing a template must never be answered from results produced by the old wording.
        assert self._prefix(**{field: "changed {text} {context}"}) != self._prefix()
