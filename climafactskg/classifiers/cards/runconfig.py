"""Config file for ``climafactskg eval``: which classifiers are benchmarked on which datasets, and how.

A TOML file is validated into :class:`RunConfig`; :func:`build_dataset` / :func:`build_classifier` turn its entries
into the objects :func:`~climafactskg.classifiers.cards.eval.benchmark_configs` takes. Heavy imports stay inside the
builders so loading and planning a config needs neither the ML extras nor network access.
"""

import tomllib
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

LOCAL_PROVIDERS = frozenset({"ollama", "lmstudio"})
_LLM_ONLY_KEYS = ("provider", "model", "preset", "concurrency", "use_preclassifier")
_CLIMATESENSE_ONLY_KEYS = ("climate_only", "with_context", "only_with_context", "max_context_chars", "context_path")
_DATASET_FACTORIES = {
    "nslp": "nslp_dataset",
    "climatesense_v1": "climatesense_dataset_v1",
    "climatesense_v2": "climatesense_dataset_v2",
}


class ConfigError(ValueError):
    """The config file is missing, is not valid TOML, or breaks the schema."""


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RunSettings(_Strict):
    """``[run]``: where results go and which context modes are benchmarked."""

    save_dir: str = "data/eval_runs"
    context_modes: list[Literal["none", "with"]] = Field(default_factory=lambda: ["none", "with"], min_length=1)
    min_context_coverage: float = Field(0.5, ge=0, le=1)
    category_scores: Literal["all", "narrative_only"] = "all"


class ClassifierSpec(_Strict):
    """One ``[[classifiers]]`` entry. ``label`` names the config in results."""

    label: str = Field(min_length=1)
    engine: Literal["llm", "transformer", "matcher"] = "llm"
    provider: str | None = None
    model: str | None = None
    preset: str | None = None
    cache_path: str | None = None
    concurrency: int | None = Field(None, ge=1)
    use_preclassifier: bool = False
    options: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _llm_settings_only_for_llm(self) -> "ClassifierSpec":
        if self.engine != "llm":
            set_keys = [k for k in _LLM_ONLY_KEYS if getattr(self, k) not in (None, False)]
            if set_keys:
                raise ValueError(f"{', '.join(set_keys)} only apply to engine 'llm', not {self.engine!r}")
        return self


class DatasetSpec(_Strict):
    """One ``[[datasets]]`` entry. ``label`` defaults to ``name``; use it to run one dataset under several settings."""

    name: Literal["nslp", "climatesense_v1", "climatesense_v2"]
    label: str = ""
    limit: int | None = Field(None, gt=0)
    split: Literal["train", "test"] | None = None
    climate_only: bool | None = None
    with_context: bool | None = None
    only_with_context: bool | None = None
    max_context_chars: int | None = Field(None, gt=0)
    context_path: str | None = None

    @model_validator(mode="after")
    def _options_match_dataset(self) -> "DatasetSpec":
        if not self.label:
            self.label = self.name
        if self.name == "nslp":
            wrong = [k for k in _CLIMATESENSE_ONLY_KEYS if getattr(self, k) is not None]
            if wrong:
                raise ValueError(f"{', '.join(wrong)} only apply to the climatesense datasets, not 'nslp'")
        elif self.split is not None:
            raise ValueError("split only applies to the 'nslp' dataset")
        if self.only_with_context and not self.with_context:
            raise ValueError("only_with_context needs with_context = true")
        return self


class RunConfig(_Strict):
    """A whole ``eval`` config file."""

    run: RunSettings = Field(default_factory=RunSettings)
    classifiers: list[ClassifierSpec] = Field(min_length=1)
    datasets: list[DatasetSpec] = Field(min_length=1)

    @model_validator(mode="after")
    def _labels_unique(self) -> "RunConfig":
        for kind, entries in (("classifier", self.classifiers), ("dataset", self.datasets)):
            labels = [e.label for e in entries]
            repeated = sorted({label for label in labels if labels.count(label) > 1})
            if repeated:
                raise ValueError(f"duplicate {kind} labels: {', '.join(repeated)}")
        return self


