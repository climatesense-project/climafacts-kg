"""Dataset factory functions for CARDS classifier evaluation.

Each factory returns a pydantic-evals :class:`~pydantic_evals.Dataset` ready to
pass to :func:`~climafactskg.classifiers.cards.eval.evaluate` or
:func:`~climafactskg.classifiers.cards.eval.benchmark_configs`.

Public factories
----------------
nslp_dataset
    NSLP / ClimateCheck claims from the ``rabuahmad/climatecheck`` HuggingFace
    dataset.

climatesense_dataset_v1
    Internal ClimateSense annotation round 1.  Loads from a cached CSV or
    downloads from Google Drive on first call.

climatesense_dataset_v2
    Internal ClimateSense annotation round 2.  Same format and pipeline as v1,
    different spreadsheet and Drive folder.

Annotation pipeline (private helpers)
--------------------------------------
_hierarchical_majority_vote
    Applies hierarchical conditional majority voting to one document's annotation
    rows and returns the consensus CARDS code(s).

_download_annotations_df
    Authenticates with Google, reads the master annotation-groups spreadsheet,
    discovers and downloads all individual annotation sheets from Google Drive,
    then calls :func:`_hierarchical_majority_vote` per document.

_load_climatesense_dataset
    Shared implementation for both v1 and v2: CSV fast-path or Drive download,
    followed by case construction.
"""

import dataclasses
import logging
import os
import re
import time
from typing import Literal

import pandas as pd
from pydantic_evals import Case, Dataset

from .evaluators import (
    _MAX_CLASSIFIER_DEPTH,
    CARDSHierarchicalMatch,
    CARDSOneOfMatch,
    DepthMetricsReportEvaluator,
    HierarchicalMetricsReportEvaluator,
    MultiMetricsReportEvaluator,
    project_to_depth,
)

logger = logging.getLogger(__name__)


@dataclasses.dataclass
class CARDSInput:
    """Inputs for one CARDS evaluation case.

    Attributes:
        text: The claim text to classify.
        context: Optional fact-check context (e.g. reviewer verdict, sources).
            When provided, classifiers can use it to inform the classification.
    """

    text: str
    context: str | None = None


# Annotators sometimes fill in labels as "[5_1_1] Description text" — this
# pattern extracts the bare code from the bracket prefix.
_BRACKET_CODE_RE = re.compile(r"^\[([^\]]+)\]")

# Evaluators attached to every dataset returned by this module.
_DEFAULT_EVALUATORS = [CARDSOneOfMatch(), CARDSHierarchicalMatch()]
_DEFAULT_REPORT_EVALUATORS = [
    MultiMetricsReportEvaluator(),
    HierarchicalMetricsReportEvaluator(),
    DepthMetricsReportEvaluator(),
]


def nslp_dataset(limit: int | None = None, split: Literal["train", "test"] = "train") -> Dataset:
    """Build a dataset from the NSLP / ClimateCheck HuggingFace parquet.

    Args:
        limit: Maximum number of cases to include.  Useful for quick smoke-tests.
            Defaults to None (all cases).
        split: Which HuggingFace split to load — ``"train"`` (default) or
            ``"test"``.  Published NSLP results are on the test split, so
            train-split numbers are not directly comparable to the paper's Table 2.
    """
    split_paths = {
        "train": "data/train-00000-of-00001.parquet",
        "test": "data/test-00000-of-00001.parquet",
    }
    logger.info("Downloading NSLP dataset (%s split) from Hugging Face", split)
    df = pd.read_parquet("hf://datasets/rabuahmad/climatecheck/" + split_paths[split])
    df = (
        df[["claim_id", "claim", "narrative"]]
        .dropna()
        .drop_duplicates()
        .rename(columns={"narrative": "cards_category"})
        .reset_index(drop=True)
    )
    df["cards_category"] = df.cards_category.apply(lambda x: [y.strip() for y in x.split(";")])
    df = df.drop_duplicates(subset=["claim_id"])
    if limit is not None:
        df = df.head(limit)
    limit_note = f" (limited to {limit})" if limit is not None else ""
    logger.info("Loaded NSLP dataset (%s): %d cases%s", split, len(df), limit_note)
    cases = [
        Case(name=str(row["claim_id"]), inputs=CARDSInput(text=row["claim"]), expected_output=row["cards_category"])
        for _, row in df.iterrows()
    ]
    return Dataset(
        cases=cases,
        name="NSLP Claims Evaluation Dataset",
        evaluators=_DEFAULT_EVALUATORS,
        report_evaluators=_DEFAULT_REPORT_EVALUATORS,
    )


