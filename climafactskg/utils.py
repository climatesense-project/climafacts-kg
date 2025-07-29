import hashlib
import json
import os
import re
import tempfile
from datetime import datetime, timedelta
from typing import Dict
from urllib.parse import urljoin

import bs4
import pandas as pd
import requests
from SPARQLWrapper import JSON, SPARQLWrapper


def query_sparqlendpoint(endpoint_url, query) -> pd.DataFrame:
    """Executes a SPARQL query against a specified endpoint and returns the results as a pandas DataFrame.

    Parameters:
        endpoint_url (str): The URL of the SPARQL endpoint to query.
        query (str): The SPARQL query string to execute.

    Returns:
        pandas.DataFrame: A DataFrame containing the query results, where each row corresponds to a result binding.

    Raises:
        Any exceptions raised by SPARQLWrapper or pandas during query execution or DataFrame creation.

    Example:
        df = query_sparqlendpoint("https://dbpedia.org/sparql", "SELECT ?s WHERE { ?s a dbo:Person } LIMIT 10")
    """
    sparql = SPARQLWrapper(endpoint_url)
    sparql.setQuery(query)
    sparql.setReturnFormat(JSON)
    results = sparql.query().convert()
    rows = []

    if (
        not isinstance(results, dict)
        or "results" not in results
        or not isinstance(results.get("results"), dict)
        or "bindings" not in results["results"]
    ):
        return pd.DataFrame()
    else:
        for result in results["results"]["bindings"]:
            row = {k: v["value"] for k, v in result.items()}
            rows.append(row)
        return pd.DataFrame(rows)


def remove_html_tags(text) -> str:
    """Removes HTML tags from the given string.

    Args:
        text (str): The input string potentially containing HTML tags.

    Returns:
        str: The input string with all HTML tags removed.

    Example:
        >>> remove_html_tags("<p>Hello <b>World</b></p>")
        'Hello World'
    """
    """Remove HTML tags from a string."""
    clean = re.compile("<.*?>")
    return re.sub(clean, "", text)


def extract_hierarchy(ul_element: bs4.element.Tag, base_url: str = "") -> list[Dict]:
    """Recursively extracts a hierarchical structure from a given <ul> HTML element.

    Args:
        ul_element (bs4.element.Tag): A BeautifulSoup Tag object representing a <ul> element.
        base_url (str, optional): The base URL to resolve relative links. Defaults to an empty string.

    Returns:
        list[Dict]: A list of dictionaries representing the hierarchy. Each dictionary contains:
            - 'title' (str): The text of the link in the <li> element.
            - 'url' (str): The absolute URL of the link.
            - 'subcategories' (list, optional): A list of subcategories if nested <ul> elements exist.
    """
    hierarchy = []
    for li in ul_element.find_all("li", recursive=False):
        item = {}
        # Extract the text and URL of the current <li>
        if isinstance(li, bs4.element.Tag):
            link = li.find("a")
            if isinstance(link, bs4.element.Tag):
                item["url"] = urljoin(base_url, str(link["href"]))
            # Check if there is a nested <ul> and recursively extract it
            nested_ul = li.find("ul")
            if isinstance(nested_ul, bs4.element.Tag):
                item["subcategories"] = extract_hierarchy(nested_ul, base_url)
        hierarchy.append(item)
    return hierarchy


def fetch_url_content(
    url: str,
    cache_dir: str = os.getenv("CLIMAFACTSKG_CACHE_DIR", tempfile.gettempdir()),
    cache_expiry: timedelta = timedelta(
        seconds=int(os.getenv("CLIMAFACTSKG_KG_CACHE_EXPIRY", 3600))  # noqa: B008
    ),  # noqa: B008
) -> str:
    """Fetch the content of a URL using a disk cache. Cache expires after a given period.

    Args:
        url (str): The URL to fetch.
        cache_dir (str, optional): The directory to store the cache. Defaults to an environment variable or the system temporary directory.
        cache_expiry (timedelta, optional): The cache expiry duration in seconds. Defaults to an environment variable or 1 hour.

    Returns:
        str: The content of the URL.

    Raises:
        requests.RequestException: If the request fails.
    """  # noqa: E501
    # Ensure the cache directory exists
    os.makedirs(cache_dir, exist_ok=True)

    # Create a unique cache key based on the URL
    cache_key = hash_string(url)
    cache_path = os.path.join(cache_dir, f"{cache_key}.json")

    # Check if the cache exists and is still valid
    if os.path.exists(cache_path):
        with open(cache_path, "r", encoding="utf-8") as cache_file:
            cached_data = json.load(cache_file)
            if datetime.fromisoformat(cached_data["timestamp"]) > datetime.now() - cache_expiry:
                return cached_data["content"]

    # Fetch the content from the URL
    response = requests.get(url)
    if response.status_code != 200:
        raise ValueError(f"Failed to fetch URL content for '{url}'. Status code: {response.status_code}")

    content = response.text

    # Store the content in the cache
    with open(cache_path, "w", encoding="utf-8") as cache_file:
        json.dump({"content": content, "timestamp": datetime.now().isoformat()}, cache_file)

    return content


def hash_string(s: str) -> str:
    """Generate an MD5 hash for the given string.

    Args:
        s (str): The input string to be hashed.

    Returns:
        str: The hexadecimal representation of the MD5 hash of the input string.
    """
    return hashlib.md5(s.encode("utf-8")).hexdigest()