def _merge_defaults(raw: dict[str, Any]) -> dict[str, Any]:
    """Applies ``[defaults]`` under each classifier (its own settings win; ``options`` merge key by key)."""
    defaults = raw.pop("defaults", None) or {}
    if not isinstance(defaults, dict):
        raise ConfigError("[defaults] must be a table")
    merged = []
    for entry in raw.get("classifiers") or []:
        if not isinstance(entry, dict):
            merged.append(entry)
            continue
        engine = entry.get("engine", defaults.get("engine", "llm"))
        # LLM settings are meaningless elsewhere, so they must not leak into other engines; only the transformer caches.
        inherited = {k: v for k, v in defaults.items() if k != "engine"}
        if engine == "transformer":
            inherited = {k: v for k, v in inherited.items() if k == "cache_path"}
        elif engine == "matcher":
            inherited = {}
        options = {**(inherited.pop("options", None) or {}), **(entry.get("options") or {})}
        merged.append({**inherited, **entry, "options": options})
    return {**raw, "classifiers": merged} if "classifiers" in raw else raw


def _describe(error: ValidationError) -> str:
    lines = []
    for item in error.errors():
        where = ".".join(str(part) for part in item["loc"]) or "config"
        lines.append(f"{where}: {item['msg']}")
    return "invalid config:\n  " + "\n  ".join(lines)


def load_run_config(path: str) -> tuple[RunConfig, str]:
    """Reads and validates a config file; returns it with its raw text (saved next to the run for reproducibility)."""
    file = Path(path)
    if not file.is_file():
        raise ConfigError(f"config file not found: {path}")
    text = file.read_text(encoding="utf-8")
    try:
        raw = tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"{path} is not valid TOML: {exc}") from exc
    try:
        return RunConfig.model_validate(_merge_defaults(raw)), text
    except ValidationError as exc:
        raise ConfigError(_describe(exc)) from exc


def is_paid(spec: ClassifierSpec) -> bool:
    """True when running the classifier can bill an API account (hosted LLM provider, or an unnamed default one)."""
    return spec.engine == "llm" and (spec.provider or "").lower() not in LOCAL_PROVIDERS


def build_dataset(spec: DatasetSpec) -> Any:
    """Builds the dataset, passing only the options the config set so the factories' own defaults apply otherwise."""
    from climafactskg.classifiers.cards import datasets

    options = spec.model_dump(exclude={"name", "label"}, exclude_none=True)
    return getattr(datasets, _DATASET_FACTORIES[spec.name])(**options)


def build_classifier(spec: ClassifierSpec) -> Any:
    """Builds the classifier named by the spec (imports its engine lazily)."""
    if spec.engine == "matcher":
        from climafactskg.classifiers.cards.matcher import CARDSMatcher

        return CARDSMatcher(**spec.options)
    if spec.engine == "transformer":
        from climafactskg.classifiers.cards.transformer import CARDSClassifier

        cache = {"cache_path": spec.cache_path} if spec.cache_path else {}
        return CARDSClassifier(**cache, **spec.options)

    from climafactskg.classifiers.cards.llm.classifier import CARDSLLMClassifier

    # TOML has no null, so "none" switches a preset's value off (e.g. top_p = "none").
    options = {k: None if v == "none" else v for k, v in spec.options.items()}
    kwargs: dict[str, Any] = {"use_preclassifier": spec.use_preclassifier, **options}
    for key, value in (
        ("provider", spec.provider),
        ("model", spec.model),
        ("cache_path", spec.cache_path),
        ("default_concurrency", spec.concurrency),
    ):
        if value is not None:
            kwargs[key] = value
    if spec.preset:
        return CARDSLLMClassifier.from_preset(spec.preset, **kwargs)
    return CARDSLLMClassifier(**kwargs)