def _hierarchical_majority_vote(doc_df: pd.DataFrame) -> tuple[list[str] | None, dict]:
    """Apply hierarchical conditional majority voting to one document's annotation rows.

    Each annotation level is voted on only by the annotators who agreed on the
    parent level.  When no single value wins a majority (tie), all tied values
    are returned so the classifier is credited if it predicts any one of them.

    Returns:
        ``(None, info)`` when the document should be excluded from evaluation:
        either a tie on ``is_climate_related`` (genuinely ambiguous) or all
        annotators agreed the claim is climate-related but none assigned a CARDS
        category (valid judgement — no fitting category exists).

        ``(["0_0"], info)`` when the majority said not-climate.

        ``(codes, info)`` otherwise, where *codes* is a list of one or more valid
        CARDS codes and *info* records per-level vote counts for logging and the
        ``agreement_info`` CSV column.
    """
    info: dict = {
        "n_annotators": len(doc_df),
        "climate_votes": {},
        "level1_votes": {},
        "level2_votes": {},
        "level3_votes": {},
        "resolved_at": None,
    }

    # Step 1 — is_climate_related (all annotators)
    # Replace empty strings before dropna — gspread returns "" for blank cells.
    climate = doc_df["is_climate_related"].replace("", pd.NA).dropna().value_counts()
    info["climate_votes"] = {str(k): int(v) for k, v in climate.items()}
    if climate.empty:
        info["resolved_at"] = "skipped_no_votes"
        return None, info
    top_climate = climate[climate == climate.max()]
    if len(top_climate) > 1:
        info["resolved_at"] = "skipped_tie_climate"
        return None, info
    if not top_climate.index[0]:
        info["resolved_at"] = "not_climate"
        return ["0_0"], info

    climate_df = doc_df[doc_df["is_climate_related"] == True]  # noqa: E712

    # Step 2 — cards_level1 (climate-True annotators only)
    l1 = climate_df["cards_level1"].replace("", pd.NA).dropna().value_counts()
    info["level1_votes"] = {str(k): int(v) for k, v in l1.items()}
    if l1.empty:
        # Annotators agreed climate=True but left no level1 — valid judgement that
        # the claim is climate misinformation but doesn't fit any CARDS category.
        # Excluded because no expected code can be assigned for evaluation.
        info["resolved_at"] = "skipped_no_cards_category"
        return None, info
    top_l1 = l1[l1 == l1.max()]
    if len(top_l1) > 1:
        info["resolved_at"] = "level1_tie"
        return [f"{c}_0" if "_" not in str(c) else str(c) for c in top_l1.index], info

    winning_l1 = top_l1.index[0]
    l1_df = climate_df[climate_df["cards_level1"] == winning_l1]

    # Step 3 — cards_level2 (annotators who agreed on winning level1)
    l2 = l1_df["cards_level2"].replace("", pd.NA).dropna().value_counts()
    info["level2_votes"] = {str(k): int(v) for k, v in l2.items()}
    if l2.empty:
        code = f"{winning_l1}_0" if "_" not in str(winning_l1) else str(winning_l1)
        info["resolved_at"] = "level1"
        return [code], info
    top_l2 = l2[l2 == l2.max()]
    if len(top_l2) > 1:
        info["resolved_at"] = "level2_tie"
        return [str(c) for c in top_l2.index], info

    winning_l2 = top_l2.index[0]
    l2_df = l1_df[l1_df["cards_level2"] == winning_l2]

    # Step 4 — cards_level3 (annotators who agreed on winning level2)
    l3 = l2_df["cards_level3"].replace("", pd.NA).dropna().value_counts()
    info["level3_votes"] = {str(k): int(v) for k, v in l3.items()}
    if l3.empty:
        info["resolved_at"] = "level2"
        return [str(winning_l2)], info
    top_l3 = l3[l3 == l3.max()]
    info["resolved_at"] = "level3_tie" if len(top_l3) > 1 else "level3"
    return [str(c) for c in top_l3.index], info


