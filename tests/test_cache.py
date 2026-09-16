"""Tests for the shared ClassificationCache used by CARDSClassifier and CARDSLLMClassifier."""

from climafactskg.classifiers.cards.cache import ClassificationCache


class TestClassificationCache:
    def test_no_cache_path_always_computes(self):
        cache = ClassificationCache(None, fingerprint="fp")
        calls = []

        def compute(pending):
            calls.append(list(pending))
            return [t.upper() for t in pending]

        result = cache.get_or_compute(["a", "b"], key_fn=lambda t: t, compute_fn=compute)

        assert result == ["A", "B"]
        assert calls == [["a", "b"]]

    def test_second_call_hits_cache_not_compute(self, tmp_path):
        cache = ClassificationCache(str(tmp_path / "cache.db"), fingerprint="fp")
        calls = []

        def compute(pending):
            calls.append(list(pending))
            return [t.upper() for t in pending]

        first = cache.get_or_compute(["a", "b"], key_fn=lambda t: t, compute_fn=compute)
        second = cache.get_or_compute(["a", "b"], key_fn=lambda t: t, compute_fn=compute)

        assert first == second == ["A", "B"]
        assert calls == [["a", "b"]]  # only computed once

    def test_partial_hit_only_computes_misses(self, tmp_path):
        cache = ClassificationCache(str(tmp_path / "cache.db"), fingerprint="fp")
        cache.get_or_compute(["a"], key_fn=lambda t: t, compute_fn=lambda pending: [t.upper() for t in pending])

        calls = []

        def compute(pending):
            calls.append(list(pending))
            return [t.upper() for t in pending]

        result = cache.get_or_compute(["a", "b"], key_fn=lambda t: t, compute_fn=compute)

        assert result == ["A", "B"]
        assert calls == [["b"]]  # "a" was already cached

    def test_different_fingerprint_is_a_separate_cache(self, tmp_path):
        path = str(tmp_path / "cache.db")
        cache_v1 = ClassificationCache(path, fingerprint="v1")
        cache_v2 = ClassificationCache(path, fingerprint="v2")
        cache_v1.get_or_compute(["a"], key_fn=lambda t: t, compute_fn=lambda pending: ["from_v1" for _ in pending])

        result = cache_v2.get_or_compute(
            ["a"], key_fn=lambda t: t, compute_fn=lambda pending: ["from_v2" for _ in pending]
        )

        assert result == ["from_v2"]

    def test_should_cache_false_skips_write(self, tmp_path):
        cache = ClassificationCache(str(tmp_path / "cache.db"), fingerprint="fp")
        calls = []

        def compute(pending):
            calls.append(list(pending))
            return [ValueError("boom") for _ in pending]

        not_exception = lambda v: not isinstance(v, Exception)  # noqa: E731
        cache.get_or_compute(["a"], key_fn=lambda t: t, compute_fn=compute, should_cache=not_exception)
        cache.get_or_compute(["a"], key_fn=lambda t: t, compute_fn=compute, should_cache=not_exception)

        assert len(calls) == 2  # never cached, recomputed both times

    def test_on_hit_called_for_cached_items_only(self, tmp_path):
        cache = ClassificationCache(str(tmp_path / "cache.db"), fingerprint="fp")
        cache.get_or_compute(["a"], key_fn=lambda t: t, compute_fn=lambda pending: [t.upper() for t in pending])

        hits = []
        cache.get_or_compute(
            ["a", "b"],
            key_fn=lambda t: t,
            compute_fn=lambda pending: [t.upper() for t in pending],
            on_hit=lambda item, value: hits.append((item, value)),
        )

        assert hits == [("a", "A")]

    def test_serialize_deserialize_round_trip_for_non_string_values(self, tmp_path):
        cache = ClassificationCache(
            str(tmp_path / "cache.db"),
            fingerprint="fp",
            serialize=lambda v: {"n": v},
            deserialize=lambda d: d["n"],
        )
        cache.get_or_compute([1], key_fn=str, compute_fn=lambda pending: [n * 10 for n in pending])

        result = cache.get_or_compute([1], key_fn=str, compute_fn=lambda pending: [n * 999 for n in pending])

        assert result == [10]  # came from cache, not recomputed with the new multiplier
