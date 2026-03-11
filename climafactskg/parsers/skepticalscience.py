import json
import re
import unicodedata
from datetime import datetime
from typing import Any, Dict, List, Optional, Set
from urllib.parse import urljoin

import langcodes
from bs4 import BeautifulSoup, Tag

from climafactskg.utils import (
    extract_hierarchy,
    fetch_url_content,
    js_object_to_dict,
    parse_apa_citation_html,
    remove_html_tags,
)

_LEVEL_SUFFIX_RE = re.compile(r"-(basic|intermediate|advanced)(\.htm)$", re.IGNORECASE)


def _canonical_url(url: str) -> str:
    """Strip a difficulty-level suffix from a SkS URL to get the canonical myth URL."""
    return _LEVEL_SUFFIX_RE.sub(r"\2", url)


def parse_taxonomy(
    url: str = "https://skepticalscience.com/argument.php?f=taxonomy",
    html: Optional[str] = None,
) -> list:
    """Parses the taxonomy hierarchy from the given Skeptical Science taxonomy URL or provided HTML.

    Args:
        url (str, optional): The URL of the taxonomy page. Defaults to "https://skepticalscience.com/argument.php?f=taxonomy".
        html (str, optional): The HTML content of the taxonomy page. If not provided, it will be fetched from the URL.

    Returns:
        dict: A nested dictionary representing the taxonomy hierarchy.
    """
    if html is None:
        # If no HTML is provided, fetch it from the URL:
        html = fetch_url_content(url)

    # Parse the HTML content using BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")

    # Extract the top-level <ul> element containing the taxonomy
    top_level_ul = soup.select_one("#mainbody > ul")  # Adjust selector based on the actual HTML structure
    if not top_level_ul:
        raise ValueError("Failed to locate the taxonomy hierarchy in the page.")

    # Extract and return the taxonomy hierarchy
    return extract_hierarchy(top_level_ul)