def _download_annotations_df(
    annotation_groups_sheet_url: str,
    annotation_folder_id: str,
    min_annotators: int = 3,
    completed_status: str = "Finished",
) -> pd.DataFrame:
    """Authenticate with Google, download all annotation sheets, and run majority voting.

    Reads the master annotation-groups spreadsheet to find which annotation
    groups are complete, then discovers the corresponding spreadsheets in Google
    Drive, reads each ``"annotations"`` worksheet, and applies
    :func:`_hierarchical_majority_vote` per document.

    Requires ``gspread``, ``google-auth``, and ``google-api-python-client``.
    Set ``GOOGLE_APPLICATION_CREDENTIALS`` in the environment to a service-account
    JSON file with read access to the annotation spreadsheets and Drive folder.

    Args:
        annotation_groups_sheet_url: URL of the master annotation-groups spreadsheet.
            Each row lists one annotator's sheet with columns ``Annotation Group``,
            ``Annotation Sheet``, and ``Status``.
        annotation_folder_id: Google Drive folder ID containing annotation subfolders
            (one subfolder per annotation group, one spreadsheet per annotator).
        min_annotators: Minimum number of completed annotators required for a group
            to be included.  Groups below this threshold are silently skipped.
        completed_status: Value of the ``Status`` column that indicates a finished
            annotation (e.g. ``"Finished"`` for v1, ``"done"`` for v2).

    Returns:
        DataFrame with columns ``document_id``, ``content``, ``source``, ``type``,
        ``cards_code`` (semicolon-separated when a tie produced multiple valid
        labels), and ``agreement_info`` (JSON string with per-level vote counts).
    """
    import json as _json

    import gspread
    from dotenv import load_dotenv
    from google.oauth2.service_account import Credentials
    from googleapiclient.discovery import build

    load_dotenv()
    service_account_file = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if not service_account_file:
        raise EnvironmentError("GOOGLE_APPLICATION_CREDENTIALS is not set")

    scopes = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_file(service_account_file, scopes=scopes)
    gc = gspread.authorize(creds)
    drive_service = build("drive", "v3", credentials=creds)
    logger.info("Google authentication successful")

    # Load annotation group metadata from master spreadsheet
    annotators_df = pd.DataFrame(gc.open_by_url(annotation_groups_sheet_url).sheet1.get_all_records())
    logger.info("Master sheet columns: %s", list(annotators_df.columns))
    status_values = annotators_df.get("Status", pd.Series()).unique().tolist()
    logger.info("Master sheet rows: %d  |  Status values: %s", len(annotators_df), status_values)
    status_df = annotators_df[annotators_df["Status"] == completed_status]
    group_counts = status_df.groupby("Annotation Group").size()
    logger.info("Group sizes (status='%s'): %s", completed_status, group_counts.to_dict())
    completed_df = status_df.groupby("Annotation Group").filter(lambda x: len(x) >= min_annotators)
    logger.info(
        "Found %d completed annotation sheets in %d groups (min_annotators=%d)",
        len(completed_df),
        completed_df["Annotation Group"].nunique() if not completed_df.empty else 0,
        min_annotators,
    )

    # Discover spreadsheets in Google Drive
    subfolders = (
        drive_service.files()
        .list(
            q=f"'{annotation_folder_id}' in parents and mimeType='application/vnd.google-apps.folder'",
            fields="files(id,name)",
        )
        .execute()
        .get("files", [])
    )
    logger.info("Drive subfolders found: %d — %s", len(subfolders), [f["name"] for f in subfolders])
    all_sheet_meta = []
    for folder in subfolders:
        sheets = (
            drive_service.files()
            .list(
                q=f"'{folder['id']}' in parents and mimeType='application/vnd.google-apps.spreadsheet'",
                fields="files(id,name)",
            )
            .execute()
            .get("files", [])
        )
        for s in sheets:
            all_sheet_meta.append(
                {
                    "group_id": str(folder["name"].replace("_", " ")).title(),
                    "annotation_id": str(s["name"].split("_")[-1]).upper(),
                    "sheet_id": s["id"],
                }
            )
    sheets_df = (
        pd.DataFrame(all_sheet_meta)
        if all_sheet_meta
        else pd.DataFrame(columns=["group_id", "annotation_id", "sheet_id"])
    )
    logger.info("Sheets discovered in Drive: %d", len(sheets_df))
    if not sheets_df.empty and not completed_df.empty:
        logger.info("Drive group_ids sample: %s", sheets_df["group_id"].unique().tolist()[:5])
        logger.info("Master group_ids sample: %s", completed_df["Annotation Group"].unique().tolist()[:5])
        logger.info("Drive annotation_ids sample: %s", sheets_df["annotation_id"].unique().tolist()[:5])
        logger.info("Master annotation_ids sample: %s", completed_df["Annotation Sheet"].unique().tolist()[:5])

    filtered_sheets_df = (
        sheets_df[
            sheets_df["group_id"].isin(completed_df["Annotation Group"])
            & sheets_df["annotation_id"].isin(completed_df["Annotation Sheet"])
        ]
        if not sheets_df.empty and not completed_df.empty
        else pd.DataFrame()
    )
    logger.info("Sheets matched after filtering: %d", len(filtered_sheets_df))

    # Read every annotation worksheet
    all_annotations = []
    for _, row in filtered_sheets_df.iterrows():
        try:
            ws = gc.open_by_key(row["sheet_id"]).worksheet("annotations")
            df = pd.DataFrame(ws.get_all_records())
            df.insert(0, "group_id", row["group_id"])
            df.insert(1, "annotation_id", row["annotation_id"])
            all_annotations.append(df)
            time.sleep(1.2)  # stay under the 60-reads/min Sheets API quota
        except Exception as exc:
            logger.warning("Skipping sheet %s / %s: %s", row["group_id"], row["annotation_id"], exc)

    if not all_annotations:
        raise RuntimeError("No annotation sheets could be loaded — check credentials and sheet access")

    combined_df = pd.concat(all_annotations, ignore_index=True)
    combined_df["is_climate_related"] = combined_df["is_climate_related"].map({"Yes": True, "No": False})

    # Strip bracket-formatted codes, e.g. "[5_1_1] Description" → "5_1_1"
    for col in ("cards_level1", "cards_level2", "cards_level3"):
        combined_df[col] = combined_df[col].apply(
            lambda v: (m.group(1) if (m := _BRACKET_CODE_RE.match(str(v).strip())) else str(v).strip())
            if pd.notna(v) and str(v).strip() != ""
            else pd.NA
        )
    logger.info(
        "Combined %d sheets → %d rows, %d unique documents",
        len(all_annotations),
        len(combined_df),
        combined_df["document_id"].nunique(),
    )

    # Hierarchical majority voting
    content_map = combined_df.drop_duplicates("document_id").set_index("document_id")[["content", "source", "type"]]
    records = []
    skipped = 0
    for doc_id, doc_df in combined_df.groupby("document_id"):
        codes, info = _hierarchical_majority_vote(doc_df)
        logger.debug(
            "doc_id=%s resolved_at=%s codes=%s votes=%s",
            doc_id,
            info["resolved_at"],
            codes,
            {k: info[k] for k in ("climate_votes", "level1_votes", "level2_votes", "level3_votes")},
        )
        if codes is None:
            skipped += 1
            continue
        meta = content_map.loc[doc_id]
        records.append(
            {
                "document_id": doc_id,
                "content": meta["content"],
                "source": meta["source"],
                "type": meta["type"],
                "cards_code": ";".join(codes),
                "agreement_info": _json.dumps(info),
            }
        )

    logger.info(
        "Majority voting complete: %d documents resolved, %d skipped (ambiguous or no CARDS category)",
        len(records),
        skipped,
    )
    return pd.DataFrame(records)


