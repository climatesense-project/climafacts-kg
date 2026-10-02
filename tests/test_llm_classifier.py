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

    def test_the_context_length_limit_is_part_of_the_key(self):
        # The request uses context[:max_context_chars], so two limits must not share cached answers.
        assert self._prefix(max_context_chars=200) != self._prefix(max_context_chars=400) != self._prefix()

    @pytest.mark.parametrize(
        "field", ["system_prompt", "user_prompt", "system_prompt_with_context", "user_prompt_with_context"]
    )
    def test_changing_any_prompt_template_changes_the_key(self, field):
        # Editing a template must never be answered from results produced by the old wording.
        assert self._prefix(**{field: "changed {text} {context}"}) != self._prefix()


class TestBatchFailuresAndCaching:
    """classify_batch with the LLM call itself stubbed: failure isolation, caching and context routing."""

    def _classifier(self, tmp_path, outputs):
        from climafactskg.classifiers.cards.cache import ClassificationCache
        from climafactskg.classifiers.cards.llm.classifier import CARDSOutput

        clf = CARDSLLMClassifier.__new__(CARDSLLMClassifier)
        clf._preclassifier = None
        clf._default_concurrency = 1
        clf._model = "stub"
        clf._output_cache = ClassificationCache(
            str(tmp_path / "c.db"),
            fingerprint="fp",
            serialize=lambda out: out.model_dump(),
            deserialize=lambda data: CARDSOutput.model_validate(data),
        )
        clf.calls = []

        async def fake(texts, contexts, concurrency, progress, task_id):
            clf.calls.append(list(zip(texts, contexts, strict=True)))
            return [outputs[text] for text in texts]

        clf._classify_batch_async = fake
        return clf

    def _out(self, category, related=True):
        from climafactskg.classifiers.cards.llm.classifier import CARDSOutput

        return CARDSOutput(is_climate_related=related, cards_category=category, reasoning="r")

    def test_one_failed_item_is_none_and_the_others_keep_their_labels(self, tmp_path):
        clf = self._classifier(tmp_path, {"a": self._out("1_1"), "b": RuntimeError("boom"), "c": self._out("2_1")})

        assert clf.classify_batch(["a", "b", "c"]) == ["1_1", None, "2_1"]

    def test_failures_are_not_cached_so_they_are_retried_on_the_next_run(self, tmp_path):
        clf = self._classifier(tmp_path, {"a": self._out("1_1"), "b": RuntimeError("boom")})
        clf.classify_batch(["a", "b"])
        clf.classify_batch(["a", "b"])

        assert [text for text, _ in clf.calls[1]] == ["b"]  # "a" came from the cache, only "b" was asked again

    def test_an_unrelated_or_category_less_answer_is_the_not_related_code(self, tmp_path):
        clf = self._classifier(tmp_path, {"a": self._out(None), "b": self._out("1_1", related=False)})

        assert clf.classify_batch(["a", "b"]) == ["0_0", "0_0"]

    def test_the_same_text_with_and_without_context_is_two_separate_calls(self, tmp_path):
        clf = self._classifier(tmp_path, {"a": self._out("1_1")})
        clf.classify_batch(["a"])
        clf.classify_batch(["a"], contexts=["review text"])
        clf.classify_batch(["a"], contexts=["review text"])

        assert clf.calls == [[("a", None)], [("a", "review text")]]  # the third call was fully cached