def parse_main_article(url: str, html: Optional[str] = None) -> dict:
    """Parses article metadata from the given URL or provided HTML content.

    This function extracts various metadata and content from an article's HTML or URL, including
    details such as the title, keywords, description, author, last update date, language versions,
    content levels, and more.

        url (str): The URL of the article to parse.
        html (str, optional): The HTML content of the article. If not provided, the function will
            fetch the HTML content from the given URL.

        dict: A dictionary containing the parsed article metadata with the following keys:
            - main_url (str): The main URL of the article.
            - level (str or None): The level of the article (e.g., basic, intermediate, advanced), if available.
            - lang (str): The language of the article (default is "en").
            - description (str or None): The description of the article, if available.
            - languages (list): A list of available language versions, each represented as a dictionary
            with keys:
                - lang (str): The language name.
                - url (str): The URL for the language version.
                - code (str): The language code.
            - levels (list): A list of content levels (e.g., basic, intermediate, advanced), each represented
            as a dictionary with keys:
                - level (str): The level name.
                - urls (list): A list of URLs associated with the level.
            - what_the_science_says (str or None): The content of the "What the science says" section, if available.
            - climate_myth (str or None): The climate myth text, if available.
            - climate_myth_source (dict or None): The source of the climate myth, represented as a dictionary with keys:
                - url (str): The source URL.
                - name (str): The source name.
            - at_glance (str or None): The content of the "At a glance" section, if available.
            - figures (list): A list of figures in the article, each represented as a dictionary with keys:
                - src (str): The source URL of the figure.
                - alt (str, optional): The alternative text for the figure, if available.
                - caption (str, optional): The caption for the figure, if available.
            - related_arguments (list): A list of related arguments, each represented as a dictionary with keys:
                - url (str): The URL of the related argument.
                - title (str): The title of the related argument.

    Notes:
        - If the HTML content is not provided, the function will fetch it from the given URL.
        - The function uses BeautifulSoup for HTML parsing and may raise exceptions if the HTML structure
        does not match the expected format.
        - The function normalizes text content using Unicode normalization (NFKD).
    """
    if html is None:
        # If no HTML is provided, fetch it from the URL:
        html = fetch_url_content(url)

    # Parse the HTML content using BeautifulSoup:
    soup = BeautifulSoup(html, "html.parser")

    if "Rebuttal not found" in soup.text:
        return {"url": url, "content": None}

    # Get the author and last updated date:
    title_tag = soup.find("title")
    title = title_tag.text if title_tag else None
    keywords = remove_html_tags(
        soup.find("meta", attrs={"name": "keywords"})["content"]  # type: ignore
    ).split(", ")

    if soup.find("meta", attrs={"name": "description"}):
        description = remove_html_tags(
            soup.find("meta", attrs={"name": "description"})["content"]  # type: ignore
        )
    else:
        description = None

    # Get the author and last updated date:
    last_update = None
    author = None
    for box in soup.select("p.greenbox"):
        if "Last updated" in box.text:
            match = re.search(r"Last updated on (\d{1,2} \w+ \d{4})", box.text)

            if match:
                last_update = datetime.strptime(match.group(1), "%d %B %Y")
            else:
                last_update = None

            author = None
            if match := re.search(r"by ([\w\s]+)\.", box.text):
                author = match.group(1).strip()  # Only in english version.
            break
        elif "Translation by" in box.text:
            last_update = None
            match = re.search(r"by ([\w\s]+)\.", box.text)
            author = match.group(1).strip() if match else None
            break

    if author is None:
        comment_div = soup.find("div", class_="comment")
        if comment_div:
            next_footnote = comment_div.find_next_sibling("p", class_="footnote padding")
            if next_footnote:
                text = next_footnote.text

                if "Translation by" in text:
                    match = re.search(r"Translation by ([A-Za-z\s]+)", text)
                    if match:
                        author = match.group(1).strip()

    # Get language version with URLs:
    languages = []
    for a in soup.select("#centerColumn p a"):
        if a.has_attr("title") and "View this argument in " in a["title"]:
            match = re.search(r"View this argument in (.+)", str(a["title"]))
            if match:
                lang = match.group(1).strip()
                languages.append(
                    {
                        "lang": lang,
                        "url": urljoin(url, str(a["href"])),
                        "code": langcodes.find(lang).language,
                    }
                )

    # Get basic/intermediate/advanced/versions:
    level = None
    if "Select a level..." in soup.text:
        levels = []
        if table_list := soup.select_one("#mainbody tr"):
            for t in table_list:
                if t.text.strip() in ["Basic", "Intermediate", "Advanced"]:
                    if a := t.find("a"):  # type: ignore
                        levels.append(
                            {
                                "level": a.text.strip().lower(),
                                "urls": [urljoin(url, a["href"])],
                            }
                        )
                    else:
                        alternate_url = url.replace(".htm", f"-{t.text.strip().lower()}.htm")
                        level = t.text.strip().lower()
                        if alternate_url != url:
                            levels.append(
                                {
                                    "level": t.text.strip().lower(),
                                    "urls": [url, alternate_url],
                                }
                            )
                        else:
                            levels.append({"level": t.text.strip().lower(), "urls": [url]})
    else:
        levels = []

    # What the science says:
    what_the_science_says = None
    climate_myth = None
    climate_myth_source = None
    h2_elem = soup.select_one("#mainbody h2")
    if h2_elem is not None:
        sel = h2_elem.find_next_sibling("div")
        if sel:
            what_the_science_says = sel.text.strip()

    if what_the_science_says and soup.select_one(".comment.myth"):
        comment_myth_elem = soup.select_one(".comment.myth")
        climate_myth = (
            unicodedata.normalize("NFKD", comment_myth_elem.text.strip()) if comment_myth_elem is not None else None
        )

        climate_myth_source = None
        comment_myth_a = soup.select_one(".comment.myth a")
        if comment_myth_a:
            climate_myth_source = {
                "url": comment_myth_a["href"],
                "name": comment_myth_a.text.strip(),
            }
    elif what_the_science_says:
        comment_elem = soup.select_one(".comment")
        if comment_elem is not None:
            climate_myth = unicodedata.normalize("NFKD", comment_elem.text.strip())
            a_tag = comment_elem.find("a")
            if a_tag and a_tag.has_attr("href"):  # type: ignore
                climate_myth_source = {
                    "url": a_tag.get("href"),  # type: ignore
                    "name": a_tag.text.strip(),
                }
        else:
            climate_myth = None
            climate_myth_source = None

    # Get at glance if it exists:
    h2_at_glance = soup.find("h2", string="At a glance")  # type: ignore
    if h2_at_glance:
        at_glance = ""

        for sibling in h2_at_glance.find_next_siblings():
            if isinstance(sibling, Tag) and sibling.has_attr("class") and "bluebox" in sibling["class"]:
                break
            at_glance = at_glance + sibling.text.strip() + "\n"
        at_glance = at_glance.strip()
    else:
        at_glance = None

    # Get the main content:
    content = ""
    figures = []
    if at_glance:
        further_details_element = soup.find(id="FurtherDetails")
        if further_details_element and further_details_element.parent:
            siblings = further_details_element.parent.find_next_siblings()
        else:
            h2_further_details = soup.find("h2", string="Further details")  # type: ignore
            if h2_further_details is not None:
                siblings = h2_further_details.find_next_siblings()
            else:
                siblings = []

    elif (
        what_the_science_says
        and soup.select_one(".comment.myth")
        and soup.find("div", class_="comment myth").next_sibling  # type: ignore
    ):
        siblings = soup.find("div", class_="comment myth").next_sibling.find_all("p")  # type: ignore

    elif what_the_science_says:
        comment_div = soup.find("div", class_="comment")
        next_div = comment_div.find_next_sibling("div") if comment_div else None

        if next_div and isinstance(next_div, Tag):
            siblings = next_div.find_all("p")
        else:
            siblings = []
    else:
        h4_elem = soup.find("h4")
        if h4_elem is not None:
            siblings = h4_elem.find_next_siblings()
        else:
            siblings = []

    siblings_iter = iter(siblings)
    while sibling := next(siblings_iter, None):
        if (sibling is None) or (
            sibling.has_attr("class") and "greenbox" in sibling["class"]  # type: ignore
        ):
            break

        if sibling.find("img"):  # type: ignore
            img = sibling.find("img")  # type: ignore
            fig = {"src": img["src"]}  # type: ignore
            if img.has_attr("alt") and img["alt"] != "":  # type: ignore
                fig["alt"] = img["alt"]  # type: ignore

            # Get the caption (it should be the next paragraph if there is no text) and skip it for the main text:
            if sibling.text.strip() != "":
                fig["caption"] = unicodedata.normalize("NFKD", remove_html_tags(sibling.text.strip()))
            elif sibling := next(siblings_iter, None):
                fig["caption"] = unicodedata.normalize("NFKD", remove_html_tags(sibling.text.strip()))

            figures.append(fig)

        elif sibling.text.strip() != "":
            content = content + sibling.text.strip() + "\n"

    content = unicodedata.normalize("NFKD", content.strip())

    # Get related arguments:
    if args := soup.find("h2", string="Related Arguments"):  # type: ignore
        related_arguments = [
            {"url": urljoin(url, str(a["href"])), "title": a.text.strip()}
            for a in args.parent.find_next_sibling("div").select("a")  # type: ignore
        ]
    else:
        related_arguments = []

    # Create a dictionary with all the information:
    article = {
        "url": url,
        "main_url": _canonical_url(url),
        "level": level,
        "lang": "en",
        "title": title,
        "keywords": keywords,
        "description": description,
        "author": author,
        "last_update": last_update,
        "languages": languages,
        "levels": levels,
        "what_the_science_says": what_the_science_says,
        "climate_myth": climate_myth,
        "climate_myth_source": climate_myth_source,
        "at_glance": at_glance,
        "content": content,
        "figures": figures,
        "related_arguments": related_arguments,
    }

    return article


