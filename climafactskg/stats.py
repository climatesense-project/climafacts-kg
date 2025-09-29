from collections import Counter

import preserve


def count_unique_values(
    sks_db="data/skepticalscience_arguments_db.db",
    key="main_url",
):
    with preserve.open(format="sqlite", filename=sks_db) as db:
        values = [db[k].get(key) for k in db if key in db[k]]
        unique_values = Counter(values)

        print(f"Unique values for '{key}': {len(unique_values)}")
        print(f"Unique values for '{key}': {len(unique_values)}")

    return unique_values


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()
    db = "data/skepticalscience_arguments_db.db"
    db = "data/skepticalscience_arguments_db.db"

    print("---------- ClimaFactsKG ----------")
    count_unique_values(db, key="lang")
    count_unique_values(db, key="main_url")
    print(count_unique_values(db, key="cards_category"))
    count_unique_values(db, key="lang")
    count_unique_values(db, key="main_url")
    print(count_unique_values(db, key="cards_category"))

    print("---------- CimpleKG ----------")
    query = """PREFIX da: <https://www.wowman.org/index.php?id=1&type=get#>
    PREFIX sd: <http://www.w3.org/ns/sparql-service-description#>
    PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
    PREFIX sdo: <https://schema.org/>
    PREFIX cf: <https://purl.net/climatesense/climafactskg/ns#>

    SELECT (COUNT(DISTINCT ?c) as ?count) WHERE {
        ?c ?d ?e .
        FILTER (STRSTARTS(str(?c), str('http://data.cimple.eu/')) ) .
    }"""

    db = "data/cimplekg_mappings_db.db"
    cnt = count_unique_values(db, key="cards_category")

    # Count the total number of claims except 0_0:
    print(cnt)
    total_claims = sum(cnt.values()) - cnt.get("0_0", 0) - cnt.get(None, 0)
    print(f"Total claims (excluding '0_0' and None): {total_claims}")
