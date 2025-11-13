import argparse
import ast
import json
import re
import sys
from pathlib import Path
from typing import Iterable, List, Optional

try:
    import requests
except ImportError as exc:  # pragma: no cover - requests should be available, but fallback just in case
    raise SystemExit("The 'requests' package is required to run this script") from exc


REPORTS_LIST_MARKER = "reportsList:["
THUMBNAIL_TEMPLATE = "https://datastudio.google.com/reporting/{report_id}/thumbnail?sz=w320-h240-p-k-nu"
STRING_ESCAPE_PATTERN = re.compile(r"\\u[0-9a-fA-F]{4}")


class ReportsParseError(RuntimeError):
    """Raised when the reports list cannot be parsed from the JS payload."""


def fetch_js(source: str, timeout: float = 30.0) -> str:
    """Download the Looker gallery JavaScript bundle or read it from disk."""
    path_candidate = Path(source)
    if path_candidate.exists():
        return path_candidate.read_text(encoding="utf-8")

    if source.startswith("file://"):
        return Path(source[7:]).read_text(encoding="utf-8")

    response = requests.get(source, timeout=timeout)
    response.raise_for_status()
    response.encoding = response.encoding or "utf-8"
    return response.text


def extract_reports_array(js_source: str) -> str:
    """Locate and return the raw JS array string assigned to reportsList."""
    marker_index = js_source.find(REPORTS_LIST_MARKER)
    if marker_index == -1:
        raise ReportsParseError("Unable to locate 'reportsList' marker in JS payload")

    array_start = js_source.find("[", marker_index)
    if array_start == -1:
        raise ReportsParseError("Unable to find opening '[' for reportsList")

    depth = 0
    in_string = False
    string_quote = ""
    escape = False

    for index in range(array_start, len(js_source)):
        char = js_source[index]
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == string_quote:
                in_string = False
        else:
            if char in ('"', "'"):
                in_string = True
                string_quote = char
            elif char == "[":
                depth += 1
            elif char == "]":
                depth -= 1
                if depth == 0:
                    return js_source[array_start : index + 1]
    raise ReportsParseError("Unable to find closing ']' for reportsList array")


def iter_object_literals(array_src: str) -> Iterable[str]:
    depth = 0
    start = None
    in_string = False
    string_quote = ""
    escape = False

    for index, char in enumerate(array_src):
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == string_quote:
                in_string = False
        else:
            if char in ('"', "'"):
                in_string = True
                string_quote = char
            elif char == "{":
                if depth == 0:
                    start = index
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0 and start is not None:
                    yield array_src[start : index + 1]
                    start = None
    return []


def extract_string_field(obj_src: str, key: str) -> Optional[str]:
    key_pattern = f"{key}:"
    pos = obj_src.find(key_pattern)
    if pos == -1:
        return None
    index = pos + len(key_pattern)

    while index < len(obj_src) and obj_src[index].isspace():
        index += 1
    if index >= len(obj_src) or obj_src[index] not in ('"', "'"):
        return None

    quote = obj_src[index]
    value_start = index
    index += 1
    escape = False

    while index < len(obj_src):
        char = obj_src[index]
        if escape:
            escape = False
        elif char == "\\":
            escape = True
        elif char == quote:
            literal = obj_src[value_start : index + 1]
            try:
                value = ast.literal_eval(literal)
            except SyntaxError as exc:  # pragma: no cover - unlikely but guard anyway
                raise ReportsParseError(f"Unable to decode string for key '{key}'") from exc
            if isinstance(value, str):
                value = value.encode("utf-16", "surrogatepass").decode("utf-16")
            return value
        index += 1
    return None


def parse_reports(js_array_src: str) -> List[dict]:
    reports: List[dict] = []
    for obj_src in iter_object_literals(js_array_src):
        report_id = extract_string_field(obj_src, "reportId")
        report_title = extract_string_field(obj_src, "reportTitle")
        report_url = extract_string_field(obj_src, "reportUrl")
        category = extract_string_field(obj_src, "category")
        authorName = extract_string_field(obj_src, "authorName")
        if not (report_id and report_title and report_url):
            continue
        reports.append(
            {
                "reportId": report_id,
                "reportTitle": report_title,
                "reportUrl": report_url,
                "category": category,
                "author":authorName
            }
        )
    return reports


def normalize_category(category_value) -> Optional[str]:
    if category_value is None:
        return None
    if isinstance(category_value, str):
        return category_value
    if isinstance(category_value, Iterable):
        for entry in category_value:
            if entry:
                return str(entry)
    return None


def transform_reports(reports: Iterable[dict]) -> List[dict]:
    items: List[dict] = []
    for report in reports:
        report_id = report.get("reportId")
        report_title = report.get("reportTitle")
        report_url = report.get("reportUrl")
        author = report.get("author")
        if not (report_id and report_title and report_url):
            continue
        category = normalize_category(report.get("category"))
        items.append(
            {
                "title": report_title,
                "author": author,
                "thumbnail_url": THUMBNAIL_TEMPLATE.format(report_id=report_id),
                "category": category,
                "sourceUrl": report_url,
            }
        )
    return items


def write_reports(reports: List[dict], output_path: Path, indent: int = 2) -> None:
    output_path.write_text(
        json.dumps(reports, ensure_ascii=False, indent=indent),
        encoding="utf-8",
    )


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scrape Looker gallery reports metadata.")
    parser.add_argument(
        "--js-url",
        required=True,
        help="URL or local path to the Looker gallery JavaScript bundle (e.g. https://datastudio.google.com/gallery/static/js/...).",
    )
    parser.add_argument(
        "--output",
        default="reports.json",
        help="Path to the output JSON file (default: reports.json)",
    )
    parser.add_argument(
        "--indent",
        type=int,
        default=2,
        help="JSON indentation level (default: 2)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=30.0,
        help="Request timeout in seconds (default: 30)",
    )
    return parser.parse_args(argv)


def main(
    argv: Optional[List[str]] = None,
    *,
    js_url: Optional[str] = None,
    output_path: Optional[Path] = None,
    indent: int = 2,
    timeout: float = 30.0,
    write_output: bool = True,
) -> List[dict]:
    """
    Scrape Looker Studio gallery metadata.

    When called from the command line, provide ``argv`` so argparse handles the CLI
    flags. When used programmatically, pass ``js_url`` (and optionally ``output_path``,
    ``indent``, ``timeout`` and ``write_output``) and omit ``argv``.
    """
    if argv is not None:
        args = parse_args(argv)
        js_url = args.js_url
        output_path = Path(args.output).resolve()
        indent = args.indent
        timeout = args.timeout
        write_output = True
    else:
        if js_url is None:
            raise ValueError("js_url must be provided when argv is not supplied")
        if output_path is not None:
            output_path = Path(output_path)

    try:
        js_source = fetch_js(js_url, timeout=timeout)
        reports_array_src = extract_reports_array(js_source)
        reports_raw = parse_reports(reports_array_src)
        reports = transform_reports(reports_raw)
    except (requests.RequestException, ReportsParseError):
        raise

    if not reports:
        print("Warning: No reports found in the JS payload", file=sys.stderr)

    if write_output and output_path:
        write_reports(reports, output_path, indent=indent)
        print(f"Saved {len(reports)} reports to {output_path}")

    return reports


if __name__ == "__main__":
    try:
        main_reports = main(sys.argv[1:])
    except (requests.RequestException, ReportsParseError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
    sys.exit(0 if main_reports else 1)
