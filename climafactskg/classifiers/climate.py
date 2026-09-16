import numpy as np
import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer


class ClimateBertClassifier:
    """A classifier that uses a pre-trained ClimateBERT model to detect.

    if a given text is climate-related or not.
    """

    def __init__(self, model_name: str = "climatebert/distilroberta-base-climate-detector", device: str = None):
        """Initializes the ClimateBertClassifier with a pre-trained model.

        Args:
            model_name (str): The name of the Hugging Face model.
            device (str, optional): The device to run the model on ('cpu', 'cuda', 'mps').
                                   If None, it will attempt to detect the best available device.
        """
        self.model_name = model_name

        if device is None:
            if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                self.device = "mps"
            elif torch.cuda.is_available():
                self.device = "cuda"
            else:
                self.device = "cpu"
        else:
            self.device = device

        import transformers as _transformers

        _kwargs = {"local_files_only": True}
        try:
            self.tokenizer = AutoTokenizer.from_pretrained(model_name, **_kwargs)
            self.model = AutoModelForSequenceClassification.from_pretrained(model_name, **_kwargs)
        except OSError:
            # Model not in local cache yet — download it (first run only).
            _prev_verbosity = _transformers.logging.get_verbosity()
            _transformers.logging.set_verbosity_error()
            self.tokenizer = AutoTokenizer.from_pretrained(model_name)
            self.model = AutoModelForSequenceClassification.from_pretrained(model_name)
            _transformers.logging.set_verbosity(_prev_verbosity)
        self.model.to(self.device)
        self.model.eval()

        # Map of index to label (e.g., {0: 'unrelated', 1: 'climate-related'})
        self.labels = self.model.config.id2label

    def classify(self, text: str, context: str | None = None) -> str:
        """Predicts the class label for the input text.

        Args:
            text: The input text to classify.
            context: Optional fact-check context appended to the text before
                tokenisation. The tokenizer truncates the combined string to
                ``max_length=512`` tokens automatically.

        Returns:
            The predicted class label (e.g., ``'unrelated'`` or ``'related'``).
        """
        input_text = f"{text}\n\n{context}" if context else text
        probabilities = self.predict_proba(input_text)
        predicted_idx = np.argmax(probabilities)
        return self.labels[predicted_idx]

    def predict_proba(self, text: str) -> np.ndarray:
        """Predicts the probabilities for each class for the input text.

        Args:
            text (str): The input text to classify.


        Returns:
            np.ndarray: An array of probabilities for each class.
        """
        text = str(text).strip()
        if not text:
            # Return a default probability distribution if text is empty
            # Assuming the model has 2 classes (unrelated, climate-related)
            return np.array([1.0, 0.0])

        inputs = self.tokenizer(text, return_tensors="pt", truncation=True, padding=True, max_length=512).to(
            self.device
        )

        with torch.no_grad():
            outputs = self.model(**inputs)
            probabilities = torch.nn.functional.softmax(outputs.logits, dim=-1)
            return probabilities.cpu().numpy()[0]

    def classify_batch(self, texts: list[str], contexts: list[str | None] | None = None) -> list[str]:
        """Classifies multiple texts in a single forward pass.

        Args:
            texts: The input texts to classify.
            contexts: Optional per-item fact-check context. When provided, each
                context is appended to its corresponding text before tokenisation.
                Must be ``None`` or the same length as ``texts``.

        Returns:
            Predicted class labels in the same order as the input.
        """
        if contexts is not None:
            texts = [f"{t}\n\n{ctx}" if ctx else t for t, ctx in zip(texts, contexts)]
        texts = [str(t).strip() for t in texts]
        inputs = self.tokenizer(
            texts,
            return_tensors="pt",
            truncation=True,
            padding=True,
            max_length=512,
        ).to(self.device)

        with torch.no_grad():
            outputs = self.model(**inputs)
            preds = torch.argmax(outputs.logits, dim=1).cpu().tolist()
        return [self.labels[p] for p in preds]
