from collections import Counter

from tinydb import JSONStorage, TinyDB
from tinydb_serialization import SerializationMiddleware
from tinydb_serialization.serializers import DateTimeSerializer


def count_unique_values(
    json_db="data/skepticalscience_arguments_db.json",
    key="main_url",
    table_name="arguments",
):
    serialization = SerializationMiddleware(JSONStorage)
    serialization.register_serializer(DateTimeSerializer(), "TinyDate")

    with TinyDB(json_db, storage=serialization) as db:
        db.default_table_name = table_name

        values = [item.get(key) for item in db.all() if key in item]
        unique_values = Counter(values)

        print(f"Unique values for '{key}' in table '{table_name}': {len(unique_values)}")

    return unique_values


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()
    json_db = "data/skepticalscience_arguments_db.json"

    print("---------- ClimaFactsKG ----------")
    count_unique_values(json_db, key="lang", table_name="arguments")
    count_unique_values(json_db, key="main_url", table_name="arguments")
    print(count_unique_values(json_db, key="cards_category", table_name="arguments"))

    print("---------- CimpleKG ----------")
    json_db = "data/cimplekg_claims_db.json"
    cnt = count_unique_values(json_db, key="cards_category", table_name="mappings")

    # Count the total number of claims except 0_0:
    print(cnt)
    total_claims = sum(cnt.values()) - cnt.get("0_0", 0) - cnt.get(None, 0)
    print(f"Total claims (excluding '0_0' and None): {total_claims}")