def _load_climatesense_dataset(
    path: str | None,
    limit: int | None,
    climate_only: bool,
    annotation_groups_sheet_url: str,
    annotation_folder_id: str,
    min_annotators: int,
    completed_status: str,
    dataset_name: str,
) -> Dataset:
    """Shared implementation for :func:`climatesense_dataset_v1` and :func:`climatesense_dataset_v2`.

    **Fast path** — if *path* points to an existing CSV, it is loaded directly
    without any network calls.

    **Slow path** — if the file is absent or *path* is ``None``, all annotation
    sheets are downloaded from Google Drive via :func:`_download_annotations_df`,
    and the result is cached to *path* (when set) for future calls.

    Annotations may include depth-3 codes (e.g. ``"5_1_1"``) that the classifier
    cannot produce.  These are projected to depth-2 via :func:`project_to_depth`
    before the cases are built, and duplicates resulting from the projection are
    removed.

    Args:
        path: Path to a cached consensus CSV, or ``None`` to always download.
        limit: Maximum number of cases to include.
        climate_only: When ``True``, exclude ``"0_0"`` (not-climate) documents.
        annotation_groups_sheet_url: URL of the master annotation-groups spreadsheet.
        annotation_folder_id: Google Drive folder ID containing annotation subfolders.
        min_annotators: Minimum annotators required per group.
        completed_status: ``Status`` column value that marks a finished annotation.
        dataset_name: Human-readable name attached to the returned :class:`Dataset`.
    """
    if path is not None and os.path.exists(path):
        logger.info("Loading annotations dataset from cached CSV: %s", path)
        df = pd.read_csv(path).dropna(subset=["document_id", "content", "cards_code"])
    else:
        logger.info("Consensus CSV not found — downloading from Google Drive")
        df = _download_annotations_df(
            annotation_groups_sheet_url, annotation_folder_id, min_annotators, completed_status
        )
        if path is not None:
            os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
            df.to_csv(path, index=False)
            logger.info("Cached consensus CSV to %s", path)

    if climate_only:
        df = df[df["cards_code"] != "0_0"]
    df = df.drop_duplicates(subset=["document_id"]).reset_index(drop=True)
    if limit is not None:
        df = df.head(limit)
    limit_note = f" (limited to {limit})" if limit is not None else ""
    logger.info("Loaded %s: %d cases%s", dataset_name, len(df), limit_note)

    cases = []
    for _, row in df.iterrows():
        # Project to _MAX_CLASSIFIER_DEPTH and deduplicate — annotations may include
        # depth-3 codes (e.g. "5_1_1") that the classifier cannot produce.
        labels = list(
            dict.fromkeys(project_to_depth(c.strip(), _MAX_CLASSIFIER_DEPTH) for c in str(row["cards_code"]).split(";"))
        )
        context = row["context"] if "context" in df.columns and pd.notna(row.get("context")) else None
        cases.append(
            Case(
                name=str(row["document_id"]),
                inputs=CARDSInput(text=str(row["content"]), context=context or None),
                expected_output=labels,
            )
        )

    return Dataset(
        cases=cases,
        name=dataset_name,
        evaluators=_DEFAULT_EVALUATORS,
        report_evaluators=_DEFAULT_REPORT_EVALUATORS,
    )


