"""Rule-based CARDS classifier using Jaccard similarity over spaCy-lemmatised text."""

import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Iterable, Optional

import spacy
from rdflib import Graph
from spacy.tokens import Doc

from .base import CARDSClassifierBase
from .taxonomy import TAXONOMY

logger = logging.getLogger(__name__)


def _clean_component(doc: Doc) -> Doc:
    """Cleans a spaCy Doc by removing punctuation, currency, digits, whitespace, stop words, numbers, and proper nouns. Remaining tokens are lemmatized and lowercased.

    Args:
        doc (Doc): The input spaCy Doc to clean.

    Returns:
        Doc: A new Doc containing the cleaned tokens.
    """  # noqa: E501
    filtered_tokens = [
        token
        for token in doc
        if (
            not token.is_punct
            and not token.is_currency
            and not token.is_digit
            and not token.is_space
            and not token.is_stop
            and not token.like_num
            and not token.pos_ == "PROPN"
        )
    ]
    return Doc(doc.vocab, words=[token.lemma_.strip().lower() for token in filtered_tokens])


# Register the component; force=True prevents errors on repeated module imports in tests.
if not spacy.language.Language.has_factory("clean_component"):
    spacy.language.Language.component("clean_component", func=_clean_component)


class CARDSMatcher(CARDSClassifierBase):
    """CARDSMatcher: classifies text against the CARDS taxonomy using Jaccard similarity.

    By default uses the built-in 61-entry taxonomy. Pass a CARDS RDF/TTL file to
    override it with a custom taxonomy loaded via SPARQL.
    """

    taxonomy: list[dict] = TAXONOMY

    def __init__(self, cards_ttl: Optional[str] = None, format: Optional[str] = None):
        self._nlp = spacy.load("en_core_web_sm")
        self._nlp.add_pipe("clean_component", last=True)

        if cards_ttl is not None and format is not None:
            cards_g = Graph()
            cards_g.parse(cards_ttl, format=format, encoding="utf-8")

            query = """
            PREFIX cf: <https://purl.net/climatesense/cards/ns#>
            PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
            SELECT DISTINCT ?c ?label WHERE {
                ?c a skos:Concept;
                    skos:inScheme cf:CARDS ;
                    skos:prefLabel ?label
            }
            """

            results = cards_g.query(query)
            self.taxonomy = []
            if hasattr(results, "__iter__"):
                for row in results:
                    if isinstance(row, (list, tuple)) and len(row) >= 2:
                        self.taxonomy.append(
                            {
                                "id": str(row[0]).split("#")[-1],
                                "url": str(row[0]),
                                "label": str(row[1]),
                            }
                        )

        # Taxonomy labels are static, but `classify()` re-compares every input
        # text against all of them — clean and tokenize each label once here
        # instead of re-running the spaCy pipeline on the same ~90 labels
        # (and, via `jaccard_similarity`, running it *again* on the already-
        # cleaned label/text on every comparison) for every call.
        self._cleaned_labels: dict[str, str] = {
            category["id"]: self.clean(category["label"]) for category in self.taxonomy
        }
        self._label_tokens: dict[str, frozenset[str]] = {
            cat_id: frozenset(label.split()) for cat_id, label in self._cleaned_labels.items()
        }

    def clean(self, text: str) -> str:
        """Cleans the input text by passing it through the spaCy pipeline.

        Args:
            text (str): The input text to clean.

        Returns:
            str: The cleaned text.
        """
        doc = self._nlp(text)
        return doc.text

    def jaccard_similarity(self, text1: str, text2: str) -> float:
        """Calculates the Jaccard similarity between two strings.

        Args:
            text1 (str): The first input string.
            text2 (str): The second input string.

        Returns:
            float: Jaccard similarity coefficient between 0.0 and 1.0.
        """
        text1_set = set(self.clean(text1).split())
        text2_set = set(self.clean(text2).split())
        return self._jaccard_from_tokens(text1_set, text2_set)

    @staticmethod
    def _jaccard_from_tokens(tokens1: Iterable[str], tokens2: Iterable[str]) -> float:
        """Jaccard similarity between two already-cleaned, already-tokenized token sets."""
        set1, set2 = set(tokens1), set(tokens2)
        intersection = len(set1 & set2)
        union = len(set1) + len(set2) - intersection
        return float(intersection) / union if union > 0 else 0.0

    def classify(self, text: str, context: Optional[str] = None, min_threshold: float = 0.25) -> str:
        """Classifies a single text against the CARDS taxonomy using Jaccard similarity.

        Args:
            text (str): The input text to classify.
            context (str, optional): Extra text (e.g. fact-check context) appended
                to *text* before matching. ``None`` (default) matches on *text* alone.
            min_threshold (float): Minimum Jaccard similarity required to assign a category.

        Returns:
            str: The predicted CARDS taxonomy code, or "0" if no match exceeds the threshold.
        """
        text = f"{text}\n\n{context}" if context else text
        cleaned_text = self.clean(text)
        text_tokens = set(cleaned_text.split())

        highest_similarity = 0.0
        matched_category_id = "0"
        for category in self.taxonomy:
            sim = self._jaccard_from_tokens(text_tokens, self._label_tokens[category["id"]])
            logger.debug(
                "Comparing %r with %r — Jaccard: %.4f", cleaned_text, self._cleaned_labels[category["id"]], sim
            )
            if sim > highest_similarity:
                highest_similarity = sim
                matched_category_id = category["id"]

        if highest_similarity >= min_threshold:
            return matched_category_id

        logger.info(
            "No match found for %r with threshold %.2f. Returning default category.",
            cleaned_text,
            min_threshold,
        )
        return "0"

    def classify_batch(
        self,
        texts: list[str],
        contexts: Optional[list[Optional[str]]] = None,
        min_threshold: float = 0.25,
        max_workers: Optional[int] = None,
    ) -> list[str]:
        """Classifies multiple texts in parallel using a thread pool.

        spaCy releases the GIL during tokenization, so threads provide real
        concurrency for CPU-bound Jaccard computation.

        Args:
            texts (list[str]): Texts to classify.
            contexts (list[str | None], optional): Optional per-item context,
                same length as *texts* if given.
            min_threshold (float): Minimum Jaccard similarity threshold.
            max_workers (int | None): Maximum number of threads. Defaults to
                ``min(32, os.cpu_count() + 4)`` (ThreadPoolExecutor default).

        Returns:
            list[str]: CARDS taxonomy codes in the same order as the input.
        """
        effective_contexts = contexts if contexts is not None else [None] * len(texts)
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            return list(
                executor.map(
                    lambda pair: self.classify(pair[0], context=pair[1], min_threshold=min_threshold),
                    zip(texts, effective_contexts),
                )
            )
