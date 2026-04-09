from __future__ import annotations

import random
import time

from tabulate import tabulate  # type: ignore

from asu_monitor import fetch_class_sections, notify_for_open_sections, parse_csv_list

message_counter = 0


def highlight_text(text: str) -> str:
    return f"\033[93m{text}\033[0m"


def main() -> None:
    global message_counter

    subject = input("Enter the subject code (e.g., PHY) [default: PHY]: ").strip() or "PHY"
    catalog_nbr = input("Enter the catalog number (e.g., 131) [default: 131]: ").strip() or "131"
    term = input("Enter the term number (e.g., 2257 for Fall 2025) [default: 2257]: ").strip() or "2257"
    watched_numbers = parse_csv_list(
        input(
            "Enter the class numbers to highlight (comma-separated NO spaces) [default: 61694]: "
        ).strip()
        or "61694"
    )
    phone_numbers = parse_csv_list(
        input(
            "Enter the + format phone numbers to notify (comma-separated NO spaces) "
            "[default: +12065658179,+12066837599]: "
        ).strip()
        or "+12065658179,+12066837599"
    )

    print("Starting continuous monitoring... Press Ctrl+C to stop.")
    print(f"Monitoring {subject} {catalog_nbr} for term {term}...")

    try:
        while True:
            _, sections = fetch_class_sections(subject, catalog_nbr, term, watched_numbers)
            rows = []
            for section in sections:
                row = [section.course_number, section.instructor, section.seat_text]
                if section.is_watched:
                    row = [highlight_text(value) for value in row]
                rows.append(row)

            headers = ["Course Number", "Instructor", "Seats"]
            print(tabulate(rows, headers=headers, tablefmt="pretty"))

            sent_count, messages = notify_for_open_sections(
                sections,
                subject,
                catalog_nbr,
                phone_numbers,
            )
            message_counter += sent_count
            for message in messages:
                print("*" * 80)
                print(message)
                print("*" * 80)

            print(f"Total messages sent so far: {message_counter}")
            wait_time = random.randint(45, 60)
            print(f"Waiting {wait_time} seconds before the next check...")
            time.sleep(wait_time)
    except KeyboardInterrupt:
        print("\nMonitoring stopped by user.")


if __name__ == "__main__":
    main()
