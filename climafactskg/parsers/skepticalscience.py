import re
import unicodedata
from datetime import datetime
from typing import Optional
from urllib.parse import urljoin

import langcodes
from bs4 import BeautifulSoup, Tag

from climafactskg.utils import extract_hierarchy, fetch_url_content, remove_html_tags


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
    h2_at_glance = soup.find("h2", string="At a glance")
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
            h2_further_details = soup.find("h2", string="Further details")
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
    if args := soup.find("h2", string="Related Arguments"):
        related_arguments = [
            {"url": urljoin(url, str(a["href"])), "title": a.text.strip()}
            for a in args.parent.find_next_sibling("div").select("a")  # type: ignore
        ]
    else:
        related_arguments = []

    # Create a dictionary with all the information:
    article = {
        "url": url,
        "main_url": url,
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
