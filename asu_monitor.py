from __future__ import annotations

from dataclasses import dataclass
import subprocess
import time
from typing import Iterable

from selenium import webdriver  # type: ignore
from selenium.webdriver.common.by import By  # type: ignore
from selenium.webdriver.chrome.options import Options  # type: ignore
from selenium.webdriver.chrome.service import Service  # type: ignore
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
        f"?campus=ICOURSE%2CTEMPE&campusOrOnlineSelection=A&catalogNbr={catalog_nbr}"
        f"&honors=F&promod=F&searchType=all&subject={subject}&term={term}"
    )
    return base_url + params


def _create_driver() -> webdriver.Chrome:
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1600,1200")
    return webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=chrome_options,
    )


def fetch_class_sections(
    subject: str,
    catalog_nbr: str,
    term: str,
    watched_course_numbers: Iterable[str] | None = None,
) -> tuple[str, list[ClassSection]]:
    watched = {value.strip() for value in watched_course_numbers or [] if value.strip()}
    driver = _create_driver()
    full_url = build_class_list_url(subject, catalog_nbr, term)

    try:
        log(f"Loading URL: {full_url}")
        driver.get(full_url)
        time.sleep(2)

        sections = driver.find_elements(
            By.XPATH,
            "/html/body/div[2]/div[2]/div[2]/div/div/div[5]/div/div/div/div",
        )

        if not sections:
            raise MonitorError(
                "No class sections were found. Verify the subject, catalog number, and term."
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