def parse_translated_article(url: str, html: Optional[str] = None, language_code: Optional[str] = None) -> dict:
    """Parses a translated article from the given URL and optional HTML content.

    This function processes the main article data and removes unnecessary fields
    specific to translated articles. It also identifies the language code of the
    article and extracts the main URL for the English version.

    Args:
        url (str): The URL of the translated article.
        html (str, optional): The HTML content of the article. If not provided,
            the function will fetch the content based on the URL.
        language_code (str, optional): The language code of the article. If not provided,
            the function will attempt to determine it automatically.

    Returns:
        dict: A dictionary containing the parsed article data with the following modifications:
            - Unnecessary fields such as "keywords", "description", "last_update",
                "levels", and "related_arguments" are removed.
            - Adds a "lang" field indicating the language code of the article.
            - Adds a "main_url" field pointing to the main English version of the article.
    """
    article = parse_main_article(url, html)

    # Remove unnecessary fields for translated articles:
    del article["keywords"]
    del article["level"]
    del article["description"]
    del article["last_update"]
    del article["levels"]
    del article["related_arguments"]

    # Add the language code by finding the corresponding url in languages:
    # Also extract the main url at the same time.
    if language_code:
        article["lang"] = language_code

    for lang in article["languages"]:
        if language_code is None and lang["url"] == url:
            article["lang"] = lang["code"]
        if lang["code"] == "en":
            article["main_url"] = lang["url"]

    return article


