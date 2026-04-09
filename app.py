from __future__ import annotations

from flask import Flask, render_template, request

from asu_monitor import MonitorError, fetch_class_sections, notify_for_open_sections, parse_csv_list

app = Flask(__name__)

DEFAULTS = {
    "subject": "PHY",
    "catalog_nbr": "131",
    "term": "2257",
    "watched": "61694",
    "phones": "",
}


@app.route("/", methods=["GET"])
def index():
    values = {
        "subject": (request.args.get("subject") or DEFAULTS["subject"]).strip().upper(),
        "catalog_nbr": (request.args.get("catalog_nbr") or DEFAULTS["catalog_nbr"]).strip(),
        "term": (request.args.get("term") or DEFAULTS["term"]).strip(),
        "watched": (request.args.get("watched") or DEFAULTS["watched"]).strip(),
        "phones": (request.args.get("phones") or DEFAULTS["phones"]).strip(),
        "auto_refresh": request.args.get("auto_refresh") == "on",
        "send_texts": request.args.get("send_texts") == "on",
    }

    sections = []
    summary = None
    alert_messages: list[str] = []
    error = None
    source_url = None
    has_query = any(request.args.get(key) for key in ["subject", "catalog_nbr", "term", "watched", "phones"])

    if has_query:
        watched_numbers = parse_csv_list(values["watched"])
        phone_numbers = parse_csv_list(values["phones"])
        try:
            source_url, sections = fetch_class_sections(
                values["subject"],
                values["catalog_nbr"],
                values["term"],
                watched_numbers,
            )

            open_watched = [section for section in sections if section.is_watched and section.available_seats > 0]
            closed_watched = [section for section in sections if section.is_watched and section.available_seats <= 0]

            sent_count = 0
            if values["send_texts"] and phone_numbers:
                sent_count, alert_messages = notify_for_open_sections(
                    sections,
                    values["subject"],
                    values["catalog_nbr"],
                    phone_numbers,
                )

            summary = {
                "total_sections": len(sections),
                "watched_sections": sum(1 for section in sections if section.is_watched),
                "open_sections": sum(1 for section in sections if section.available_seats > 0),
                "open_watched": len(open_watched),
                "closed_watched": len(closed_watched),
                "sent_count": sent_count,
            }
        except MonitorError as exc:
            error = str(exc)

    return render_template(
        "index.html",
        values=values,
        sections=sections,
        summary=summary,
        error=error,
        source_url=source_url,
        alert_messages=alert_messages,
        has_query=has_query,
    )


if __name__ == "__main__":
    app.run(debug=True)
