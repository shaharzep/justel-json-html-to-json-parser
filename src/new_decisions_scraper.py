#!/usr/bin/env python3
"""
JuPortal Decisions URL Scraper (Phase 1)
1. Scrapes new decision URLs from JuPortal starting from the last date in urls.csv
2. Saves URLs to CSV immediately after discovery
3. HTML download is handled separately by parallel_html_downloader.py for speed
"""

import csv
import logging
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Tuple, Optional

from playwright.sync_api import sync_playwright, Page
from playwright_recaptcha import recaptchav2

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Constants
URLS_CSV_PATH = Path(__file__).parent.parent / "urls_data" / "urls.csv"
HTMLS_DIR = Path(__file__).parent / "htmls"  # Now in src/htmls
NEW_URLS_SESSION_PATH = Path(__file__).parent.parent / "new_urls_session.txt"
JUPORTAL_FORM_URL = "https://juportal.be/moteur/formulaire"
BASE_URL = "https://juportal.be"


def get_last_date_from_csv() -> Tuple[datetime, int]:
    """
    Read the last row from urls.csv and extract the date.
    Returns: (last_date, total_rows_count)
    """
    if not URLS_CSV_PATH.exists():
        logger.error(f"CSV file not found: {URLS_CSV_PATH}")
        sys.exit(1)
    
    # Get the last line efficiently
    with open(URLS_CSV_PATH, 'rb') as f:
        # Seek to end minus 1KB (should be enough for last few lines)
        try:
            f.seek(-1024, os.SEEK_END)
        except OSError:
            f.seek(0)
        
        lines = f.read().decode('utf-8', errors='ignore').strip().split('\n')
        last_line = lines[-1] if lines else ""
    
    # Count total rows for logging
    with open(URLS_CSV_PATH, 'r', encoding='utf-8') as f:
        total_rows = sum(1 for _ in f)
    
    if not last_line:
        logger.error("CSV file is empty")
        sys.exit(1)
    
    # Parse the last line
    parts = last_line.split(',')
    if len(parts) < 3:
        logger.error(f"Invalid CSV format in last line: {last_line}")
        sys.exit(1)
    
    # Extract date from the third column
    # Handle both DD/MM/YYYY and MM/DD/YYYY formats
    date_str = parts[2].strip()
    if not date_str:
        logger.error("No date found in last row")
        sys.exit(1)
    
    try:
        # The date "07/02/2025" is July 2nd, 2025 (MM/DD format)
        # Try MM/DD/YYYY format first
        try:
            last_date = datetime.strptime(date_str, "%m/%d/%Y")
            logger.info(f"Last scraped date (MM/DD format): {date_str} = {last_date.strftime('%B %d, %Y')}")
        except ValueError:
            # Fall back to DD/MM/YYYY format
            last_date = datetime.strptime(date_str, "%d/%m/%Y")
            logger.info(f"Last scraped date (DD/MM format): {date_str} = {last_date.strftime('%B %d, %Y')}")
        
        logger.info(f"Total existing rows in CSV: {total_rows}")
        return last_date, total_rows
    except ValueError as e:
        logger.error(f"Invalid date format '{date_str}': {e}")
        sys.exit(1)


def format_date_for_form(date: datetime) -> str:
    """Format date as DD/MM/YYYY for the form"""
    return date.strftime("%d/%m/%Y")


