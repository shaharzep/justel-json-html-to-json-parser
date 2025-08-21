#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HTML (.txt) -> JSON extractor (CLI, no GUI).

Features (parity with GUI variant):
- Structured mode (default ON):
    * Auto-anchor: #content1 > #page_main > #conteneur > <body>
    * Parse `.champ-notice-table` / `.description-notice-table` to key/value rows
    * Sections grouped by <fieldset><legend>
    * Attachments index (PDFs, internal /content/, .show-lien)
    * Capture lang + title
    * Optional join of section paragraphs into body_text
    * Optional embed of generic selector dump (debug)
- Legacy generic selector dump (if enabled): selectors -> list of {text, html?, links[]}

Performance & Ops:
- Multiprocessing (default ON) with configurable workers
- Skip existing outputs (default ON) so you can resume runs safely
- Mirrors input directory tree; one JSON per .txt
- Robust encoding fallbacks; safe error handling
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import signal
import sys
import traceback
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Set

# -------- Dependencies --------
try:
    from bs4 import BeautifulSoup
    from bs4.element import Tag
except ImportError:
    print("Please install dependencies first:\n  pip install beautifulsoup4 lxml")
    sys.exit(1)

# -------- Defaults (edit here or via CLI flags) --------
DEFAULT_INCLUDE_HTML = True
DEFAULT_STRIP_NOISE = True
DEFAULT_RECURSE = True
DEFAULT_STRUCTURED = True
DEFAULT_JOIN_PARAGRAPHS = True
DEFAULT_INCLUDE_SELECTOR_DUMP = False
DEFAULT_USE_MP = True
DEFAULT_SKIP_EXISTING = True
DEFAULT_WORKERS = min(8, os.cpu_count() or 4)
DEFAULT_CHUNKSIZE = 32  # batch size for mp map (tune if needed)

DEFAULT_SELECTORS_TEXT = """fieldset
legend
.champ-notice-table
.description-notice-table
.show-lien
p
"""

ANCHOR_CANDIDATES = ["#content1", "#page_main", "#conteneur"]

# -------- Utilities --------
def setup_logging(verbosity: int):
    level = logging.WARNING if verbosity == 0 else logging.INFO if verbosity == 1 else logging.DEBUG
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%H:%M:%S"
    )

def read_text_with_fallbacks(path: Path) -> str:
    encodings = ["utf-8", "utf-16", "latin-1"]
    for enc in encodings:
        try:
            with path.open("r", encoding=enc, errors="strict") as f:
                return f.read()
        except Exception:
            continue
    with path.open("r", encoding="utf-8", errors="replace") as f:
        return f.read()

def parse_html(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "lxml") if "lxml" in sys.modules else BeautifulSoup(html, "html.parser")

def normalize_ws(s: str) -> str:
    return " ".join(s.split()) if isinstance(s, str) else s

def element_links_info(el) -> List[Dict[str, str]]:
    links = []
    for a in el.find_all("a"):
        href = (a.get("href") or "").strip()
        txt = normalize_ws(a.get_text(" ", strip=True)) if a.get_text() else ""
        if href or txt:
            links.append({"href": href, "text": txt})
    return links

def iter_input_files(input_path: Path, recurse: bool) -> List[Path]:
    if input_path.is_file():
        return [input_path]
    pattern = "**/*.txt" if recurse else "*.txt"
    return list(input_path.glob(pattern))

def out_path_for_file(input_root: Path, file_path: Path, out_root: Path) -> Path:
    """
    Mirror input tree and produce <stem>.json.
    """
    if input_root.is_file():
        rel = Path(file_path.name)
    else:
        try:
            rel = file_path.relative_to(input_root)
        except ValueError:
            rel = Path(file_path.name)
    target_name = f"{rel.stem}.json"
    return (out_root / rel.parent / target_name)

