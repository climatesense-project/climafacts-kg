"""Tests for the eval config: schema, defaults, validation, cost classification and the builders (offline)."""

import pytest
from climafactskg.classifiers.cards import runconfig
from climafactskg.classifiers.cards.runconfig import ConfigError, is_paid, load_run_config

MINIMAL = """
[[classifiers]]
label = "gpt"
model = "openai/gpt-4o-mini"

[[datasets]]
name = "climatesense_v2"
"""


def _write(tmp_path, text, name="eval.toml"):
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return str(path)


class TestLoading:
    def test_a_minimal_config_gets_sensible_defaults(self, tmp_path):
        config, text = load_run_config(_write(tmp_path, MINIMAL))

        assert text == MINIMAL
        assert config.run.save_dir == "data/eval_runs"
        assert config.run.context_modes == ["none", "with"]
        assert config.run.category_scores == "all"
        assert config.classifiers[0].engine == "llm" and config.classifiers[0].model == "openai/gpt-4o-mini"
        assert config.datasets[0].label == "climatesense_v2"  # the label defaults to the dataset name

    def test_defaults_apply_to_classifiers_and_classifier_settings_win(self, tmp_path):
        text = """
[defaults]
provider = "openrouter"
preset = "xplainnlp-nslp"
concurrency = 8
[defaults.options]
temperature = 0.0
top_p = 0.9

[[classifiers]]
label = "a"
model = "m1"

[[classifiers]]
label = "b"
model = "m2"
concurrency = 2
[classifiers.options]
top_p = 1.0

[[datasets]]
name = "nslp"
"""
        config, _ = load_run_config(_write(tmp_path, text))
        a, b = config.classifiers

        assert (a.provider, a.preset, a.concurrency) == ("openrouter", "xplainnlp-nslp", 8)
        assert b.concurrency == 2 and b.provider == "openrouter"
        assert a.options == {"temperature": 0.0, "top_p": 0.9}
        assert b.options == {"temperature": 0.0, "top_p": 1.0}  # options merge key by key

    def test_llm_only_defaults_do_not_leak_into_other_engines(self, tmp_path):
        text = """
[defaults]
provider = "openrouter"
concurrency = 8

[[classifiers]]
label = "free-baseline"
engine = "matcher"

[[datasets]]
name = "nslp"
"""
        config, _ = load_run_config(_write(tmp_path, text))

        assert config.classifiers[0].engine == "matcher" and config.classifiers[0].provider is None

    def test_the_same_dataset_can_appear_twice_with_distinct_labels(self, tmp_path):
        text = (
            MINIMAL
            + """
[[datasets]]
name = "climatesense_v2"
label = "v2-with-context"
with_context = true
"""
        )
        config, _ = load_run_config(_write(tmp_path, text))
        assert [d.label for d in config.datasets] == ["climatesense_v2", "v2-with-context"]