def parse_misinformer_article(url: str, html: Optional[str] = None) -> dict:
    """Parses a Skeptical Science 'misinformer' article and extracts the author name and quotes.

    Args:
        url (str): The URL of the article to parse.
        html (Optional[str], optional): The HTML content of the article.
            If not provided, it will be fetched from the URL.

    Returns:
        dict: A dictionary containing:
            - 'url' (str): The URL of the article.
            - 'author_name' (Optional[str]): The name of the author or source.
            - 'quotes' (List[dict]): A list of dictionaries, each containing:
                - 'quote' (Optional[str]): The extracted quote text.
                - 'date' (Optional[datetime]): The date associated with the quote.
                - 'url' (Optional[str]): The URL of the quote source.
                - 'argument_url' (Optional[str]): The URL to the related argument on Skeptical Science.
    """
    author_name = None
    quotes = []

    if html is None:
        # If no HTML is provided, fetch it from the URL:
        html = fetch_url_content(url)

    # Parse the HTML content using BeautifulSoup:
    soup = BeautifulSoup(html, "html.parser")

    # Check article type:
    if "Climate Misinformation by Source" in soup.text:
        # Source article:
        h1_elem = soup.select_one("#centerColumn > h1")
        if h1_elem and h1_elem.text:
            author_name = h1_elem.text.split(":")[-1].strip()

        for i, j in zip(
            soup.select("#centerColumn > table > tr .footnote > td:nth-child(1)"),
            soup.select("#centerColumn > table > tr .footnote > td:nth-child(2) > a"),
        ):
            argument_url = None
            quote = None
            quote_date = None
            quote_url = None

            a_tag = i.select_one("a")
            if a_tag is not None and a_tag.has_attr("href"):
                quote_url = str(a_tag["href"]).strip()

            result = re.search(r"^\"((.|\s|\r)+)\"(\d.+)\(Source\)$", i.text)
            if result:
                quote = result.group(1).strip()
                quote_date = datetime.strptime(result.group(3).strip(), "%d %B %Y")

            argument_url = urljoin("https://skepticalscience.com/", str(j["href"]).strip())

            quotes.append(
                {
                    "quote": quote,
                    "quote_date": quote_date,
                    "quote_url": quote_url,
                    "argument_url": argument_url,
                }
            )
    else:
        # Politician article
        h1_elem = soup.select_one("#centerColumn > h1")
        if h1_elem and h1_elem.text:
            author_name = h1_elem.text.strip()

        for i, j in zip(
            soup.select("#centerColumn > table > tr.footnote > td:nth-child(1)"),
            soup.select("#centerColumn > table > tr > td:nth-child(2) > a"),
        ):
            argument_url = None
            quote = None
            quote_date = None
            quote_url = None

            a_tag = i.select_one("a")
            if a_tag is not None and a_tag.has_attr("href"):
                quote_url = str(a_tag["href"]).strip()

            result = re.search(r"^\"((.|\s|\r)+)\"(\d.+)\(Source\)$", i.text)
            if result:
                quote = result.group(1).strip()
                quote_date = datetime.strptime(result.group(3).strip(), "%d %B %Y")

            argument_url = urljoin("https://skepticalscience.com/", str(j["href"]).strip())

            quotes.append(
                {
                    "quote": quote,
                    "quote_date": quote_date,
                    "quote_url": quote_url,
                    "argument_url": argument_url,
                }
            )

    return {
        "url": url,
        "author_name": author_name,
        "quotes": quotes,
    }


