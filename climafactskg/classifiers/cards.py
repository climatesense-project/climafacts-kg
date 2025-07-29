import torch
from transformers import AutoConfig, AutoModelForSequenceClassification, AutoTokenizer

MAX_LEN = 256
BINARY_MODEL_DIR = "crarojasca/BinaryAugmentedCARDS"
TAXONOMY_MODEL_DIR = "crarojasca/TaxonomyAugmentedCARDS"


class CARDSClassifier:
    """CARDSClassifier: A classifier for categorizing text using the CARDS taxonomy classifier.

    The classifier first determines if the input text is relevant using the binary model, and if so,
    assigns a taxonomy label using the taxonomy model.

    Attributes:
        device (torch.device): The device (CPU, CUDA, or MPS) on which models are loaded and inference is performed.
        tokenizer (transformers.PreTrainedTokenizer): Tokenizer for preprocessing input text.
        binary_model (transformers.PreTrainedModel): Model for binary classification.
        taxonomy_model (transformers.PreTrainedModel): Model for taxonomy classification.
        id2label (dict): Mapping from taxonomy class indices to label strings.

    Args:
        binary_model_dir (str): Path to the directory containing the binary classification model.
        taxonomy_model_dir (str): Path to the directory containing the taxonomy classification model.
        max_len (int): Maximum sequence length for tokenization.

    Methods:
        classify(text: str) -> str:
            Classifies the input text. Returns "0_0" if the binary classifier predicts negative,
            otherwise returns the taxonomy label corresponding to the taxonomy classifier's prediction.
    """

    def __init__(
        self,
        binary_model_dir: str = BINARY_MODEL_DIR,
        taxonomy_model_dir: str = TAXONOMY_MODEL_DIR,
        max_len: int = MAX_LEN,
    ):
        # Set device to GPU if available, if no GPU check if MPS is available, otherwise CPU
        if torch.backends.mps.is_available():
            self.device = torch.device("mps")
        elif torch.cuda.is_available():
            self.device = torch.device("cuda")
        else:
            self.device = torch.device("cpu")

        self.max_len = max_len

        self.tokenizer = AutoTokenizer.from_pretrained(
            binary_model_dir,
            max_length=self.max_len,
            padding="max_length",
            return_token_type_ids=True,
        )

        # Load Binary Model
        config = AutoConfig.from_pretrained(binary_model_dir)
        self.binary_model = AutoModelForSequenceClassification.from_pretrained(binary_model_dir, config=config)
        self.binary_model.to(self.device)
        self.binary_model.eval()

        # Load Taxonomy Model
        config = AutoConfig.from_pretrained(taxonomy_model_dir)
        self.taxonomy_model = AutoModelForSequenceClassification.from_pretrained(taxonomy_model_dir, config=config)
        self.taxonomy_model.to(self.device)
        self.taxonomy_model.eval()

        self.id2label = {
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

    def classify(self, text: str) -> str:
        """Classifies the input text using pre-loaded binary and taxonomy classification models.

        The method performs two-stage classification:
        1. Binary classification to determine if the text belongs to a specific class (e.g., relevant/irrelevant).
        2. If the binary classifier predicts a positive class, a taxonomy classifier assigns a more specific label.

        Args:
            text (str): The input text to classify.

        Returns:
            str: The predicted label. Returns "0_0" if the binary classifier predicts the negative class,
                otherwise returns the taxonomy label corresponding to the predicted class.
        """
        text = text.strip()[: self.max_len]  # Ensure text is not longer than MAX_LEN
        tokenized_text = self.tokenizer(text, return_tensors="pt")
        tokenized_text = {k: v.to(self.device) for k, v in tokenized_text.items()}

        with torch.no_grad():
            # Binary classification
            outputs = self.binary_model(**tokenized_text)
            binary_prediction = torch.argmax(outputs.logits, dim=1)
            binary_prediction = binary_prediction.to("cpu").item()

            # Taxonomy classification
            outputs = self.taxonomy_model(**tokenized_text)
            taxonomy_prediction = torch.argmax(outputs.logits, dim=1)
            taxonomy_prediction = taxonomy_prediction.to("cpu").item()

        prediction = "0_0" if binary_prediction == 0 else self.id2label[int(taxonomy_prediction)]
        return prediction


def cards_classification(text: str) -> str:
    """Legacy function for single-use classification."""
    classifier = CARDSClassifier()
    return classifier.classify(text)


if __name__ == "__main__":
    from dotenv import load_dotenv
    from rich.progress import track
    from tinydb import JSONStorage, TinyDB
    from tinydb_serialization import SerializationMiddleware
    from tinydb_serialization.serializers import DateTimeSerializer

    load_dotenv()
    serialization = SerializationMiddleware(JSONStorage)
    serialization.register_serializer(DateTimeSerializer(), "TinyDate")

    with TinyDB("data/skepticalscience_arguments_db.json", storage=serialization) as db:
        db.default_table_name = "arguments"
        classifier = CARDSClassifier()

        for argument in track(db.all(), description="Classifying arguments..."):
            if "cards_category" in argument and argument["lang"] != "en":
                db.update({"cards_category": None}, doc_ids=[argument.doc_id])
            elif (
                "cards_category" not in argument
                and argument["climate_myth"] != None  # noqa: E711
                and argument["lang"] == "en"
            ):
                text = argument["climate_myth"]

                # print(argument.doc_id, text)
                prediction = classifier.classify(text)
                db.update({"cards_category": prediction}, doc_ids=[argument.doc_id])
                # print(
                #     f"Updated classification for argument {argument.doc_id}: {prediction}"
                # )
        print("All arguments classified.")
