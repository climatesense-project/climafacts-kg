import logging
from typing import Optional

import spacy
import torch
from rdflib import Graph
from spacy.tokens import Doc
from transformers import AutoConfig, AutoModelForSequenceClassification, AutoTokenizer

logging.basicConfig(level=logging.INFO)

MAX_LEN = 256
BINARY_MODEL_DIR = "crarojasca/BinaryAugmentedCARDS"
TAXONOMY_MODEL_DIR = "crarojasca/TaxonomyAugmentedCARDS"


@spacy.language.Language.component("clean_component")
def _clean_component(doc):
    """Cleans a spaCy Doc object by filtering out tokens based on specific criteria.

    This function removes tokens that are punctuation, currency symbols, digits, whitespace, stop words, numbers,
    or proper nouns. The remaining tokens are lemmatized, stripped, and lowercased, and a new Doc object is returned.

    Args:
        doc (spacy.tokens.Doc): The input spaCy Doc object to be cleaned.

    Returns:
        spacy.tokens.Doc: A new Doc object containing the cleaned and processed tokens.
    """
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


class CARDSMatcher:
    """CARDSMatcher is a classifier for categorizing text according to the CARDS taxonomy."""

    # add static class variable:
    taxonomy: list[dict] = [
        {
            "id": "0",
            "url": "https://purl.net/climafactskg/ns#0",
            "label": "Not climate misinformation or related to the climate.",
        },
        {
            "id": "1",
            "url": "https://purl.net/climafactskg/ns#1",
            "label": "Global warming is not happening",
        },
        {
            "id": "2",
            "url": "https://purl.net/climafactskg/ns#2",
            "label": "Human GHGs are not causing global warming",
        },
        {
            "id": "3",
            "url": "https://purl.net/climafactskg/ns#3",
            "label": "Climate impacts are not bad",
        },
        {
            "id": "4",
            "url": "https://purl.net/climafactskg/ns#4",
            "label": "Climate solutions won't work",
        },
        {
            "id": "5",
            "url": "https://purl.net/climafactskg/ns#5",
            "label": "Climate movement/science is unreliable",
        },
        {
            "id": "1_1",
            "url": "https://purl.net/climafactskg/ns#1_1",
            "label": "Ice isn't melting",
        },
        {
            "id": "1_2",
            "url": "https://purl.net/climafactskg/ns#1_2",
            "label": "Heading into ice age",
        },
        {
            "id": "1_3",
            "url": "https://purl.net/climafactskg/ns#1_3",
            "label": "Weather is cold",
        },
        {
            "id": "1_4",
            "url": "https://purl.net/climafactskg/ns#1_4",
            "label": "Hiatus in warming",
        },
        {
            "id": "1_5",
            "url": "https://purl.net/climafactskg/ns#1_5",
            "label": "Oceans are cooling",
        },
        {
            "id": "1_6",
            "url": "https://purl.net/climafactskg/ns#1_6",
            "label": "See level rise is exagerated",
        },
        {
            "id": "1_7",
            "url": "https://purl.net/climafactskg/ns#1_7",
            "label": "Extremes aren't increasing",
        },
        {
            "id": "1_8",
            "url": "https://purl.net/climafactskg/ns#1_8",
            "label": "Changed the name",
        },
        {
            "id": "2_1",
            "url": "https://purl.net/climafactskg/ns#2_1",
            "label": "It's natural cycles",
        },
        {
            "id": "2_2",
            "url": "https://purl.net/climafactskg/ns#2_2",
            "label": "Non-GHG forcings",
        },
        {
            "id": "2_3",
            "url": "https://purl.net/climafactskg/ns#2_3",
            "label": "No evidence for GHE",
        },
        {
            "id": "2_4",
            "url": "https://purl.net/climafactskg/ns#2_4",
            "label": "CO2 not rising",
        },
        {
            "id": "2_5",
            "url": "https://purl.net/climafactskg/ns#2_5",
            "label": "Emissions not raising CO2 levels",
        },
        {
            "id": "3_1",
            "url": "https://purl.net/climafactskg/ns#3_1",
            "label": "Sensitivity is low",
        },
        {
            "id": "3_2",
            "url": "https://purl.net/climafactskg/ns#3_2",
            "label": "No species impact",
        },
        {
            "id": "3_3",
            "url": "https://purl.net/climafactskg/ns#3_3",
            "label": "Not a pollutant",
        },
        {
            "id": "3_4",
            "url": "https://purl.net/climafactskg/ns#3_4",
            "label": "Only a few degrees",
        },
        {
            "id": "3_5",
            "url": "https://purl.net/climafactskg/ns#3_5",
            "label": "No link to conflict",
        },
        {
            "id": "3_6",
            "url": "https://purl.net/climafactskg/ns#3_6",
            "label": "No health impacts",
        },
        {
            "id": "4_1",
            "url": "https://purl.net/climafactskg/ns#4_1",
            "label": "Policies are harmful",
        },
        {
            "id": "4_2",
            "url": "https://purl.net/climafactskg/ns#4_2",
            "label": "Policies are ineffective",
        },
        {
            "id": "4_3",
            "url": "https://purl.net/climafactskg/ns#4_3",
            "label": "Too hard",
        },
        {
            "id": "4_4",
            "url": "https://purl.net/climafactskg/ns#4_4",
            "label": "Clean energy won't work",
        },
        {
            "id": "4_5",
            "url": "https://purl.net/climafactskg/ns#4_5",
            "label": "We need energy",
        },
        {
            "id": "5_1",
            "url": "https://purl.net/climafactskg/ns#5_1",
            "label": "Science is unreliable",
        },
        {
            "id": "5_2",
            "url": "https://purl.net/climafactskg/ns#5_2",
            "label": "Movement is unreliable",
        },
        {
            "id": "5_3",
            "url": "https://purl.net/climafactskg/ns#5_3",
            "label": "Climate is conspiracy",
        },
        {
            "id": "1_1_1",
            "url": "https://purl.net/climafactskg/ns#1_1_1",
            "label": "Antartica isn't melting",
        },
        {
            "id": "1_1_2",
            "url": "https://purl.net/climafactskg/ns#1_1_2",
            "label": "Greenland isn't melting",
        },
        {
            "id": "1_1_3",
            "url": "https://purl.net/climafactskg/ns#1_1_3",
            "label": "Artic isn't melting",
        },
        {
            "id": "1_1_4",
            "url": "https://purl.net/climafactskg/ns#1_1_4",
            "label": "Glaciers aren't vanishing",
        },
        {
            "id": "2_1_1",
            "url": "https://purl.net/climafactskg/ns#2_1_1",
            "label": "It's the sun",
        },
        {
            "id": "2_1_2",
            "url": "https://purl.net/climafactskg/ns#2_1_2",
            "label": "It's geological",
        },
        {
            "id": "2_1_3",
            "url": "https://purl.net/climafactskg/ns#2_1_3",
            "label": "It's the ocean",
        },
        {
            "id": "2_1_4",
            "url": "https://purl.net/climafactskg/ns#2_1_4",
            "label": "Past climate change",
        },
        {
            "id": "2_1_5",
            "url": "https://purl.net/climafactskg/ns#2_1_5",
            "label": "Tiny CO2 emissions",
        },
        {
            "id": "2_3_1",
            "url": "https://purl.net/climafactskg/ns#2_3_1",
            "label": "CO2 is trace gas",
        },
        {
            "id": "2_3_2",
            "url": "https://purl.net/climafactskg/ns#2_3_2",
            "label": "GHE is saturated",
        },
        {
            "id": "2_3_3",
            "url": "https://purl.net/climafactskg/ns#2_3_3",
            "label": "CO2 lags climate",
        },
        {
            "id": "2_3_4",
            "url": "https://purl.net/climafactskg/ns#2_3_4",
            "label": "Water vapor",
        },
        {
            "id": "2_3_5",
            "url": "https://purl.net/climafactskg/ns#2_3_5",
            "label": "Tropospheric hot spot",
        },
        {
            "id": "2_3_6",
            "url": "https://purl.net/climafactskg/ns#2_3_6",
            "label": "CO2 high in past",
        },
        {
            "id": "3_2_1",
            "url": "https://purl.net/climafactskg/ns#3_2_1",
            "label": "Species can adapt",
        },
        {
            "id": "3_2_2",
            "url": "https://purl.net/climafactskg/ns#3_2_2",
            "label": "Polar bears ok",
        },
        {
            "id": "3_2_3",
            "url": "https://purl.net/climafactskg/ns#3_2_3",
            "label": "Oceans are ok",
        },
        {
            "id": "3_3_1",
            "url": "https://purl.net/climafactskg/ns#3_3_1",
            "label": "CO2 is plant food",
        },
        {
            "id": "4_1_1",
            "url": "https://purl.net/climafactskg/ns#4_1_1",
            "label": "Policy increases costs",
        },
        {
            "id": "4_1_2",
            "url": "https://purl.net/climafactskg/ns#4_1_2",
            "label": "Policy weakens security",
        },
        {
            "id": "4_1_3",
            "url": "https://purl.net/climafactskg/ns#4_1_3",
            "label": "Policy harms environment",
        },
        {
            "id": "4_1_4",
            "url": "https://purl.net/climafactskg/ns#4_1_4",
            "label": "Rich future generations",
        },
        {
            "id": "4_1_5",
            "url": "https://purl.net/climafactskg/ns#4_1_5",
            "label": "Limits freedom",
        },
        {
            "id": "4_2_1",
            "url": "https://purl.net/climafactskg/ns#4_2_1",
            "label": "Green jobs don't work",
        },
        {
            "id": "4_2_2",
            "url": "https://purl.net/climafactskg/ns#4_2_2",
            "label": "Markets more efficient",
        },
        {
            "id": "4_2_3",
            "url": "https://purl.net/climafactskg/ns#4_2_3",
            "label": "Policy impact is negligible",
        },
        {
            "id": "4_2_4",
            "url": "https://purl.net/climafactskg/ns#4_2_4",
            "label": "One country is negligible",
        },
        {
            "id": "4_2_5",
            "url": "https://purl.net/climafactskg/ns#4_2_5",
            "label": "Better to adapt",
        },
        {
            "id": "4_2_6",
            "url": "https://purl.net/climafactskg/ns#4_2_6",
            "label": "China's emissions",
        },
        {
            "id": "4_2_7",
            "url": "https://purl.net/climafactskg/ns#4_2_7",
            "label": "Techno fix",
        },
        {
            "id": "4_3_1",
            "url": "https://purl.net/climafactskg/ns#4_3_1",
            "label": "Policy too difficult",
        },
        {
            "id": "4_3_2",
            "url": "https://purl.net/climafactskg/ns#4_3_2",
            "label": "Low public support",
        },
        {
            "id": "4_4_1",
            "url": "https://purl.net/climafactskg/ns#4_4_1",
            "label": "Clean energy unreliable",
        },
        {
            "id": "4_4_2",
            "url": "https://purl.net/climafactskg/ns#4_4_2",
            "label": "CCS is unproven",
        },
        {
            "id": "4_5_1",
            "url": "https://purl.net/climafactskg/ns#4_5_1",
            "label": "FF is plentiful",
        },
        {
            "id": "4_5_2",
            "url": "https://purl.net/climafactskg/ns#4_5_2",
            "label": "FF are cheap",
        },
        {
            "id": "4_5_3",
            "url": "https://purl.net/climafactskg/ns#4_5_3",
            "label": "Nuclear is good",
        },
        {
            "id": "5_1_1",
            "url": "https://purl.net/climafactskg/ns#5_1_1",
            "label": "No consensus",
        },
        {
            "id": "5_1_2",
            "url": "https://purl.net/climafactskg/ns#5_1_2",
            "label": "Proxies are unreliable",
        },
        {
            "id": "5_1_3",
            "url": "https://purl.net/climafactskg/ns#5_1_3",
            "label": "Temp is unreliable",
        },
        {
            "id": "5_1_4",
            "url": "https://purl.net/climafactskg/ns#5_1_4",
            "label": "Models are unreliable",
        },
        {
            "id": "5_2_1",
            "url": "https://purl.net/climafactskg/ns#5_2_1",
            "label": "Climate is religion",
        },
        {
            "id": "5_2_2",
            "url": "https://purl.net/climafactskg/ns#5_2_2",
            "label": "Media is alarmist",
        },
        {
            "id": "5_2_3",
            "url": "https://purl.net/climafactskg/ns#5_2_3",
            "label": "Politicians are biased",
        },
        {
            "id": "5_2_4",
            "url": "https://purl.net/climafactskg/ns#5_2_4",
            "label": "Environmentalists are alarmist",
        },
        {
            "id": "5_2_5",
            "url": "https://purl.net/climafactskg/ns#5_2_5",
            "label": "Scientist are biased",
        },
        {
            "id": "5_3_1",
            "url": "https://purl.net/climafactskg/ns#5_3_1",
            "label": "Policy is conspiracy",
        },
        {
            "id": "5_3_2",
            "url": "https://purl.net/climafactskg/ns#5_3_2",
            "label": "Science is conspiracy",
        },
    ]

    def __init__(self, cards_ttl: Optional[str] = None, format: Optional[str] = None):
        self._nlp = spacy.load("en_core_web_sm")
        self._nlp.add_pipe("clean_component", last=True)

        # Load the CARDS RDF if a file is provided:
        if cards_ttl != None and format != None:  # noqa: E711
            cards_g = Graph()
            cards_g.parse(cards_ttl, format=format, encoding="utf-8")

            # Query the graph to get the taxonomy
            query = """
            PREFIX cf: <https://purl.net/climafactskg/ns#>
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

    def clean(self, text: str) -> str:
        """Cleans the input text by removing punctuation, digits, stop words, and other non-informative tokens.

        Args:
            text (str): The input text to be cleaned.

        Returns:
            str: The cleaned text.
        """
        doc = self._nlp(text)
        return doc.text

    def jaccard_similarity(self, text1: str, text2: str):
        """Calculates the Jaccard similarity between two input strings.

        Args:
            text1 (str): The first input string.
            text2 (str): The second input string.

        Returns:
            float: The Jaccard similarity coefficient between the two input strings,
                ranging from 0.0 (no similarity) to 1.0 (identical sets).
        """
        text1_set = set(self.clean(text1).split())
        text2_set = set(self.clean(text2).split())

        intersection = len(text1_set.intersection(text2_set))
        union = (len(text1_set) + len(text2_set)) - intersection
        return float(intersection) / union

    def classify(self, text: str, min_threshold: float = 0.25) -> str:
        """Classifies the input text using the CARDS taxonomy.

        Args:
            text (str): The input text to classify.
            min_threshold (float): The minimum Jaccard similarity threshold required to assign a category.

        Returns:
            str: The predicted label from the CARDS taxonomy.
        """
        cleaned_text = self.clean(text)

        highest_similarity = 0.0
        matched_category_id = "0"  # Default to "Not climate misinformation"
        for category in self.taxonomy:
            cleaned_category_label = self.clean(category["label"])
            sim = self.jaccard_similarity(cleaned_text, cleaned_category_label)
            logging.debug(f"Comparing '{cleaned_text}' with '{cleaned_category_label}' - Jaccard similarity: {sim}")

            if sim > highest_similarity:
                highest_similarity = sim
                matched_category_id = category["id"]

        if highest_similarity >= min_threshold:
            return matched_category_id
        else:
            logging.info(
                f"No match found for '{cleaned_text}' with threshold {min_threshold}. Returning default category."
            )
            return "0"


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

        prediction = "0" if binary_prediction == 0 else self.id2label[int(taxonomy_prediction)]
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