def parse_skstiptionary_references(js_content: str) -> list:
    """Return research paper references from the sksTiptionary JS file.

    Entries with ``citation == "4"`` are research papers; all others are IPCC /
    NSIDC glossary definitions.  Each returned dict has keys ``key``, ``title``,
    ``definition_html``, plus any bibliography fields extracted from the
    definition HTML: ``authors_raw``, ``year``, ``journal``, ``volume``,
    ``issue``, ``pages``, ``doi``, ``url``.
    """
    parts = js_content.split("sksCitations=", 1)
    if len(parts) != 2:
        raise ValueError("Could not locate sksCitations= in JS content.")

    tiptionary_js = re.sub(r"^\s*sksTiptionary\s*=\s*", "", parts[0]).strip()

    _keys = ["header", "definition", "altKeys", "level", "matchType", "citation", "xmatchtype"]
    try:
        tiptionary: dict = js_object_to_dict(tiptionary_js, unquoted_keys=_keys)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Failed to parse sksTiptionary as JSON: {exc}") from exc

    references = []
    for key, entry in tiptionary.items():
        if not isinstance(entry, dict) or entry.get("citation") != "4":
            continue

        definition_html = entry.get("definition", "")
        bib = parse_apa_citation_html(definition_html)
        bib["key"] = key
        bib["header"] = entry.get("header")
        bib["title"] = entry.get("header")  # kept for backward compatibility
        bib["matchType"] = entry.get("matchType")
        alt = entry.get("altKeys")
        bib["altKeys"] = alt if isinstance(alt, list) else ([alt] if alt else [])
        bib["definition_html"] = definition_html
        references.append(bib)

    return references


def parse_skstiptionary_full(js_content: str) -> Dict[str, Any]:
    """Return the raw sksTiptionary dict (all entries, not just citation==4).

    The dict preserves the original JS structure, including ``altKeys`` as a
    nested dict (``{alt_string: {matchType: ..., xmatchtype: ...}}``) so it
    can be passed directly to :class:`SksMatcher`.
    """
    parts = js_content.split("sksCitations=", 1)
    if len(parts) != 2:
        raise ValueError("Could not locate sksCitations= in JS content.")

    tiptionary_js = re.sub(r"^\s*sksTiptionary\s*=\s*", "", parts[0]).strip()
    _keys = ["header", "definition", "altKeys", "level", "matchType", "citation", "xmatchtype"]
    try:
        return js_object_to_dict(tiptionary_js, unquoted_keys=_keys)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Failed to parse sksTiptionary as JSON: {exc}") from exc


