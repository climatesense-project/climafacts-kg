"""Shared batch cache for CARDS classifiers, backed by a Preserve SQLite file.

``CARDSClassifier`` (transformer) and ``CARDSLLMClassifier`` each cache
classification results keyed by a config fingerprint plus per-item content —
this module is the one place that does the read/miss/compute/write loop, so
neither classifier hand-rolls its own ``preserve.open`` + hit/miss bookkeeping.

Each engine still owns *what* gets cached: the cache is generic over the
cached value via ``serialize``/``deserialize`` hooks (a transformer/matcher
label is a plain string; the LLM classifier caches a full ``CARDSOutput``
object). It's also generic over what identifies an item via ``key_fn``, since
the LLM classifier's cache key must incorporate per-item context even though
the LLM call itself needs ``text`` and ``context`` as separate arguments
(different prompt templates), not a joined string.
"""

from typing import Callable, Optional, TypeVar

import preserve

from climafactskg.utils import hash_string

T = TypeVar("T")
Item = TypeVar("Item")


class ClassificationCache:
    """Batch get-or-compute cache keyed by ``hash(fingerprint|key_fn(item))``.

    Args:
        cache_path: Path to a Preserve SQLite file. ``None`` disables caching
            entirely — ``get_or_compute`` then just calls *compute_fn* on
            every item, no I/O.
        fingerprint: Identifies the config that produced cached values (e.g.
            model names, prompt hash) — bake in anything that would make an
            old cache entry wrong if it changed.
        serialize: Converts a computed value to something JSON-storable in the
            Preserve DB. Defaults to identity (plain strings).
        deserialize: Inverse of *serialize*, applied when reading a cache hit.
    """

    def __init__(
        self,
        cache_path: Optional[str],
        fingerprint: str,
        serialize: Callable[[T], object] = lambda v: v,
        deserialize: Callable[[object], T] = lambda v: v,
    ):
        self.cache_path = cache_path
        self.fingerprint = fingerprint
        self._serialize = serialize
        self._deserialize = deserialize

    def _key(self, key_material: str) -> str:
        return hash_string(f"{self.fingerprint}|{key_material}")

    def get_or_compute(
        self,
        items: list[Item],
        key_fn: Callable[[Item], str],
        compute_fn: Callable[[list[Item]], list[T]],
        should_cache: Callable[[T], bool] = lambda value: True,
        on_hit: Callable[[Item, T], None] = lambda item, value: None,
    ) -> list[T]:
        """Returns one value per item, computing and caching only the misses.

        Args:
            items: Inputs to classify, in any shape *compute_fn* understands
                (a plain string, or e.g. a ``(text, context)`` tuple).
            key_fn: Derives the cache-key material for one item. Applied to
                every item regardless of cache hit/miss (cheap — it's just
                string formatting), so it can safely differ from *compute_fn*'s
                view of the item.
            compute_fn: Computes results for a list of cache-miss items, in
                the same order. Called once with all misses, not once per item
                — batch engines (tensor/async batching) should do their own
                internal chunking inside this callable.
            should_cache: Whether a computed value should be written back.
                Defaults to always. Use this to skip caching failures (e.g. an
                exception placeholder from a batch that tolerates per-item
                failure) without the failure ever reaching *serialize*.
            on_hit: Called for every cache hit, with the original item and the
                deserialized value — e.g. to advance a shared progress bar the
                same way a freshly computed item would.

        Returns:
            One result per item in *items*, same order, cache hits included.
        """
        if self.cache_path is None or not items:
            return compute_fn(items)

        keys = [self._key(key_fn(item)) for item in items]
        results: list[Optional[T]] = [None] * len(items)
        miss_indices: list[int] = []

        with preserve.open(format="sqlite", filename=self.cache_path) as db:
            for i, key in enumerate(keys):
                if key in db:
                    value = self._deserialize(db[key]["result"])
                    results[i] = value
                    on_hit(items[i], value)
                else:
                    miss_indices.append(i)

            if miss_indices:
                computed = compute_fn([items[i] for i in miss_indices])
                for i, value in zip(miss_indices, computed):
                    results[i] = value
                    if should_cache(value):
                        db[keys[i]] = {"key": key_fn(items[i]), "result": self._serialize(value)}

        return results  # type: ignore[return-value]