# -------- Generic selector dump --------
def parse_selectors(raw: str) -> List[str]:
    parts: List[str] = []
    for line in raw.splitlines():
        if "," in line:
            parts.extend([p.strip() for p in line.split(",") if p.strip()])
        else:
            s = line.strip()
            if s:
                parts.append(s)
    # de-dupe preserving order
    seen = set(); ordered = []
    for s in parts:
        if s not in seen:
            seen.add(s); ordered.append(s)
    return ordered

def extract_for_selector(soup: BeautifulSoup, selector: str, keep_html: bool) -> List[Dict[str, str]]:
    results: List[Dict[str, str]] = []
    try:
        for node in soup.select(selector):
            text = normalize_ws(node.get_text(" ", strip=True)) if node.get_text() else ""
            entry = {"text": text}
            if keep_html:
                entry["html"] = str(node)
            lnks = element_links_info(node)
            if lnks:
                entry["links"] = lnks
            results.append(entry)
    except Exception as e:
        logging.debug("Selector failed: %s | %s", selector, e)
    return results

def generic_selector_dump(soup: BeautifulSoup, selectors: List[str], keep_html: bool) -> Dict:
    extracted = {}
    for sel in selectors:
        s = sel.strip()
        if not s:
            continue
        extracted[s] = extract_for_selector(soup, s, keep_html=keep_html)
    return {
        "selectors": selectors,
        "counts": {sel: len(extracted.get(sel, [])) for sel in selectors},
        "extracted": extracted
    }

# -------- Structured extraction --------
def find_best_anchor(soup: BeautifulSoup) -> Tuple[Tag, str]:
    for sel in ANCHOR_CANDIDATES:
        try:
            node = soup.select_one(sel)
        except Exception:
            node = None
        if node:
            return node, sel
    if soup.body:
        return soup.body, "body"
    return soup, "document"

def cell_texts(cells: List[Tag]) -> List[str]:
    out = []
    for c in cells:
        txt = c.get_text(" ", strip=True) if c else ""
        out.append(normalize_ws(txt))
    return out

def parse_table_to_kv(tbl: Tag, keep_html: bool) -> List[Dict[str, str]]:
    rows_out: List[Dict[str, str]] = []
    for tr in tbl.find_all("tr"):
        ths = tr.find_all("th")
        tds = tr.find_all("td")
        th_txt = cell_texts(ths)
        td_txt = cell_texts(tds)

        label = ""
        value = ""
        if ths and tds:
            label = " ".join([t for t in th_txt if t])
            value = " | ".join([t for t in td_txt if t])
        elif len(tds) >= 2:
            candidate = td_txt[0] or ""
            if candidate.endswith(":") or len(candidate) <= 64:
                label = candidate.rstrip(":")
                value = " | ".join([t for t in td_txt[1:] if t])
            else:
                label = candidate
                value = " | ".join([t for t in td_txt[1:] if t])
        elif ths and not tds:
            label = " ".join([t for t in th_txt if t])
            value = ""
        elif tds and len(tds) == 1:
            label = ""
            value = td_txt[0] or ""
        else:
            continue

        row = {"label": label, "value": value}
        if keep_html:
            row["row_html"] = str(tr)
        rows_out.append(row)
    return rows_out

def parse_metadata_tables(anchor: Tag, keep_html: bool) -> Dict[str, List[Dict[str, str]]]:
    out = {"champ_notice": [], "description_notice": []}
    for tbl in anchor.select(".champ-notice-table"):
        out["champ_notice"].extend(parse_table_to_kv(tbl, keep_html))
    for tbl in anchor.select(".description-notice-table"):
        out["description_notice"].extend(parse_table_to_kv(tbl, keep_html))
    return out