def climatesense_dataset_v1(
    path: str | None = "data/cards_annotations_v2/cards_annotations_consensus.csv",
    limit: int | None = None,
    climate_only: bool = True,
    annotation_groups_sheet_url: str = "https://docs.google.com/spreadsheets/d/1lFn7kVaZE2AKbBRjrhIPxSCMHwjholZV8CQfrek25u0",
    annotation_folder_id: str = "1SGcdG3AxVqSsOT6ofCiMQcZcTIBOW0kh",
    min_annotators: int = 3,
) -> Dataset:
    """Build a dataset from the ClimateSense annotation round 1.

    When *path* points to an existing CSV the function loads it directly (fast
    path). When the file is absent or *path* is ``None``, all annotation sheets
    are downloaded from Google Drive, majority voting is applied to produce one
    consensus label per claim, and — if *path* is set — the result is cached for
    future calls.

    Majority voting is **hierarchical**: ``cards_level1`` is voted on only by
    annotators who agreed ``is_climate_related=True``; ``cards_level2`` only by
    those who agreed on the winning ``cards_level1``; and so on.  Ties at any
    level produce a set of valid labels, matching the multi-label convention used
    by :func:`nslp_dataset`.

    Requires ``gspread``, ``google-auth``, and ``google-api-python-client`` for
    the download path.  Set ``GOOGLE_APPLICATION_CREDENTIALS`` to a service-account
    JSON with read access to the annotation spreadsheets.

    Args:
        path: Path to a cached consensus CSV.  Loaded directly when the file exists;
            downloaded and saved here otherwise.  Pass ``None`` to always download
            without caching.
        limit: Maximum number of cases.  Defaults to None (all).
        climate_only: When ``True`` (default), exclude ``"0_0"`` (not-climate) entries.
        annotation_groups_sheet_url: URL of the master annotation-groups spreadsheet.
        annotation_folder_id: Google Drive folder ID containing annotation subfolders.
        min_annotators: Minimum annotators required per group to include it.
    """
    return _load_climatesense_dataset(
        path=path,
        limit=limit,
        climate_only=climate_only,
        annotation_groups_sheet_url=annotation_groups_sheet_url,
        annotation_folder_id=annotation_folder_id,
        min_annotators=min_annotators,
        completed_status="Finished",
        dataset_name="ClimateSense Annotations v1",
    )


