from __future__ import annotations

from dataclasses import dataclass
import os
import subprocess
import time
from typing import Iterable

import certifi  # type: ignore
from selenium import webdriver  # type: ignore
from selenium.webdriver.common.by import By  # type: ignore
from selenium.webdriver.chrome.options import Options  # type: ignore
from selenium.webdriver.chrome.service import Service  # type: ignore
from selenium.webdriver.support import expected_conditions as EC  # type: ignore
from selenium.webdriver.support.ui import WebDriverWait  # type: ignore
from webdriver_manager.chrome import ChromeDriverManager  # type: ignore

VERBOSE = False


@dataclass
class ClassSection:
    course_number: str
    instructor: str
    seat_text: str
    available_seats: int
    is_watched: bool = False


class MonitorError(RuntimeError):
    """Raised when the ASU class monitor cannot fetch or parse results."""


def log(message: str) -> None:
    if VERBOSE:
        print(message)


def parse_csv_list(raw_value: str | None) -> list[str]:
    if not raw_value:
        return []
    return [item.strip() for item in raw_value.split(",") if item.strip()]


def parse_seats(seat_text: str) -> int:
    try:
        return int(seat_text.split()[0])
    except (IndexError, ValueError):
        log(f"Warning: Could not parse seat text: {seat_text}")
        return 0


def build_class_list_url(subject: str, catalog_nbr: str, term: str) -> str:
    base_url = "https://catalog.apps.asu.edu/catalog/classes/classlist"
    params = (
        f"?campusOrOnlineSelection=A&catalogNbr={catalog_nbr}"
        f"&honors=F&promod=F&searchType=all&subject={subject}&term={term}"
    )
    return base_url + params


def _configure_tls_cert_bundle() -> None:
    """Avoid stale virtualenv certificate paths breaking webdriver downloads."""
    tls_env_vars = ["SSL_CERT_FILE", "REQUESTS_CA_BUNDLE", "CURL_CA_BUNDLE"]

    for env_var in tls_env_vars:
        env_value = os.environ.get(env_var)
        if env_value and not os.path.exists(env_value):
            os.environ.pop(env_var, None)

    certifi_bundle = certifi.where()
    if os.path.exists(certifi_bundle):
        os.environ.setdefault("SSL_CERT_FILE", certifi_bundle)
        os.environ.setdefault("REQUESTS_CA_BUNDLE", certifi_bundle)


def _create_driver() -> webdriver.Chrome:
    _configure_tls_cert_bundle()
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1600,1200")
    return webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=chrome_options,
    )


def _find_section_elements(driver: webdriver.Chrome) -> list:
    """Try several result layouts because ASU's catalog markup shifts over time."""
    section_xpath = "//div[.//div[contains(@class, 'number')] and .//div[contains(@class, 'seats')]]"
    sections = driver.find_elements(By.XPATH, section_xpath)
    if sections:
        return sections

    expandable_buttons = driver.find_elements(By.XPATH, "//button[@aria-expanded='false']")
    for button in expandable_buttons[:12]:
        try:
            driver.execute_script("arguments[0].click();", button)
            time.sleep(0.1)
        except Exception:
            continue

    return driver.find_elements(By.XPATH, section_xpath)


def fetch_class_sections(
    subject: str,
    catalog_nbr: str,
    term: str,
    watched_course_numbers: Iterable[str] | None = None,
) -> tuple[str, list[ClassSection]]:
    watched = {value.strip() for value in watched_course_numbers or [] if value.strip()}
    full_url = build_class_list_url(subject, catalog_nbr, term)
    driver = _create_driver()

    try:
        log(f"Loading URL: {full_url}")
        driver.get(full_url)
        WebDriverWait(driver, 15).until(
            lambda current_driver: current_driver.execute_script("return document.readyState") == "complete"
        )
        time.sleep(2)

        sections = _find_section_elements(driver)

        if not sections:
            raise MonitorError(
                "No class sections were found. Verify the subject, catalog number, term, and campus availability."
            )

        parsed_sections: list[ClassSection] = []
        for section in sections:
            try:
                course_number = section.find_element(
                    By.XPATH,
                    ".//div[contains(@class, 'number')]",
                ).text.strip()
                try:
                    instructor = section.find_element(
                        By.XPATH,
                        ".//div[contains(@class, 'instructor')]/a",
                    ).text.strip()
                except Exception:
                    instructor = section.find_element(
                        By.XPATH,
                        ".//div[contains(@class, 'instructor')]",
                    ).text.strip()

                seat_text = section.find_element(
                    By.XPATH,
                    ".//div[contains(@class, 'seats')]",
                ).text.strip()
                available_seats = parse_seats(seat_text)

                parsed_sections.append(
                    ClassSection(
                        course_number=course_number,
                        instructor=instructor or "Staff",
                        seat_text=seat_text,
                        available_seats=available_seats,
                        is_watched=course_number in watched,
                    )
                )
            except Exception as exc:
                log(f"Warning: Skipping section due to missing data: {exc}")

        if not parsed_sections:
            raise MonitorError("The page loaded, but no section data could be parsed.")

        return full_url, parsed_sections
    except MonitorError:
        raise
    except Exception as exc:
        raise MonitorError(str(exc)) from exc
    finally:
        driver.quit()


def send_imessage(phone_numbers: Iterable[str], message: str) -> int:
    sent_count = 0
    for phone_number in phone_numbers:
        cleaned_number = phone_number.strip()
        if not cleaned_number:
            continue

        applescript = f'''
        tell application "Messages"
            set targetService to 1st service whose service type = iMessage
            set targetBuddy to buddy "{cleaned_number}" of targetService
            send "{message}" to targetBuddy
        end tell
        '''

        subprocess.run(["osascript", "-e", applescript], check=True)
        sent_count += 1

    return sent_count


def notify_for_open_sections(
    sections: Iterable[ClassSection],
    subject: str,
    catalog_nbr: str,
    phone_numbers: Iterable[str],
) -> tuple[int, list[str]]:
    messages: list[str] = []
    phone_numbers = [number for number in phone_numbers if number.strip()]
    if not phone_numbers:
        return 0, messages

    sent_total = 0
    for section in sections:
        if not section.is_watched or section.available_seats <= 0:
            continue

        message = (
            f"Seats are available for {subject}-{catalog_nbr}-{section.course_number}: "
            f"{section.available_seats} seats!"
        )
        sent_total += send_imessage(phone_numbers, message)
        messages.append(message)

    return sent_total, messages