def sectionize_by_fieldset(anchor: Tag, keep_html: bool, join_paragraphs: bool) -> Tuple[List[Dict], Dict]:
    sections: List[Dict] = []
    p_ids_in_fieldsets: Set[int] = set()

    for fs in anchor.find_all("fieldset"):
        legend = ""
        lg = fs.find("legend")
        if lg:
            legend = normalize_ws(lg.get_text(" ", strip=True))
        paras = []
        links = []
        for p in fs.find_all("p"):
            p_ids_in_fieldsets.add(id(p))
            txt = normalize_ws(p.get_text(" ", strip=True)) if p.get_text() else ""
            entry = {"text": txt}
            if keep_html:
                entry["html"] = str(p)
            lnks = element_links_info(p)
            if lnks:
                entry["links"] = lnks
            paras.append(entry)
            links.extend(lnks)

        sec = {"legend": legend, "paragraphs": paras}
        if links:
            sec["links"] = links
        if join_paragraphs:
            body_text = "\n\n".join([e["text"] for e in paras if e.get("text")])
            sec["body_text"] = body_text
        sections.append(sec)

    unsec_paras = []
    unsec_links = []
    for p in anchor.find_all("p"):
        if id(p) in p_ids_in_fieldsets:
            continue
        txt = normalize_ws(p.get_text(" ", strip=True)) if p.get_text() else ""
        entry = {"text": txt}
        if keep_html:
            entry["html"] = str(p)
        lnks = element_links_info(p)
        if lnks:
            entry["links"] = lnks
        unsec_paras.append(entry)
        unsec_links.extend(lnks)

    unsectioned = {"paragraphs": unsec_paras}
    if unsec_links:
        unsectioned["links"] = unsec_links
    if join_paragraphs:
        unsectioned["body_text"] = "\n\n".join([e["text"] for e in unsec_paras if e.get("text")])

    return sections, unsectioned

def collect_attachments(anchor: Tag) -> Dict[str, List[Dict[str, str]]]:
    seen = set()
    def push(container: List[Dict[str, str]], href: str, text: str):
        key = (href, text)
        if href and key not in seen:
            container.append({"href": href, "text": text})
            seen.add(key)

    show_lien = []
    pdfs = []
    internal = []

    for a in anchor.find_all("a"):
        href = (a.get("href") or "").strip()
        if not href:
            continue
        text = normalize_ws(a.get_text(" ", strip=True)) if a.get_text() else ""
        cls = a.get("class") or []
        if "show-lien" in cls:
            push(show_lien, href, text)
        if href.lower().endswith(".pdf"):
            push(pdfs, href, text)
        if "/content/" in href:
            push(internal, href, text)

    return {"show_lien": show_lien, "pdfs": pdfs, "internal": internal}

def structured_extract(soup: BeautifulSoup, keep_html: bool, include_selector_dump: bool,
                       selectors: List[str], join_paragraphs: bool) -> Dict:
    html_tag = soup.find("html")
    lang = (html_tag.get("lang") or "").upper() if html_tag and html_tag.get("lang") else None
    title = normalize_ws(soup.title.get_text()) if soup.title else None

    anchor, anchor_name = find_best_anchor(soup)
    tables = parse_metadata_tables(anchor, keep_html)
    sections, unsectioned = sectionize_by_fieldset(anchor, keep_html, join_paragraphs)
    attachments = collect_attachments(anchor)

    raw_dump = None
    if include_selector_dump and selectors:
        raw_dump = generic_selector_dump(anchor, selectors, keep_html)

    counts = {
        "tables": {
            "champ_notice": len(tables.get("champ_notice", [])),
            "description_notice": len(tables.get("description_notice", [])),
        },
        "sections": len(sections),
        "unsectioned_paragraphs": len(unsectioned.get("paragraphs", [])),
        "attachments": {k: len(v) for k, v in attachments.items()}
    }

    doc = {
        "file": None,  # filled by caller
        "lang": lang,
        "title": title,
        "anchor_used": anchor_name,
        "tables": tables,
        "sections": sections,
        "unsectioned": unsectioned,
        "attachments": attachments,
        "counts": counts
    }
    if raw_dump is not None:
        doc["raw_from_selectors"] = raw_dump
    return doc

