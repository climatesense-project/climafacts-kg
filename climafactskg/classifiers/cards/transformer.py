"""Two-stage transformer-based CARDS classifier (binary filter + 18-class taxonomy model)."""

import logging
from typing import Optional

from .base import CARDSClassifierBase
from .cache import ClassificationCache

try:
    import torch
    from transformers import AutoConfig, AutoModelForSequenceClassification, AutoTokenizer
except ImportError as e:
    raise ImportError(
        "The transformer CARDS classifier requires the 'transformer' extra. "
        "Install it with: pip install 'climafactskg[transformer]' "
        "(or: poetry install --extras transformer)."
    ) from e

MAX_LEN = 256
BINARY_MODEL_DIR = "crarojasca/BinaryAugmentedCARDS"
TAXONOMY_MODEL_DIR = "crarojasca/TaxonomyAugmentedCARDS"

# Maps the taxonomy model's output class index to its CARDS code.
# Index order is determined by the model training setup, not the taxonomy ordering.
_TRANSFORMER_ID2LABEL: dict[int, str] = {
    0: "1_1",
    1: "1_2",
    2: "1_3",
    3: "1_4",
    4: "1_6",
    5: "1_7",
    6: "2_1",
    7: "2_3",
    8: "3_1",
    9: "3_2",
    10: "3_3",
    11: "4_1",
    12: "4_2",
    13: "4_4",
    14: "4_5",
    15: "5_1",
    16: "5_2",
    17: "5_3",
}

logger = logging.getLogger(__name__)