def fill_search_form(page: Page, from_date: datetime, to_date: datetime) -> bool:
    """
    Fill the search form with date range and handle reCAPTCHA.
    Returns True if successful, False otherwise.
    """
    try:
        logger.info(f"Navigating to {JUPORTAL_FORM_URL}")
        page.goto(JUPORTAL_FORM_URL, wait_until="networkidle")
        
        # Wait for form to load - wait for date inputs specifically
        page.wait_for_selector('input[type="date"]', timeout=10000)
        
        logger.info("Filling date range fields...")
        
        # Format dates for date input fields (YYYY-MM-DD format)
        from_date_str = from_date.strftime("%Y-%m-%d")
        to_date_str = to_date.strftime("%Y-%m-%d")
        
        logger.info(f"Date range: {from_date_str} to {to_date_str}")
        
        # Fill the date fields using the correct field names
        # TRECHPUBLICATDE = Introduction date FROM
        # TRECHPUBLICATA = Introduction date TO
        page.fill('input[name="TRECHPUBLICATDE"]', from_date_str)
        logger.info(f"Filled 'Date d'introduction de' with {from_date_str}")
        
        page.fill('input[name="TRECHPUBLICATA"]', to_date_str)
        logger.info(f"Filled 'Date d'introduction à' with {to_date_str}")
        
        # Handle reCAPTCHA
        logger.info("Checking for reCAPTCHA...")
        recaptcha_frame = page.query_selector('iframe[src*="recaptcha"]')
        
        if recaptcha_frame:
            logger.info("reCAPTCHA detected, attempting to solve...")
            try:
                # Use playwright-recaptcha to solve
                with recaptchav2.SyncSolver(page) as solver:
                    token = solver.solve_recaptcha()
                    if token:
                        logger.info("reCAPTCHA solved successfully")
                    else:
                        logger.warning("Failed to solve reCAPTCHA")
                        return False
            except Exception as e:
                logger.error(f"Error solving reCAPTCHA: {e}")
                logger.info("Proceeding without solving - may require manual intervention")
        
        # Submit the form
        logger.info("Submitting search form...")
        
        # Try to find and click submit button
        submit_button = (
            page.query_selector('button[type="submit"]') or
            page.query_selector('input[type="submit"]') or
            page.query_selector('button:has-text("Rechercher")') or
            page.query_selector('button:has-text("Search")')
        )
        
        if submit_button:
            submit_button.click()
            # Wait for navigation or results to load
            page.wait_for_load_state("networkidle")
            logger.info("Form submitted successfully")
            return True
        else:
            logger.error("Could not find submit button")
            return False
            
    except Exception as e:
        logger.error(f"Error filling form: {e}")
        return False


def extract_decisions_from_page(page: Page) -> List[Tuple[str, str]]:
    """
    Extract decision URLs and IDs from the current results page.
    Returns list of (url_path, ecli_id) tuples.
    """
    decisions = []
    
    try:
        # Wait for results to load with longer timeout
        page.wait_for_selector('a[href*="/content/ECLI"]', timeout=10000)
        
        # Additional wait to ensure page is stable
        page.wait_for_load_state("networkidle")
        
        # Find all decision links
        links = page.query_selector_all('a[href*="/content/ECLI"]')
        
        for link in links:
            # Check if the link text starts with "ECLI:BE" to ensure it's a decision
            link_text = link.text_content()
            if not link_text or not link_text.strip().startswith('ECLI:BE'):
                continue
            
            href = link.get_attribute('href')
            if not href or not href.startswith('/content/ECLI'):
                continue
            
            # First, remove any URL fragments (parts after #)
            # This handles cases like #text/FR, #notice1/NL, etc.
            if '#' in href:
                href = href.split('#')[0]
            
            # Then remove any trailing language suffix
            # Some URLs might have /FR or /NL before the fragment
            if href.endswith('/FR'):
                href = href[:-3]
            elif href.endswith('/NL'):
                href = href[:-3]
            
            # Extract ECLI ID from the clean URL
            # Format: /content/ECLI:BE:COURT:YEAR:TYPE.DATE.NUMBER
            ecli_id = href.replace('/content/', '').split('/')[0]
            
            # Convert colons to underscores for consistency
            ecli_id_formatted = ecli_id.replace(':', '_')
            
            decisions.append((href, ecli_id_formatted))
        
        logger.info(f"Found {len(decisions)} decisions on current page")
        
    except Exception as e:
        logger.warning(f"No results found or error extracting: {e}")
    
    return decisions