# -------- Single-file process --------
def process_one_file(input_root: Path, file_path: Path, out_root: Path,
                     selectors: List[str], keep_html: bool, strip_noise: bool,
                     structured: bool, join_paragraphs: bool, include_selector_dump: bool) -> Tuple[bool, str]:
    try:
        html = read_text_with_fallbacks(file_path)
        soup = parse_html(html)

        if strip_noise:
            for tag in soup(["script", "style", "noscript"]):
                tag.decompose()

        if structured:
            doc = structured_extract(
                soup=soup,
                keep_html=keep_html,
                include_selector_dump=include_selector_dump,
                selectors=selectors,
                join_paragraphs=join_paragraphs,
            )
            doc["file"] = str(file_path)
        else:
            dump = generic_selector_dump(soup, selectors, keep_html)
            doc = {"file": str(file_path), **dump}

        out_path = out_path_for_file(input_root, file_path, out_root)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with out_path.open("w", encoding="utf-8") as f:
            json.dump(doc, f, ensure_ascii=False, indent=2)

        return True, str(out_path)
    except Exception as e:
        return False, f"{e}"

# For multiprocessing
def _mp_task(args: Tuple[Path, Path, Path, List[str], bool, bool, bool, bool, bool]) -> Tuple[Path, bool, str]:
    (input_root, file_path, out_root, selectors, keep_html, strip_noise,
     structured, join_paragraphs, include_selector_dump) = args
    ok, msg = process_one_file(input_root, file_path, out_root, selectors, keep_html,
                               strip_noise, structured, join_paragraphs, include_selector_dump)
    return file_path, ok, msg

# -------- CLI --------
def parse_args():
    p = argparse.ArgumentParser(description="Convert HTML-in-.txt files to JSON (structured) at scale.")
    p.add_argument("--input", required=True, help="Path to a .txt file OR a folder of .txt files")
    p.add_argument("--output", required=True, help="Directory to write JSON files")

    # Behavior toggles (defaults per your request)
    p.add_argument("--recurse", action=argparse.BooleanOptionalAction, default=DEFAULT_RECURSE,
                   help=f"Recurse subfolders when input is a directory (default: {DEFAULT_RECURSE})")
    p.add_argument("--include-html", dest="include_html", action=argparse.BooleanOptionalAction,
                   default=DEFAULT_INCLUDE_HTML, help=f"Include raw HTML snippets (default: {DEFAULT_INCLUDE_HTML})")
    p.add_argument("--strip-noise", dest="strip_noise", action=argparse.BooleanOptionalAction,
                   default=DEFAULT_STRIP_NOISE, help=f"Strip <script>/<style>/<noscript> (default: {DEFAULT_STRIP_NOISE})")
    p.add_argument("--structured", action=argparse.BooleanOptionalAction, default=DEFAULT_STRUCTURED,
                   help=f"Structured mode ON/OFF (default: {DEFAULT_STRUCTURED})")
    p.add_argument("--join-paragraphs", dest="join_paragraphs", action=argparse.BooleanOptionalAction,
                   default=DEFAULT_JOIN_PARAGRAPHS, help=f"Join paragraphs into 'body_text' (default: {DEFAULT_JOIN_PARAGRAPHS})")
    p.add_argument("--include-selector-dump", dest="include_selector_dump", action=argparse.BooleanOptionalAction,
                   default=DEFAULT_INCLUDE_SELECTOR_DUMP, help=f"Also include generic selector dump in output (default: {DEFAULT_INCLUDE_SELECTOR_DUMP})")

    # Selectors
    p.add_argument("--selectors", help="Selectors string (comma- or newline-separated). "
                                       "If omitted, defaults to built-in list.")
    p.add_argument("--selectors-file", help="Path to a text file containing selectors (one per line).")

    # Performance
    p.add_argument("--use-mp", dest="use_mp", action=argparse.BooleanOptionalAction,
                   default=DEFAULT_USE_MP, help=f"Use multiprocessing (default: {DEFAULT_USE_MP})")
    p.add_argument("--workers", type=int, default=DEFAULT_WORKERS,
                   help=f"Number of workers when multiprocessing (default: {DEFAULT_WORKERS})")
    p.add_argument("--skip-existing", dest="skip_existing", action=argparse.BooleanOptionalAction,
                   default=DEFAULT_SKIP_EXISTING, help=f"Skip files with an existing JSON output (default: {DEFAULT_SKIP_EXISTING})")
    p.add_argument("--chunksize", type=int, default=DEFAULT_CHUNKSIZE,
                   help=f"Chunksize for multiprocessing map (default: {DEFAULT_CHUNKSIZE})")

    # Logging
    p.add_argument("-v", "--verbose", action="count", default=1, help="Increase verbosity (-v, -vv)")

    return p.parse_args()