class SksMatcher:
    """Optimised keyword matcher using an alphanumeric prefix index.

    Builds a fast lookup index from a sksTiptionary dict and scans arbitrary
    text to find which tiptionary keys are mentioned.
    """

    WORD_START = re.compile(r"[a-zA-Z0-9]")

    def __init__(self, tiptionary: Dict[str, Any], fast_key_len: int = 3):
        self.fast_key_len = fast_key_len
        self.fast_key_xref: Dict[str, List[Dict[str, Any]]] = {}
        self._build_index(tiptionary)

    def _get_match_type(self, key: str, match_type: Optional[str] = None) -> str:
        """Infer match rules from string casing."""
        if match_type:
            return match_type
        lower = key.lower()
        if key == lower:
            return "A"
        if key == key.upper():
            return "U"
        words = key.split()
        is_title = all(w[0].isupper() and w[1:].islower() for w in words if len(w) > 1)
        return "T" if is_title else "E"

    def _get_fast_key(self, text: str, pointer: int = 0) -> str:
        """Extract an alphanumeric prefix of length ``fast_key_len``."""
        fast_key: List[str] = []
        scan_ptr = pointer
        text_len = len(text)
        while len(fast_key) < self.fast_key_len and scan_ptr < text_len:
            char = text[scan_ptr]
            if char.isalnum():
                fast_key.append(char.lower())
            scan_ptr += 1
        return "".join(fast_key)

    def _add_to_index(self, find_key: str, main_key: str, match_type: Optional[str]) -> None:
        find_key = find_key.strip()
        if len(find_key) < 2:
            return
        m_type = self._get_match_type(find_key, match_type)
        f_key = self._get_fast_key(find_key)
        if not f_key:
            return
        entry = {
            "findKey": find_key,
            "mainKey": main_key,
            "matchType": m_type,
            "len": len(find_key),
        }
        self.fast_key_xref.setdefault(f_key, []).append(entry)

    def _build_index(self, tiptionary: Dict[str, Any]) -> None:
        """Build prefix index and pre-sort buckets for greedy matching."""
        for key_name, data in tiptionary.items():
            self._add_to_index(key_name, key_name, data.get("matchType"))
            if "header" in data:
                self._add_to_index(data["header"], key_name, None)
            alt_keys = data.get("altKeys")
            if isinstance(alt_keys, dict):
                for alt_str, alt_meta in alt_keys.items():
                    m_type = alt_meta.get("matchType") or alt_meta.get("xmatchtype")
                    for sub_key in alt_str.split(";"):
                        self._add_to_index(sub_key, key_name, m_type)
            elif isinstance(alt_keys, list):
                for alt_str in alt_keys:
                    if alt_str:
                        self._add_to_index(str(alt_str), key_name, None)
        for f_key in self.fast_key_xref:
            self.fast_key_xref[f_key].sort(key=lambda x: x["len"], reverse=True)

    def get_matching_keys(self, text: str) -> List[str]:
        """Scan *text* and return all tiptionary main-keys whose terms appear in it."""
        found_keys: Set[str] = set()
        ptr = 0
        text_len = len(text)
        while ptr < text_len:
            match = self.WORD_START.search(text, ptr)
            if not match:
                break
            ptr = match.start()
            f_key = self._get_fast_key(text, ptr)
            match_found = False
            if f_key in self.fast_key_xref:
                for km in self.fast_key_xref[f_key]:
                    target_len = km["len"]
                    if ptr + target_len > text_len:
                        continue
                    segment = text[ptr : ptr + target_len]
                    if km["matchType"] == "A":
                        if segment.lower() == km["findKey"].lower():
                            found_keys.add(km["mainKey"])
                            ptr += target_len
                            match_found = True
                            break
                    elif segment == km["findKey"]:
                        found_keys.add(km["mainKey"])
                        ptr += target_len
                        match_found = True
                        break
            if not match_found:
                ptr += 1
                while ptr < text_len and text[ptr].isalnum():
                    ptr += 1
        return sorted(found_keys)


def parse_skscitations(js_content: str) -> dict:
    """Extracts the ``sksCitations`` mapping from the sksTiptionary JS file.

    Args:
        js_content (str): Raw content of the sksTiptionary JavaScript file.

    Returns:
        dict: Mapping of citation number strings to their label strings,
        e.g. ``{"1": "Definition courtesy of IPCC AR4.", ...}``.

    Raises:
        ValueError: If the ``sksCitations`` block cannot be located or parsed.
    """
    parts = js_content.split("sksCitations=", 1)
    if len(parts) != 2:
        raise ValueError("Could not locate sksCitations= in JS content.")

    citations_raw = parts[1].strip()
    try:
        return js_object_to_dict(citations_raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Failed to parse sksCitations as JSON: {exc}") from exc


if __name__ == "__main__":
    # Example usage:
    from climafactskg.classifiers.cards import CARDSMatcher
    from climafactskg.utils import print_dict_tree

    taxonomy = parse_taxonomy()
    print_dict_tree(taxonomy, main_key="url", list_key="subcategories")

    cm = CARDSMatcher()
    print(cm.clean("This is some testing text with some 'climate' myths."))

    print(cm.classify("Mikes Nature trick hide the decline"))
