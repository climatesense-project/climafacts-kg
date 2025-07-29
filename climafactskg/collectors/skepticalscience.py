import logging
from typing import Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from rich.progress import track
from tinydb import Query, TinyDB

from climafactskg.classifiers.cards import CARDSClassifier
from climafactskg.parsers.skepticalscience import (
    parse_main_article,
    parse_translated_article,
)
from climafactskg.utils import fetch_url_content

logging.basicConfig(level=logging.INFO)


def fetch_arguments_urls(ignore_urls: Optional[list] = None) -> list:
    """Fetch a list of argument URLs from various pages on the Skeptical Science website.

    This function extracts URLs from the following pages:
    1. The main list of arguments (https://skepticalscience.com/argument.php).
    2. The short URLs list (https://skepticalscience.com/shorturls.php).
    3. The fixed number list (https://skepticalscience.com/fixednum.php).
    4. The taxonomy list (https://skepticalscience.com/argument.php?f=taxonomy).

    Args:
        ignore_urls (list, optional): A list of URLs to exclude from the results. Defaults to None.

    Returns:
        list: A sorted list of unique argument URLs, excluding any ignored URLs if provided.
    """
    arguments_urls = []

    # 1) Extract from the main list:
    url = "https://skepticalscience.com/argument.php"
    content = fetch_url_content(url)
    soup = BeautifulSoup(content, "html.parser")
    arguments_urls = [urljoin(url, str(a["href"])) for a in soup.select("#mainbody table a")]

    # 2) Extract from the shorturls list:
    url = "https://skepticalscience.com/shorturls.php"
    content = fetch_url_content(url)
    soup = BeautifulSoup(content, "html.parser")
    arguments_urls += [urljoin(url, str(a["href"])) for a in soup.select("#centerColumn table a")]

    # 3) Extract from the fixednum list:
    url = "https://skepticalscience.com/fixednum.php"
    content = fetch_url_content(url)
    soup = BeautifulSoup(content, "html.parser")
    arguments_urls += [urljoin(url, str(a["href"])) for a in soup.select("#centerColumn table a")]

    # 4) Extract from the taxonomy list:
    url = "https://skepticalscience.com/argument.php?f=taxonomy"
    content = fetch_url_content(url)
    soup = BeautifulSoup(content, "html.parser")
    arguments_urls += [urljoin(url, str(a["href"])) for a in soup.select("#mainbody ul a")]

    arguments_urls = list(set(arguments_urls))  # Remove duplicates

    # Remove ignored URLs if provided:
    if ignore_urls:
        arguments_urls = [url for url in arguments_urls if url not in ignore_urls]

    # Sort the URLs:
    arguments_urls.sort()

    return arguments_urls


def process_urls(db: TinyDB, urls: list[str], ignore_urls: Optional[list] = None) -> None:
    """Processes a list of URLs by parsing articles, and storing the results in a TinyDB database.
    Also processes nested article levels and translated language versions if available.

        db (TinyDB): The TinyDB database instance where articles and related data will be stored.
        urls (list[str]): List of URLs to process.
        ignore_urls (Optional[list], optional): List of URLs to ignore during processing. Defaults to None.

        1. Filters out URLs present in `ignore_urls`.
            - Fetches the content.
            - Processes and stores articles for each nested level URL, if present.
            - Processes and stores articles for each translated language version, if present.

        - Assumes the existence of helper functions: `fetch_url_content`, `parse_main_article`,
            and `parse_translated_article`.
        - Uses TinyDB's `upsert` to update or insert articles based on their URL.

        Any exceptions raised by helper functions or database operations will propagate to the caller.
    """  # noqa: D205
    if ignore_urls is None:
        ignore_urls = []

    urls = [url for url in urls if url not in ignore_urls]

    logging.info(f"Processing {len(urls)} URLs.")

    for i, main_url in enumerate(urls, start=1):
        logging.info(f"Processing URL {i}/{len(urls)}: {main_url}")
        content = fetch_url_content(main_url)

        article = parse_main_article(main_url, content)

        # Store the article in TinyDB
        db.upsert(article, Query().url == main_url)
        logging.info(f"Stored article for URL: {main_url}")

        # Process the article levels:
        logging.info(f"Processing levels for URL {i}/{len(urls)}: {main_url}")
        if "levels" in article:
            for level in article["levels"]:
                logging.info(f"Processing level: {level['level']}")

                for level_url in level["urls"]:
                    logging.info(f"Processing level URL: {level_url}")
                    # Parse the main article for each level URL
                    level_article = parse_main_article(level_url)

                    # Store the article in TinyDB
                    db.upsert(level_article, Query().url == level_url)
                    logging.info(f"Stored level article for URL: {level_url}")

                logging.info(f"Finished level: {level['level']}")

        if "languages" in article:
            for lang in article["languages"]:
                logging.info(f"Processing language : {lang['lang']}")

                logging.info(f"Processing language URL: {lang['url']}")
                lang_article = parse_translated_article(lang["url"], language_code=lang["code"])

                # Store the  article in TinyDB
                db.upsert(lang_article, Query().url == lang["url"])
                logging.info(f"Stored translated article for language URL: {lang['url']}")

                logging.info(f"Finished language: {lang['lang']}")

        logging.info(f"Finished processing URL {i}/{len(urls)}: {main_url}")


def classify_urls(db: TinyDB) -> None:
    """Classifies arguments in the TinyDB database using the CARDSClassifier.

    This function iterates over all arguments in the provided TinyDB instance.
    - If an argument has a "cards_category" and its language is not English ("en"),
        the "cards_category" is reset to None.
    - If an argument does not have a "cards_category", has a non-None "climate_myth", and its language is English,
        the function uses the CARDSClassifier to predict a category for the "climate_myth" text and updates the argument
        with this prediction.

    Args:
        db (TinyDB): The TinyDB database instance containing arguments to classify.

    Returns:
        None
    """
    classifier = CARDSClassifier()

    for argument in track(db.all(), description="Classifying arguments..."):
        if "cards_category" in argument and argument["lang"] != "en":
            db.update({"cards_category": None}, doc_ids=[argument.doc_id])
        elif "cards_category" not in argument and argument["climate_myth"] is not None and argument["lang"] == "en":
            text = argument["climate_myth"]
            prediction = classifier.classify(text)
            db.update({"cards_category": prediction}, doc_ids=[argument.doc_id])
    logging.info("All arguments classified.")


def process_all(
    db: TinyDB,
    urls: Optional[list[str]] = None,
    ignore_urls: Optional[list] = None,
) -> None:
    """Fetches, processes, and classifies arguments from Skeptical Science.

    This function fetches argument URLs, processes them to extract articles and their levels,
    and classifies the articles using the CARDSClassifier. It stores all results in the provided TinyDB instance.

    Args:
        db (TinyDB): The TinyDB database instance where articles and classifications will be stored.
        urls (list[str]): List of URLs to process and classify.
        ignore_urls (Optional[list], optional): List of URLs to ignore during processing. Defaults to None.

    Returns:
        None
    """
    if urls is None:
        urls = []
    process_urls(db, urls, ignore_urls=ignore_urls)
    classify_urls(db)