def handle_pagination(page: Page) -> List[Tuple[str, str]]:
    """
    Handle pagination and extract all decisions from all pages.
    Returns complete list of (url_path, ecli_id) tuples.
    """
    all_decisions = []
    page_num = 1
    
    # Check total results count first
    try:
        result_text = page.query_selector('text=/\\d+ résultat/')
        if result_text:
            count_text = result_text.text_content()
            logger.info(f"Total results shown on page: {count_text}")
    except:
        pass
    
    # First, try to set results per page to 1000
    try:
        dropdown = page.query_selector('select[name="COMBONPPAGE"]')
        if dropdown:
            logger.info("Setting results per page to 1000...")
            dropdown.select_option(value="1000")
            # Wait for page to reload with new results
            page.wait_for_load_state("networkidle")
            time.sleep(3)  # Give more time for the page to stabilize
            
            # Wait for results to be visible again after reload
            try:
                page.wait_for_selector('a[href*="/content/ECLI"]', timeout=10000)
                # Log the new results count after changing page size
                result_text = page.query_selector('text=/\\d+ résultat/')
                if result_text:
                    count_text = result_text.text_content()
                    logger.info(f"Results after setting 1000 per page: {count_text}")
            except:
                logger.warning("Results not immediately visible after changing page size")
    except Exception as e:
        logger.warning(f"Could not set results per page: {e}")
    
    while True:
        logger.info(f"Processing page {page_num}...")
        
        # Extract decisions from current page
        decisions = extract_decisions_from_page(page)
        all_decisions.extend(decisions)
        
        # Check for next page
        try:
            next_button = page.query_selector('a:has-text("Suivant")') or \
                         page.query_selector('a:has-text("Next")') or \
                         page.query_selector('a[rel="next"]')
            
            if next_button and next_button.is_enabled():
                logger.info("Moving to next page...")
                next_button.click()
                page.wait_for_load_state("networkidle")
                page_num += 1
                time.sleep(2)  # Be polite to the server and let page stabilize
            else:
                logger.info(f"No more pages. Total pages processed: {page_num}")
                break
        except Exception as e:
            logger.warning(f"Error checking for next page: {e}")
            logger.info(f"Assuming no more pages. Total pages processed: {page_num}")
            break
    
    # Remove duplicates while preserving order
    seen = set()
    unique_decisions = []
    for decision in all_decisions:
        if decision not in seen:
            seen.add(decision)
            unique_decisions.append(decision)
    
    logger.info(f"Total unique decisions found: {len(unique_decisions)}")
    return unique_decisions