class TestValidation:
    def _error(self, tmp_path, text):
        with pytest.raises(ConfigError) as info:
            load_run_config(_write(tmp_path, text))
        return str(info.value)

    def test_a_typo_in_a_key_is_reported_with_its_name(self, tmp_path):
        message = self._error(tmp_path, MINIMAL.replace('model = "openai/gpt-4o-mini"', 'modle = "x"'))
        assert "modle" in message

    def test_an_unknown_section_is_an_error(self, tmp_path):
        assert "extras" in self._error(tmp_path, MINIMAL + "\n[extras]\nfoo = 1\n")

    def test_duplicate_labels_are_errors(self, tmp_path):
        text = MINIMAL + '\n[[classifiers]]\nlabel = "gpt"\nmodel = "x"\n'
        assert "duplicate" in self._error(tmp_path, text).lower()
        assert "duplicate" in self._error(tmp_path, MINIMAL + '\n[[datasets]]\nname = "climatesense_v2"\n').lower()

    def test_at_least_one_classifier_and_one_dataset_are_required(self, tmp_path):
        assert "classifiers" in self._error(tmp_path, '[[datasets]]\nname = "nslp"\n')
        assert "datasets" in self._error(tmp_path, '[[classifiers]]\nlabel = "a"\nmodel = "m"\n')

    def test_llm_settings_on_a_non_llm_classifier_are_an_error(self, tmp_path):
        text = '[[classifiers]]\nlabel = "t"\nengine = "transformer"\nmodel = "x"\n[[datasets]]\nname = "nslp"\n'
        assert "model" in self._error(tmp_path, text)

    def test_dataset_options_must_belong_to_that_dataset(self, tmp_path):
        base = '[[classifiers]]\nlabel = "a"\nmodel = "m"\n'
        assert "split" in self._error(tmp_path, base + '[[datasets]]\nname = "climatesense_v2"\nsplit = "test"\n')
        assert "with_context" in self._error(tmp_path, base + '[[datasets]]\nname = "nslp"\nwith_context = true\n')

    def test_only_with_context_needs_context_to_be_enabled(self, tmp_path):
        text = (
            '[[classifiers]]\nlabel = "a"\nmodel = "m"\n'
            '[[datasets]]\nname = "climatesense_v2"\nonly_with_context = true\n'
        )
        assert "only_with_context" in self._error(tmp_path, text)

    def test_bad_values_are_errors(self, tmp_path):
        assert "context_modes" in self._error(tmp_path, '[run]\ncontext_modes = ["sometimes"]\n' + MINIMAL)
        assert "limit" in self._error(tmp_path, MINIMAL.replace('name = "climatesense_v2"', 'name = "nslp"\nlimit = 0'))

    def test_a_missing_or_broken_file_is_a_clear_error(self, tmp_path):
        with pytest.raises(ConfigError, match="not found"):
            load_run_config(str(tmp_path / "nope.toml"))
        with pytest.raises(ConfigError, match="TOML"):
            load_run_config(_write(tmp_path, "this is = not [valid toml"))


class TestPaidClassification:
    def _spec(self, tmp_path, body):
        config, _ = load_run_config(_write(tmp_path, body + '\n[[datasets]]\nname = "nslp"\n'))
        return config.classifiers[0]

    def test_hosted_llm_providers_are_paid(self, tmp_path):
        for provider in ("openrouter", "openai", "anthropic"):
            spec = self._spec(tmp_path, f'[[classifiers]]\nlabel = "a"\nmodel = "m"\nprovider = "{provider}"\n')
            assert is_paid(spec)

    def test_local_engines_and_providers_are_free(self, tmp_path):
        for provider in ("ollama", "lmstudio"):
            spec = self._spec(tmp_path, f'[[classifiers]]\nlabel = "a"\nmodel = "m"\nprovider = "{provider}"\n')
            assert not is_paid(spec)
        for engine in ("transformer", "matcher"):
            assert not is_paid(self._spec(tmp_path, f'[[classifiers]]\nlabel = "a"\nengine = "{engine}"\n'))


class TestBuilders:
    def test_datasets_are_built_with_only_the_options_that_were_set(self, tmp_path, monkeypatch):
        seen = {}
        monkeypatch.setattr(
            "climafactskg.classifiers.cards.datasets.climatesense_dataset_v2",
            lambda **kwargs: seen.update(kwargs) or "ds",
        )
        text = MINIMAL.replace(
            'name = "climatesense_v2"',
            'name = "climatesense_v2"\nlimit = 20\nwith_context = true\nmax_context_chars = 400',
        )
        config, _ = load_run_config(_write(tmp_path, text))

        assert runconfig.build_dataset(config.datasets[0]) == "ds"
        assert seen == {"limit": 20, "with_context": True, "max_context_chars": 400}

    def test_an_llm_classifier_with_a_preset_goes_through_from_preset(self, tmp_path, monkeypatch):
        from climafactskg.classifiers.cards.llm.classifier import CARDSLLMClassifier

        seen = {}

        def fake_from_preset(cls, name, **kwargs):
            seen.update(name=name, **kwargs)
            return "clf"

        monkeypatch.setattr(CARDSLLMClassifier, "from_preset", classmethod(fake_from_preset))
        text = """
[defaults]
provider = "openrouter"
preset = "xplainnlp-nslp"
cache_path = "cache.db"
concurrency = 4
[defaults.options]
temperature = 0.0

[[classifiers]]
label = "a"
model = "m"

[[datasets]]
name = "nslp"
"""
        config, _ = load_run_config(_write(tmp_path, text))

        assert runconfig.build_classifier(config.classifiers[0]) == "clf"
        assert seen == {
            "name": "xplainnlp-nslp",
            "provider": "openrouter",
            "model": "m",
            "use_preclassifier": False,
            "cache_path": "cache.db",
            "default_concurrency": 4,
            "temperature": 0.0,
        }

    def test_the_label_names_the_config_in_the_results(self, tmp_path):
        config, _ = load_run_config(_write(tmp_path, MINIMAL))
        assert config.classifiers[0].label == "gpt"


