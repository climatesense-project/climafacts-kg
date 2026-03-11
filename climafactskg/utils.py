import hashlib
import json
import os
import re
import tempfile
from datetime import datetime, timedelta
from typing import Dict, Optional
from urllib.parse import urljoin

import bs4
import pandas as pd
import preserve
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


def js_object_to_dict(js_block: str, unquoted_keys: Optional[list] = None) -> dict:
    """Parse a JavaScript object literal into a Python dict.

    Handles the common differences between JS object literals and JSON:

    - Unquoted property names.
    - Trailing commas.
    - Backslash escape sequences that are valid in JS but not in JSON.

    Args:
        js_block (str): A JS object literal string, e.g. the value assigned
            to a ``var`` / ``const`` / ``let`` declaration.
        unquoted_keys (list, optional): Explicit list of unquoted property names
            to quote.  When provided, only these names are matched, which avoids
            false positives inside string values that contain ``word:`` patterns
            (e.g. HTML with ``Austin, TX: ...``).  When omitted, any JS
            identifier immediately following ``{`` or ``,`` is quoted.

    Returns:
        dict: The parsed Python dictionary.

    Raises:
        json.JSONDecodeError: If the block cannot be parsed even after
            the normalisation steps above.
    """
    if unquoted_keys:
        pattern = r"([{,]\s*)(" + "|".join(re.escape(k) for k in unquoted_keys) + r")(\s*:)"
    else:
        pattern = r"([{,]\s*)([a-zA-Z_$][a-zA-Z0-9_$]*)(\s*:)"
    # Quote unquoted property names.
    # Anchoring on [{,] prevents false matches inside quoted string values.
    s = re.sub(pattern, r'\1"\2"\3', js_block)
    # Remove trailing commas before } or ].
    s = re.sub(r",(\s*[}\]])", r"\1", s)
    # Drop backslashes that form invalid JSON escape sequences.
    # \\ is kept as-is; any other \X is reduced to just X.
    s = re.sub(
        r'\\\\|\\([^"\\/bfnrtu])',
        lambda m: m.group(0) if m.group(1) is None else m.group(1),
        s,
    )
    return json.loads(s)


_DOI_TEXT_RE = re.compile(r"\bdoi\s*:?\s*(10\.\d{4,}/\S+)", re.IGNORECASE)


def parse_apa_citation_html(definition_html: str) -> dict:
    """Extract structured bibliography fields from an APA-style HTML citation snippet.

    Parses HTML such as those produced by Skeptical Science's sksTiptionary,
    but is generic enough for any APA-formatted ``<p>`` block.

    Args:
        definition_html (str): HTML string containing the citation.  Expected
            to have the citation in the first ``<p>`` element with the journal
            title and volume in ``<em>`` tags.

    Returns:
        dict: Any subset of the following keys that could be extracted:
            ``authors_raw``, ``year``, ``journal``, ``volume``, ``issue``,
            ``pages``, ``doi``, ``url``.
    """
    soup = bs4.BeautifulSoup(definition_html, "html.parser")
    out: dict = {}

    # Non-DOI link (link to paper / PDF / abstract)
    for a in soup.find_all("a", href=True):
        href = str(a["href"])
        if "doi.org" not in href and href.startswith(("http://", "https://")):
            out["url"] = href
            break

    # DOI: prefer anchor whose href *starts* with a doi.org domain, then fall
    # back to plain-text "doi: ...".  Using `in` is intentionally avoided here
    # because URLs like https://example.com/"https:/doi.org/10..." would match.
    _doi_href_re = re.compile(r"^https?://(?:dx\.)?doi\.org/10\.", re.IGNORECASE)
    doi: Optional[str] = None
    for a in soup.find_all("a", href=True):
        if _doi_href_re.match(str(a["href"])):
            doi = str(a["href"])
            break
    if doi is None:
        m = _DOI_TEXT_RE.search(soup.get_text(" "))
        if m:
            doi = "https://doi.org/" + m.group(1).rstrip(".,;)")
    if doi is not None:
        out["doi"] = doi

    # Structured fields come from the first <p> (the main citation line)
    p = soup.find("p")
    if not p:
        return out

    text = p.get_text(" ", strip=True)

    # Year and authors_raw
    m_yr = re.search(r"\((\d{4}[a-z]?)\)", text)
    if m_yr:
        out["year"] = m_yr.group(1)
        raw = text[: m_yr.start()].strip()
        if raw:
            out["authors_raw"] = raw

    # Journal and volume from <em> tags
    em_tags = p.find_all("em")
    if not em_tags:
        return out

    j_text = em_tags[0].get_text(strip=True)
    # Some entries embed volume in the journal em: "Journal Name, 42"
    m_jv = re.match(r"^(.*?),\s*(\d+)\s*$", j_text)
    if m_jv:
        out["journal"] = m_jv.group(1).strip()
        out["volume"] = m_jv.group(2)
        vol_em = em_tags[0]
    elif len(em_tags) > 1 and re.match(r"^\s*\d+\s*$", em_tags[1].get_text()):
        out["journal"] = j_text.strip()
        out["volume"] = em_tags[1].get_text(strip=True)
        vol_em = em_tags[1]
    else:
        out["journal"] = j_text.strip()
        vol_em = em_tags[0]

    # Issue and pages: text immediately after the volume em tag
    after_parts = []
    for sib in vol_em.next_siblings:
        if hasattr(sib, "get_text"):
            after_parts.append(sib.get_text(" "))
        elif isinstance(sib, str):
            after_parts.append(sib)
    after = "".join(after_parts).strip()
    m_ip = re.match(r"\s*\((\w+)\)\s*,?\s*([\w\-\u2013]+)", after)
    if m_ip:
        out["issue"] = m_ip.group(1)
        out["pages"] = m_ip.group(2).rstrip(".")

    return out


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
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3"  # noqa: E501
    }
    response = requests.get(url, headers=headers)
    if response.status_code != 200 and "not found" in response.text.strip().lower():
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