def check_url_exists(url: str, ecli_id: str) -> bool:
    """
    Check if a URL already exists in the CSV.
    Returns True if exists, False otherwise.
    """
    if not URLS_CSV_PATH.exists():
        return False
    
    with open(URLS_CSV_PATH, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        for row in reader:
            if len(row) >= 2 and (row[0] == url or row[1] == ecli_id):
                return True
    return False


def append_to_csv(url: str, ecli_id: str, date_str: str):
    """
    Append a single row to the CSV file.
    """
    # First ensure the file ends with a newline
    with open(URLS_CSV_PATH, 'rb+') as f:
        # Go to end of file
        f.seek(0, 2)
        # Check if we're at start of file (empty) or check last character
        if f.tell() > 0:
            f.seek(-1, 2)
            last_byte = f.read(1)
            if last_byte != b'\n':
                f.write(b'\n')
    
    # Now append the new row
    with open(URLS_CSV_PATH, 'a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([url, ecli_id, date_str])


def save_decisions_to_csv(decisions: List[Tuple[str, str]], scrape_date: datetime):
    """
    Save discovered URLs directly to CSV without downloading HTML.
    Also tracks new URLs in a session file for the HTML downloader.
    HTML download will be handled separately for speed.
    """
    if not decisions:
        logger.warning("No decisions to save")
        return
    
    # Use DD/MM/YYYY format consistently
    date_str = scrape_date.strftime("%d/%m/%Y")
    
    new_urls = 0
    skipped = 0
    new_urls_list = []  # Track new URLs for session file
    
    logger.info(f"Saving {len(decisions)} decisions (x2 languages) to CSV...")
    
    for url_path, ecli_id in decisions:
        # Process French version
        url_fr = f"{BASE_URL}{url_path}/FR"
        id_fr = f"{ecli_id}-FR"
        
        if not check_url_exists(url_fr, id_fr):
            append_to_csv(url_fr, id_fr, date_str)
            new_urls_list.append((url_fr, id_fr, date_str))
            new_urls += 1
        else:
            skipped += 1
        
        # Process Dutch version
        url_nl = f"{BASE_URL}{url_path}/NL"
        id_nl = f"{ecli_id}-NL"
        
        if not check_url_exists(url_nl, id_nl):
            append_to_csv(url_nl, id_nl, date_str)
            new_urls_list.append((url_nl, id_nl, date_str))
            new_urls += 1
        else:
            skipped += 1
    
    logger.info(f"CSV update complete: {new_urls} new URLs added, {skipped} already existed")
    
    # Save new URLs to session file for the HTML downloader
    if new_urls_list:
        with open(NEW_URLS_SESSION_PATH, 'w', encoding='utf-8') as f:
            # Write header
            f.write("url,ecli_id,date\n")
            # Write new URLs
            for url, ecli_id, date in new_urls_list:
                f.write(f"{url},{ecli_id},{date}\n")
        logger.info(f"Saved {len(new_urls_list)} new URLs to session file: {NEW_URLS_SESSION_PATH}")
    
    return new_urls


def main():
    """Main scraping function"""
    logger.info("Starting JuPortal Decisions URL Scraper (Phase 1 - URL Discovery Only)")
    
    # Get last date from CSV
    last_date, initial_rows = get_last_date_from_csv()
    
    # Calculate date range
    from_date = last_date + timedelta(days=1)
    to_date = datetime.now()
    
    if from_date > to_date:
        logger.info("No new dates to scrape. CSV is up to date!")
        # Clear any existing session file since there are no new URLs
        if NEW_URLS_SESSION_PATH.exists():
            NEW_URLS_SESSION_PATH.unlink()
        return
    
    logger.info(f"Will scrape from {from_date.strftime('%d/%m/%Y')} to {to_date.strftime('%d/%m/%Y')}")
    
    # Start Playwright
    with sync_playwright() as p:
        # Launch browser in headless mode for server deployment
        # Set headless=False for debugging
        headless = os.environ.get('BROWSER_HEADLESS', 'true').lower() == 'true'
        
        browser = p.chromium.launch(
            headless=headless,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--lang=fr-FR',  # Force French locale
                '--accept-lang=fr-FR,fr'
            ]
        )
        
        logger.info(f"Browser launched (headless={headless})")
        
        try:
            # Create a new page with French locale
            context = browser.new_context(
                locale='fr-FR',
                timezone_id='Europe/Brussels'
            )
            page = context.new_page()
            
            # Set viewport
            page.set_viewport_size({"width": 1280, "height": 720})
            
            # Fill and submit the search form
            if not fill_search_form(page, from_date, to_date):
                logger.error("Failed to submit search form")
                return
            
            # Wait a bit for results to load
            time.sleep(3)
            
            # Extract all decisions (handles pagination)
            decisions = handle_pagination(page)
            
            if decisions:
                # Save URLs to CSV immediately (no HTML download)
                save_decisions_to_csv(decisions, to_date)
                
                # Verify the save
                with open(URLS_CSV_PATH, 'r', encoding='utf-8') as f:
                    final_rows = sum(1 for _ in f)
                
                logger.info(f"Scraping completed successfully!")
                logger.info(f"Initial rows: {initial_rows}")
                logger.info(f"Final rows: {final_rows}")
                logger.info(f"New rows added: {final_rows - initial_rows}")
            else:
                logger.warning("No decisions found for the specified date range")
            
        except Exception as e:
            logger.error(f"Scraping failed: {e}")
            raise
        finally:
            browser.close()
    
    logger.info("Scraper finished")


if __name__ == "__main__":
    main()