def main():
    args = parse_args()
    setup_logging(args.verbose)

    input_path = Path(args.input).expanduser()
    out_root = Path(args.output).expanduser()
    out_root.mkdir(parents=True, exist_ok=True)

    if not input_path.exists():
        logging.error("Input path not found: %s", input_path)
        sys.exit(1)

    # Build selectors
    if args.selectors_file:
        sel_text = Path(args.selectors_file).read_text(encoding="utf-8")
    elif args.selectors:
        sel_text = args.selectors
    else:
        sel_text = DEFAULT_SELECTORS_TEXT
    selectors = parse_selectors(sel_text)

    # Build task list
    files = iter_input_files(input_path, recurse=args.recurse)
    if not files:
        logging.warning("No .txt files found at input: %s", input_path)
        sys.exit(0)

    tasks = []
    skipped = 0
    for fp in files:
        outp = out_path_for_file(input_path, fp, out_root)
        if args.skip_existing and outp.exists():
            skipped += 1
            continue
        tasks.append((
            input_path, fp, out_root, selectors,
            args.include_html, args.strip_noise,
            args.structured, args.join_paragraphs, args.include_selector_dump
        ))

    logging.info("Start | tasks=%d (skipped existing=%d) | mp=%s workers=%d | output=%s",
                 len(tasks), skipped, args.use_mp, args.workers, out_root)

    total = len(tasks)
    ok = 0
    fail = 0

    if total == 0:
        logging.info("Nothing to do (all outputs exist).")
        return

    # Handle Ctrl+C gracefully
    stop_flag = {"stop": False}
    def _sigint_handler(signum, frame):
        stop_flag["stop"] = True
        logging.warning("Cancellation requested? finishing in-flight tasks.")
    signal.signal(signal.SIGINT, _sigint_handler)

    if args.use_mp and total > 1:
        try:
            with ProcessPoolExecutor(max_workers=max(1, args.workers)) as ex:
                # Streamed map to keep memory bounded
                for (file_path, success, msg) in ex.map(_mp_task, tasks, chunksize=max(1, args.chunksize)):
                    if success:
                        ok += 1
                        if ok % 100 == 0 or args.verbose >= 2:
                            logging.info("OK  | %s -> %s", file_path, msg)
                    else:
                        fail += 1
                        logging.error("ERR | %s | %s", file_path, msg)
                    if stop_flag["stop"]:
                        # Cancel remaining futures
                        ex.shutdown(cancel_futures=True)
                        break
        except Exception as e:
            logging.error("FATAL | Multiprocessing error: %s", e)
            logging.debug(traceback.format_exc())
    else:
        for (input_root, file_path, out_root_, selectors_, keep_html, strip_noise,
             structured, join_paragraphs, include_selector_dump) in tasks:
            if stop_flag["stop"]:
                break
            success, msg = process_one_file(input_root, file_path, out_root_, selectors_,
                                            keep_html, strip_noise, structured,
                                            join_paragraphs, include_selector_dump)
            if success:
                ok += 1
                if ok % 100 == 0 or args.verbose >= 2:
                    logging.info("OK  | %s -> %s", file_path, msg)
            else:
                fail += 1
                logging.error("ERR | %s | %s", file_path, msg)

    logging.warning("DONE | processed=%d ok=%d fail=%d | output=%s", ok+fail, ok, fail, out_root)

if __name__ == "__main__":
    main()