def climatesense_dataset_v2(
    path: str | None = "data/cards_annotations_v2b/cards_annotations_consensus.csv",
    limit: int | None = None,
    climate_only: bool = True,
    annotation_groups_sheet_url: str = "https://docs.google.com/spreadsheets/d/1TPnG0cAxe4eh_nSV0xQJ7r9dmQoJtq4tqdFpjftZ8rw",
    annotation_folder_id: str = "1GQz59v_-ufwX1WgWgJUHQAWu7NUjxOdg",
    min_annotators: int = 2,
) -> Dataset:
    """Build a dataset from the ClimateSense annotation round 2.

    Same pipeline as :func:`climatesense_dataset_v1`; differs only in the source
    spreadsheet and Drive folder (and uses ``completed_status="done"`` instead of
    ``"Finished"``).

    Args:
        path: Path to a cached consensus CSV.  Loaded directly when the file exists;
            downloaded and saved here otherwise.  Pass ``None`` to always download
            without caching.
        limit: Maximum number of cases.  Defaults to None (all).
        climate_only: When ``True`` (default), exclude ``"0_0"`` (not-climate) entries.
        annotation_groups_sheet_url: URL of the master annotation-groups spreadsheet.
        annotation_folder_id: Google Drive folder ID containing annotation subfolders.
        min_annotators: Minimum annotators required per group to include it.
    """
    return _load_climatesense_dataset(
        path=path,
        limit=limit,
        climate_only=climate_only,
        annotation_groups_sheet_url=annotation_groups_sheet_url,
        annotation_folder_id=annotation_folder_id,
        min_annotators=min_annotators,
        completed_status="done",
        dataset_name="ClimateSense Annotations v2",
    )
