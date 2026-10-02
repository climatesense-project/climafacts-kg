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


class TestExtraBody:
    def _clf(self, **kw):
        return CARDSLLMClassifier(provider="ollama", model="m", use_preclassifier=False, **kw)

    def test_extra_body_is_sent_with_every_request(self):
        clf = self._clf(extra_body={"reasoning": {"effort": "low"}})

        assert clf._model_settings["extra_body"] == {"reasoning": {"effort": "low"}}
        assert "extra_body" not in self._clf()._model_settings

    def test_it_is_part_of_the_cache_key_independent_of_key_order(self):
        base = self._clf()._run_prefix
        a = self._clf(extra_body={"reasoning": {"effort": "low"}, "x": 1})._run_prefix
        b = self._clf(extra_body={"x": 1, "reasoning": {"effort": "low"}})._run_prefix
        c = self._clf(extra_body={"reasoning": {"effort": "high"}, "x": 1})._run_prefix

        assert a == b != base and a != c

    def test_without_it_the_key_is_unchanged_so_existing_cache_entries_stay_valid(self):
        assert "|x=" not in self._clf()._run_prefix

    def test_presets_accept_it_as_an_override(self):
        clf = CARDSLLMClassifier.from_preset(
            "xplainnlp-nslp", provider="ollama", model="m", use_preclassifier=False, extra_body={"a": 1}
        )

        assert clf._model_settings["extra_body"] == {"a": 1}


class TestRequestTimeoutAndRetries:
    def _clf(self, **kw):
        return CARDSLLMClassifier(provider="ollama", model="m", use_preclassifier=False, **kw)

    def test_request_timeout_goes_to_the_model_settings_but_not_the_cache_key(self):
        with_timeout = self._clf(request_timeout=90)

        assert with_timeout._model_settings["timeout"] == 90
        assert "timeout" not in self._clf()._model_settings
        assert with_timeout._run_prefix == self._clf()._run_prefix  # a timeout does not change the answers

    def test_presets_accept_it_as_an_override(self):
        clf = CARDSLLMClassifier.from_preset(
            "xplainnlp-nslp", provider="ollama", model="m", use_preclassifier=False, request_timeout=45
        )

        assert clf._model_settings["timeout"] == 45

    def _with_fake_agent(self, monkeypatch, failures, error):
        import asyncio

        from climafactskg.classifiers.cards.llm import classifier as module
        from climafactskg.classifiers.cards.llm.classifier import CARDSOutput

        monkeypatch.setattr(module, "_DEFAULT_RETRY_BASE_DELAY", 0.0)
        clf = self._clf()
        calls = {"n": 0}

        class _Result:
            output = CARDSOutput(is_climate_related=True, cards_category="1_1", reasoning="r")

        class _Agent:
            async def run(self, *args, **kwargs):
                calls["n"] += 1
                if calls["n"] <= failures:
                    raise error
                return _Result()

        clf._agent = _Agent()
        return clf, calls, asyncio

    def test_a_timeout_is_retried_and_then_succeeds(self, monkeypatch):
        from pydantic_ai.exceptions import ModelAPIError

        clf, calls, asyncio = self._with_fake_agent(monkeypatch, 2, ModelAPIError("m", "Request timed out."))

        out = asyncio.run(clf._call_llm_async("claim", asyncio.Semaphore(1)))

        assert out.cards_category == "1_1" and calls["n"] == 3

    def test_a_timeout_that_never_recovers_raises_after_the_retry_limit(self, monkeypatch):
        import pytest
        from pydantic_ai.exceptions import ModelAPIError

        clf, calls, asyncio = self._with_fake_agent(monkeypatch, 99, ModelAPIError("m", "Request timed out."))

        with pytest.raises(ModelAPIError):
            asyncio.run(clf._call_llm_async("claim", asyncio.Semaphore(1)))
        assert calls["n"] == 4  # the first try plus three retries

    def test_a_client_error_is_still_not_retried(self, monkeypatch):
        import pytest
        from pydantic_ai.exceptions import ModelHTTPError

        clf, calls, asyncio = self._with_fake_agent(monkeypatch, 99, ModelHTTPError(401, "m", "unauthorized"))

        with pytest.raises(ModelHTTPError):
            asyncio.run(clf._call_llm_async("claim", asyncio.Semaphore(1)))
        assert calls["n"] == 1