def test_the_string_none_in_options_means_python_none(tmp_path, monkeypatch):
    # TOML has no null, but a preset's top_p/max_tokens can only be switched off by passing None.
    from climafactskg.classifiers.cards.llm.classifier import CARDSLLMClassifier

    seen = {}
    monkeypatch.setattr(
        CARDSLLMClassifier, "from_preset", classmethod(lambda cls, name, **kw: seen.update(kw) or "clf")
    )
    text = MINIMAL.replace(
        "\n[[datasets]]", '\npreset = "p"\noptions = { top_p = "none", temperature = 0.0 }\n[[datasets]]'
    )
    config, _ = load_run_config(_write(tmp_path, text))

    runconfig.build_classifier(config.classifiers[0])

    assert seen["top_p"] is None and seen["temperature"] == 0.0


def test_category_scores_must_be_a_known_value(tmp_path):
    with pytest.raises(ConfigError, match="category_scores"):
        load_run_config(_write(tmp_path, '[run]\ncategory_scores = "some"\n' + MINIMAL))


def test_a_default_engine_applies_to_classifiers_that_do_not_set_one(tmp_path):
    text = """
[defaults]
engine = "transformer"
cache_path = "c.db"
provider = "openrouter"

[[classifiers]]
label = "a"

[[classifiers]]
label = "b"
engine = "matcher"

[[datasets]]
name = "nslp"
"""
    config, _ = load_run_config(_write(tmp_path, text))
    a, b = config.classifiers

    assert (a.engine, a.cache_path, a.provider) == ("transformer", "c.db", None)  # llm-only defaults do not leak
    assert (b.engine, b.cache_path) == ("matcher", None)
    assert not is_paid(a)  # it used to become a paid LLM classifier


def test_peek_builds_an_llm_classifier_without_the_preclassifier_gate(tmp_path, monkeypatch):
    from climafactskg.classifiers.cards.llm.classifier import CARDSLLMClassifier

    seen = {}
    monkeypatch.setattr(
        CARDSLLMClassifier, "from_preset", classmethod(lambda cls, name, **kw: seen.update(kw) or "clf")
    )
    text = MINIMAL.replace("\n[[datasets]]", '\npreset = "p"\nuse_preclassifier = true\n[[datasets]]')
    config, _ = load_run_config(_write(tmp_path, text))

    runconfig.build_classifier(config.classifiers[0])
    assert seen["use_preclassifier"] is True
    runconfig.build_classifier(config.classifiers[0], peek=True)  # only reads the cache: must not load ClimateBERT
    assert seen["use_preclassifier"] is False


class TestModelSizeFields:
    def _spec(self, tmp_path, extra):
        text = MINIMAL.replace('model = "openai/gpt-4o-mini"', f'model = "openai/gpt-4o-mini"\n{extra}')
        return load_run_config(_write(tmp_path, text))[0].classifiers[0]

    def test_size_and_active_size_are_optional_numbers_in_billions(self, tmp_path):
        spec = self._spec(tmp_path, "size_b = 235\nactive_b = 22")
        assert (spec.size_b, spec.active_b) == (235.0, 22.0)
        assert (self._spec(tmp_path, "").size_b, self._spec(tmp_path, "").active_b) == (None, None)

    def test_sizes_must_be_positive_and_active_cannot_exceed_total(self, tmp_path):
        for extra in ("size_b = 0", "size_b = -3", "size_b = 10\nactive_b = 20"):
            with pytest.raises(ConfigError):
                self._spec(tmp_path, extra)

    def test_a_non_llm_classifier_may_state_its_size(self, tmp_path):
        text = '[[classifiers]]\nlabel = "t"\nengine = "transformer"\nsize_b = 0.2\n[[datasets]]\nname = "nslp"\n'
        assert load_run_config(_write(tmp_path, text))[0].classifiers[0].size_b == 0.2