class CARDSClassifier(CARDSClassifierBase):
    """CARDSClassifier: classifies text using the CARDS taxonomy via transformer models.

    Performs two-stage classification:
    1. A binary model filters out non-climate-misinformation text.
    2. A taxonomy model assigns one of 18 fine-grained CARDS codes.

    Supports single-item classification via ``classify()`` and efficient tensor-batched
    classification via ``classify_batch()``.

    Attributes:
        device (torch.device): Inference device (MPS, CUDA, or CPU).
        tokenizer: Shared tokenizer for both models.
        binary_model: Binary relevance classifier.
        taxonomy_model: 18-class CARDS taxonomy classifier.
        id2label (dict[int, str]): Mapping from taxonomy class index to CARDS code.

    Args:
        binary_model_dir (str): HuggingFace model path for the binary classifier.
        taxonomy_model_dir (str): HuggingFace model path for the taxonomy classifier.
        max_len (int): Maximum tokenisation sequence length.
        cache_path (str | None): Path to a Preserve SQLite cache for
            ``classify_batch`` results, keyed by
            ``hash(binary_model_dir|taxonomy_model_dir|max_len|text)`` — same
            file can be shared across collector sources (e.g. CimpleKG and
            ClimateSenseKG) so identical claim text is classified once. ``None``
            (default) disables caching.
    """

    def __init__(
        self,
        binary_model_dir: str = BINARY_MODEL_DIR,
        taxonomy_model_dir: str = TAXONOMY_MODEL_DIR,
        max_len: int = MAX_LEN,
        cache_path: Optional[str] = None,
    ):
        if torch.backends.mps.is_available():
            self.device = torch.device("mps")
        elif torch.cuda.is_available():
            self.device = torch.device("cuda")
        else:
            self.device = torch.device("cpu")

        self.max_len = max_len
        self.id2label = _TRANSFORMER_ID2LABEL
        fingerprint = f"transformer|{binary_model_dir}|{taxonomy_model_dir}|{max_len}"
        self._cache = ClassificationCache(cache_path, fingerprint=fingerprint)

        self.tokenizer = AutoTokenizer.from_pretrained(
            binary_model_dir,
            max_length=self.max_len,
            padding="max_length",
            return_token_type_ids=True,
        )

        config = AutoConfig.from_pretrained(binary_model_dir)
        self.binary_model = AutoModelForSequenceClassification.from_pretrained(binary_model_dir, config=config)
        self.binary_model.to(self.device)
        self.binary_model.eval()

        config = AutoConfig.from_pretrained(taxonomy_model_dir)
        self.taxonomy_model = AutoModelForSequenceClassification.from_pretrained(taxonomy_model_dir, config=config)
        self.taxonomy_model.to(self.device)
        self.taxonomy_model.eval()

    def classify(self, text: str, context: Optional[str] = None, skip_binary: bool = False) -> str:
        """Classifies a single text using the binary and taxonomy models.

        Args:
            text (str): The input text to classify.
            context (str, optional): Extra text (e.g. fact-check context) appended
                to *text* before classification. ``None`` (default) classifies
                *text* alone.
            skip_binary (bool): Skip the binary filter and run only the taxonomy model.

        Returns:
            str: A CARDS taxonomy code, or "0" if the binary model marks the text as irrelevant.
        """
        text = f"{text}\n\n{context}" if context else text
        text = text.strip()[: self.max_len]
        tokenized = self.tokenizer(text, return_tensors="pt")
        tokenized = {k: v.to(self.device) for k, v in tokenized.items()}

        with torch.no_grad():
            if skip_binary:
                outputs = self.taxonomy_model(**tokenized)
                pred = torch.argmax(outputs.logits, dim=1).to("cpu").item()
                return self.id2label[int(pred)]

            outputs = self.binary_model(**tokenized)
            binary_pred = torch.argmax(outputs.logits, dim=1).to("cpu").item()
            if binary_pred == 0:
                return "0"

            outputs = self.taxonomy_model(**tokenized)
            tax_pred = torch.argmax(outputs.logits, dim=1).to("cpu").item()
            return self.id2label[int(tax_pred)]

    def _classify_chunk(self, texts: list[str], skip_binary: bool) -> list[str]:
        """Runs one forward pass per model stage over a single chunk of texts."""
        tokenized = self.tokenizer(
            texts,
            return_tensors="pt",
            padding=True,
            truncation=True,
            max_length=self.max_len,
        )
        tokenized = {k: v.to(self.device) for k, v in tokenized.items()}

        with torch.no_grad():
            if skip_binary:
                outputs = self.taxonomy_model(**tokenized)
                preds = torch.argmax(outputs.logits, dim=1).cpu().tolist()
                return [self.id2label[p] for p in preds]

            # Binary pass on the full chunk
            binary_outputs = self.binary_model(**tokenized)
            binary_preds = torch.argmax(binary_outputs.logits, dim=1).cpu().tolist()

            results = ["0"] * len(texts)
            taxonomy_indices = [i for i, p in enumerate(binary_preds) if p != 0]

            if taxonomy_indices:
                sub_tokenized = {k: v[taxonomy_indices] for k, v in tokenized.items()}
                tax_outputs = self.taxonomy_model(**sub_tokenized)
                tax_preds = torch.argmax(tax_outputs.logits, dim=1).cpu().tolist()
                for result_pos, orig_idx in enumerate(taxonomy_indices):
                    results[orig_idx] = self.id2label[tax_preds[result_pos]]

            return results

    def classify_batch(
        self,
        texts: list[str],
        contexts: Optional[list[Optional[str]]] = None,
        skip_binary: bool = False,
        batch_size: int = 32,
    ) -> list[str]:
        """Classifies multiple texts in mini-batches, one forward pass per stage per chunk.

        Texts are split into chunks of *batch_size* so throughput scales on both
        CPU and GPU without tokenising/forwarding the entire input as one single
        (and, for large inputs, very slow and memory-heavy) batch. Only texts
        that pass the binary filter in a given chunk are sent to the taxonomy
        model. Progress is reported chunk-by-chunk via a rich progress bar.

        Args:
            texts (list[str]): Texts to classify.
            contexts (list[str | None], optional): Optional per-item context,
                same length as *texts* if given; each is appended to its text
                before classification.
            skip_binary (bool): Skip the binary filter; run only the taxonomy model.
            batch_size (int): Number of texts to tokenise/forward per chunk.

        Returns:
            list[str]: CARDS taxonomy codes in the same order as the input.
        """
        from rich.progress import track

        effective_contexts = contexts if contexts is not None else [None] * len(texts)
        texts = [(f"{t}\n\n{c}" if c else t).strip()[: self.max_len] for t, c in zip(texts, effective_contexts)]

        def _compute(pending: list[str]) -> list[str]:
            chunks = [pending[i : i + batch_size] for i in range(0, len(pending), batch_size)]
            computed: list[str] = []
            for chunk in track(chunks, description=f"Classifying [transformer, batch_size={batch_size}]"):
                computed.extend(self._classify_chunk(chunk, skip_binary))
            return computed

        return self._cache.get_or_compute(texts, key_fn=lambda t: f"{skip_binary}|{t}", compute_fn=_compute)
