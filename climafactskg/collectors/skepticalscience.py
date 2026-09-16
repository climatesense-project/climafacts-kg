import logging
from typing import Optional
from urllib.parse import urljoin

import preserve
from bs4 import BeautifulSoup

from climafactskg.collectors.utils import batch_classify_cards_category
from climafactskg.parsers.skepticalscience import (
    parse_main_article,
    parse_misinformer_article,
    parse_skstiptionary_references,
    parse_translated_article,
)
from climafactskg.utils import fetch_url_content


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


def classify_urls(
    db: preserve.Connector,
    force: bool = False,
    concurrency: Optional[int] = None,
    classifier_engine: str = "transformer",
    cache_path: Optional[str] = None,
) -> None:
    """Classify URLs in the database using CARDS classification (batch mode).

    Iterates through arguments in the database, collecting English-language entries
    that have a 'climate_myth' text. For each entry that does not already have a
    'cards_category' (unless *force* is True), the function classifies the text using
    the batch API and updates the database entries with the resulting categories.

    Args:
        db (preserve.Connector): Database connector containing URL-indexed arguments
                                with fields like 'cards_category', 'lang', and 'climate_myth'.
        force (bool, optional): Re-classify arguments that already have a
            'cards_category'. Defaults to False.
        concurrency (int, optional): Maximum number of concurrent LLM calls.
            Defaults to the classifier preset's own tuned concurrency. Only used
            when ``classifier_engine="llm"``.
        classifier_engine (str, optional): ``"transformer"`` (default) or ``"llm"``.
            See :func:`climafactskg.collectors.utils.batch_classify_cards_category`.
        cache_path (str, optional): Preserve SQLite cache path, shared across
            sources to avoid reclassifying identical text. Defaults to None
            (no caching).

    Returns:
        None
    """
    batch_classify_cards_category(
        db,
        text_field="climate_myth",
        filter_lang="en",
        force=force,
        concurrency=concurrency,
        classifier_engine=classifier_engine,
        cache_path=cache_path,
        collect_description="Collecting arguments to classify",
        save_description="Saving classifications",
        empty_message="No arguments to classify.",
        classify_item_name="arguments",
    )
    logging.info("All arguments classified.")


def process_all(
    db: preserve.Connector,
    urls: Optional[list[str]] = None,
    ignore_urls: Optional[list] = None,
    force: bool = False,
    concurrency: Optional[int] = None,
    classifier_engine: str = "transformer",
    cache_path: Optional[str] = None,
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
        force (bool, optional): Re-classify already-classified arguments. Defaults to False.
        concurrency (int, optional): Maximum concurrent LLM calls. Defaults to the
            classifier preset's own tuned concurrency. Only used when
            ``classifier_engine="llm"``.
        classifier_engine (str, optional): ``"transformer"`` (default) or ``"llm"``.
            See :func:`climafactskg.collectors.utils.batch_classify_cards_category`.
        cache_path (str, optional): Preserve SQLite cache path, shared across
            sources to avoid reclassifying identical text. Defaults to None
            (no caching).

    Returns:
        None: This function performs operations but does not return a value.
    """
    if urls is None:
        urls = []
    process_urls(db, urls, ignore_urls=ignore_urls)
    classify_urls(db, force=force, concurrency=concurrency, classifier_engine=classifier_engine, cache_path=cache_path)


def fetch_skstiptionary(
    url: str = "https://skepticalscience.com/public/assets/jsgen/skstiptionary_1752342798469.js",
) -> str:
    """Fetches the sksTiptionary JavaScript file from Skeptical Science.

    Args:
        url (str): URL of the sksTiptionary JS file.

    Returns:
        str: Raw JavaScript file content.
    """
    return fetch_url_content(url)


def process_skstiptionary(
    db: preserve.Connector, url: str = "https://skepticalscience.com/public/assets/jsgen/skstiptionary_1752342798469.js"
) -> None:
    """Downloads the sksTiptionary JS file, extracts research paper references, and stores them in the database.

    Each reference is stored under its citation key (e.g. ``"Cook et al. (2013)"``).
    Already-stored keys are skipped.

    Args:
        db (preserve.Connector): Database connector for storing parsed references.
        url (str): URL of the sksTiptionary JS file.

    Returns:
        None
    """
    js_content = fetch_skstiptionary(url)
    references = parse_skstiptionary_references(js_content)

    logging.info(f"Found {len(references)} research paper references.")

    for ref in references:
        key = ref["key"]
        if key in db:
            logging.info(f"Skipping already stored reference: {key}")
        else:
            db[key] = ref
            logging.info(f"Stored reference: {key}")
