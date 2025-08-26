import logging
from typing import Optional
from urllib.parse import urljoin

import preserve
from bs4 import BeautifulSoup
from rich.progress import track

from climafactskg.classifiers.cards import CARDSClassifier
from climafactskg.parsers.skepticalscience import (
    parse_main_article,
    parse_misinformer_article,
    parse_translated_article,
)
from climafactskg.utils import fetch_url_content

logging.basicConfig(level=logging.INFO)


def fetch_misinformers_urls(ignore_urls: Optional[list] = None) -> list:
    """Fetches and returns a sorted list of URLs for misinformers from Skeptical Science.

    This function scrapes two specific pages on Skeptical Science:
    1. The main misinformers list.
    2. The politicians' quotes list.

    It collects all unique URLs found in the relevant sections of both pages.
    Optionally, URLs provided in `ignore_urls` will be excluded from the results.

    Args:
        ignore_urls (Optional[list]): A list of URLs to exclude from the results.

    Returns:
        list: A sorted list of unique misinformer URLs.
    """
    misinformers_urls = set()

    # 1) Extract from the main list:
    url = "https://skepticalscience.com/misinformers.php"
    content = fetch_url_content(url)
    soup = BeautifulSoup(content, "html.parser")
    misinformers_urls.update([urljoin(url, str(a["href"])) for a in soup.select("#centerColumn > ul > li > a")])

    # 2) Extract from the politicians list:
    url = "https://skepticalscience.com/skepticquotes.php"
    content = fetch_url_content(url)
    soup = BeautifulSoup(content, "html.parser")
    misinformers_urls.update([urljoin(url, str(a["href"])) for a in soup.select("#centerColumn > div > a")])

    # Remove ignored URLs if provided:
    if ignore_urls:
        misinformers_urls = [url for url in misinformers_urls if url not in ignore_urls]

    # Sort the URLs:
    logging.info(f"Found {len(misinformers_urls)} misinformer URLs.")
    return sorted(misinformers_urls)


def process_misinformers_urls(db: preserve.Connector, urls: list[str], ignore_urls: Optional[list] = None) -> None:
    """Processes a list of misinformer URLs.

    Args:
        db (preserve.Connector): The database connector used to store parsed articles.
        urls (list[str]): List of URLs to process.
        ignore_urls (Optional[list], optional): List of URLs to ignore during processing. Defaults to None.

    Returns:
        None
    """
    if ignore_urls is None:
        ignore_urls = []

    urls = [url for url in urls if url not in ignore_urls]

    logging.info(f"Processing {len(urls)} URLs.")

    for i, main_url in enumerate(urls, start=1):
        logging.info(f"Processing URL {i}/{len(urls)}: {main_url}")

        if main_url in db:
            logging.info(f"Skipping already processed URL: {main_url}")
        else:
            content = fetch_url_content(main_url)
            article = parse_misinformer_article(main_url, content)

            # Store the article in the db
            db[main_url] = article
            logging.info(f"Stored article for URL: {main_url}")


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


def process_urls(db: preserve.Connector, urls: list[str], ignore_urls: Optional[list] = None) -> None:
    """Process a list of URLs by fetching, parsing, and storing articles along with their levels and translations.

    This function processes each URL by:
    1. Fetching and parsing the main article content
    2. Processing any article levels (different versions/depths of the same content)
    3. Processing any language translations of the article
    4. Storing all processed content in the provided database connector

    Args:
        db (preserve.Connector): Database connector for storing processed articles
        urls (list[str]): List of URLs to process
        ignore_urls (Optional[list], optional): List of URLs to skip during processing.
            Defaults to None (empty list).

    Returns:
        None

    Note:
        - URLs already present in the database with a 'lang' field are skipped
        - For each main URL, the function also processes associated level URLs and translation URLs
        - Progress is logged throughout the processing with detailed status information
    """
    if ignore_urls is None:
        ignore_urls = []

    urls = [url for url in urls if url not in ignore_urls]

    logging.info(f"Processing {len(urls)} URLs.")

    for i, main_url in enumerate(urls, start=1):
        logging.info(f"Processing URL {i}/{len(urls)}: {main_url}")

        if main_url in db and "lang" in db[main_url]:
            logging.info(f"Skipping already processed URL: {main_url}")
        else:
            content = fetch_url_content(main_url)
            article = parse_main_article(main_url, content)

            # Store the article in the db
            db[main_url] = article
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

                        # Store the article in the db
                        db[level_url] = level_article
                        logging.info(f"Stored level article for URL: {level_url}")

                    logging.info(f"Finished level: {level['level']}")

            if "languages" in article:
                for lang in article["languages"]:
                    logging.info(f"Processing language : {lang['lang']}")

                    logging.info(f"Processing language URL: {lang['url']}")
                    lang_article = parse_translated_article(lang["url"], language_code=lang["code"])

                    # Store the  article in the db
                    db[lang["url"]] = lang_article
                    logging.info(f"Stored translated article for language URL: {lang['url']}")

                    logging.info(f"Finished language: {lang['lang']}")

        logging.info(f"Finished processing URL {i}/{len(urls)}: {main_url}")


def classify_urls(db: preserve.Connector) -> None:
    """Classify URLs in the database using the CARDS classifier.

    This function processes arguments stored in the database, applying classification
    to English-language climate myths while managing existing classifications for
    non-English content.

    Args:
        db (preserve.Connector): Database connector containing URL-indexed arguments
                                with fields like 'cards_category', 'lang', and 'climate_myth'

    Returns:
        None

    Behavior:
        - For non-English arguments with existing classifications: removes the classification
        - For English arguments without classification but with climate_myth content:
          applies CARDS classification to the climate_myth text
        - Updates the database with modified argument data
        - Logs completion message when all arguments are processed

    Note:
        Uses CARDSClassifier for text classification and track() for progress monitoring.
    """
    classifier = CARDSClassifier()

    for url, argument in track(db, description="Classifying arguments..."):
        if "cards_category" in argument and argument["lang"] != "en":
            argument["cards_category"] = None
            db[url] = argument
        elif "cards_category" not in argument and argument["climate_myth"] is not None and argument["lang"] == "en":
            text = argument["climate_myth"]
            argument["cards_category"] = classifier.classify(text)
            db[url] = argument
    logging.info("All arguments classified.")


def process_all(
    db: preserve.Connector,
    urls: Optional[list[str]] = None,
    ignore_urls: Optional[list] = None,
) -> None:
    """Process all URLs for skeptical science data collection and classification.

    This function orchestrates the complete processing pipeline by first processing
    the provided URLs (or an empty list if none provided) and then classifying
    all URLs in the database.

    Args:
        db (preserve.Connector): Database connector instance for data operations.
        urls (Optional[list[str]], optional): List of URLs to process. If None,
            defaults to an empty list. Defaults to None.
        ignore_urls (Optional[list], optional): List of URLs to ignore during
            processing. Defaults to None.

    Returns:
        None: This function performs operations but does not return a value.
    """
    if urls is None:
        urls = []
    process_urls(db, urls, ignore_urls=ignore_urls)
    classify_urls(db)