def print_dict_tree(
    data: list[Dict],
    main_key: str = "title",
    list_key: str = "sublist",
    indent: int = 0,
    _counter: Optional[list] = None,
) -> None:
    """Recursively prints a list of dictionaries as a tree structure and prints the total number of items at the end.

    Each dictionary should contain a 'title' key and optionally a 'subcategories' key
    which is a list of dictionaries in the same format.

    Args:
        data (list[Dict]): The list of dictionaries to print.
        main_key (str, optional): The key to use for the main label in each dictionary. Defaults to "title".
        list_key (str, optional): The key to use for subcategories in each dictionary. Defaults to "sublist".
        indent (int, optional): The current indentation level. Defaults to 0.
    """
    if _counter is None:
        _counter = [0]
        root_call = True
    else:
        root_call = False

    for item in data:
        title = item.get(main_key, "")
        print("│  " * indent + f"├─ {title}")
        _counter[0] += 1
        subcategories = item.get(list_key, [])
        if isinstance(subcategories, list) and subcategories:
            print_dict_tree(
                subcategories,
                main_key=main_key,
                list_key=list_key,
                indent=indent + 1,
                _counter=_counter,
            )

    if root_call:
        print(f"\nTotal items: {_counter[0]}")


def deserialize_datetime(obj):
    """Converts an ISO formatted datetime string to a `datetime.datetime` object.

    If the input `obj` is a string representing a datetime in ISO format,
    returns the corresponding `datetime.datetime` object. If the conversion
    fails or `obj` is not a string, returns `obj` unchanged.

    Args:
        obj (Any): The object to deserialize, typically a string or datetime.

    Returns:
        Any: A `datetime.datetime` object if deserialization is successful,
                otherwise the original `obj`.
    """
    if isinstance(obj, str):
        try:
            return datetime.fromisoformat(obj)
        except ValueError:
            pass
    return obj


def serialize_datetime(obj):
    """Serializes a datetime.datetime object to an ISO 8601 formatted string.

    Args:
        obj: The object to serialize.

    Returns:
        str: The ISO 8601 formatted string representation of the datetime object.

    Raises:
        TypeError: If the provided object is not a datetime.datetime instance.
    """
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError("Type not serializable")


def preserve_to_json(db: preserve.Connector, filename: str) -> None:
    """Serializes dictionary entries from a preserve.Connector database to a JSON file.

    Iterates over the database, selects entries that are dictionaries, and writes them to the specified
    JSON file with UTF-8 encoding. Datetime objects within the dictionaries are serialized using the
    `serialize_datetime` function.

    Args:
        db (preserve.Connector): The database connector to iterate over.
        filename (str): The path to the output JSON file.

    Returns:
        None
    """
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(
            obj=[i for _, i in db],
            fp=f,
            default=serialize_datetime,
            ensure_ascii=False,
            indent=4,
        )
