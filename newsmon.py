import os
import re
import json
import hashlib
import requests
from bs4 import BeautifulSoup
from twilio.rest import Client
from datetime import datetime
import resend
from supabase import create_client

resend.api_key = os.environ["RESEND_API_KEY"]
URL = "https://www.globenewswire.com/en/search/industry/Biotechnology,Chemicals,Computer%2520Hardware,Computer%2520Services,Pharmaceuticals%2520&%2520Biotechnology,Software%2520&%2520Computer%2520Services/lang/en/exchange/Nasdaq,NYSE?pageSize=100"
STATE_FILE = "seen_globenewswire.json"
EMAIL_TO = [
    "svcommonbox@gmail.com",
    "santhosh.veeraraman@gmail.com",
    "raagashriram@gmail.com",
    "avashwin@gmail.com",
    "sriramvks@yahoo.com",
    "grakeshkumar1@gmail.com",
    "inbox.rasool@gmail.com",
    "sathish.nb@gmail.com",
    "emailsubbus@gmail.com",
    "chandrabose.ramaraj@gmail.com",
    "dhanasekaran.selvaraj@gmail.com",
    "sreeksiramdasu@gmail.com",
]

CATALYST_KEYWORDS = [
    "FDA", "clearance", "approval", "approved", "fast track",
    "breakthrough therapy", "orphan drug", "510(k)",
    "phase 1", "phase 2", "phase 3", "topline", "primary endpoint",
    "clinical trial", "trial results", "positive", "AI",
    "public offering", "registered direct", "warrants", "pre-funded",
    "private placement", "at-the-market",
    "financial results", "quarter results", "quarterly results",
    "guidance", "revenue", "earnings",
    "merger", "acquisition", "definitive agreement",
    "strategic transaction", "buyout",
    "contract", "awarded", "partnership", "collaboration",
    "supply agreement", "distribution agreement",
    "nasdaq", "listing rule", "compliance", "minimum bid",
    "reverse split", "inducement grant", "invest", "NVIDIA", "Promising", "Investor", "Disease"
]

def get_supabase_client():
    required = ["SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY"]
    missing = [key for key in required if not os.getenv(key)]

    if missing:
        raise RuntimeError(f"Missing Supabase environment variables: {missing}")

    return create_client(
        os.environ["SUPABASE_URL"],
        os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    )

def get_active_subscribers():
    supabase = get_supabase_client()

    response = (
        supabase
        .table("news_subscribers")
        .select("email")
        .eq("is_active", True)
        .execute()
    )

    return [row["email"] for row in response.data]

def highlight_keywords(text):
    highlighted = text

    for keyword in CATALYST_KEYWORDS:
        pattern = re.compile(re.escape(keyword), re.IGNORECASE)

        highlighted = pattern.sub(
            lambda m: f"<b>{m.group(0)}</b>",
            highlighted
        )

    return highlighted

def format_alerts_html(items):
    rows = []

    for item in items:
        ticker_str = ",".join(item["tickers"]) if item["tickers"] else "N/A"

        highlighted_title = highlight_keywords(item["title"])

        row = f"""
        <tr>
            <td style="
                padding:6px 10px;
                border:1px solid #d3d3d3;
                font-family:Arial,sans-serif;
                font-size:14px;
                line-height:1.4;">{ticker_str}</td>
            <td style="
                padding:6px 10px;
                border:1px solid #d3d3d3;
                font-family:Arial,sans-serif;
                font-size:14px;
                line-height:1.4;">{item['time']}</td>
            <td style="
                padding:6px 10px;
                border:1px solid #d3d3d3;
                font-family:Arial,sans-serif;
                font-size:14px;
                line-height:1.4;
            ">{highlighted_title}</td>
        </tr>
        """

        rows.append(row)

    return f"""
    <html>
    <body>
        <h3>EntrySignal Alerts</h3>
        <h3>From: GlobeNewswire</h3>
        <table style="
            border-collapse: collapse;
            border: 1px solid #c0c0c0;
            font-family: Arial, sans-serif;
            font-size: 14px;">
            <tr style="background:#f7f7f7;">
                <th>Ticker</th>
                <th>Time</th>
                <th>Title</th>
            </tr>

            {''.join(rows)}

        </table>
    </body>
    </html>
    """

def clean_text(text):
    return " ".join(text.split())


def load_seen():
    if not os.path.exists(STATE_FILE):
        return set()

    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return set(json.load(f))
    except Exception:
        return set()


def save_seen(seen):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(sorted(list(seen)), f, indent=2)


def make_id(title, url):
    raw = f"{title}|{url}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def extract_time(text):
    match = re.search(
        r"([A-Za-z]{3,9}\s+\d{1,2},\s+\d{4}\s+\d{2}:\d{2}\s+ET)",
        text
    )
    return match.group(1) if match else "N/A"


def extract_tickers(text):
    tickers = set()

    pattern = (
        r"\((?:NASDAQ|Nasdaq|NYSE|AMEX|NYSEAMERICAN|NYSE American|"
        r"OTC|OTCQB|OTCQX|TSX|TSXV):\s*([A-Z]{1,6})\)"
    )

    for ticker in re.findall(pattern, text):
        tickers.add(ticker.strip().upper())

    return sorted(list(tickers))


def is_relevant(text):
    lower_text = text.lower()
    return any(keyword.lower() in lower_text for keyword in CATALYST_KEYWORDS)


def send_email(subject, message, recipients):
    required = ["RESEND_API_KEY", "EMAIL_FROM"]
    missing = [key for key in required if not os.getenv(key)]

    if missing:
        print(f"Email skipped. Missing environment variables: {missing}")
        return

    if not recipients:
        print("Email skipped. No active subscribers.")
        return

    resend.api_key = os.environ["RESEND_API_KEY"]

    response = resend.Emails.send({
        "from": os.environ["EMAIL_FROM"],
        "to": recipients,
        "subject": subject,
        "html": message,
    })

    print(f"Email sent via Resend. Response: {response}")


def send_sms(message):
    required = ["TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_FROM", "SMS_TO"]
    missing = [key for key in required if not os.getenv(key)]

    if missing:
        print(f"SMS skipped. Missing environment variables: {missing}")
        return

    sms_body = message

    if len(sms_body) > 1400:
        sms_body = sms_body[:1350] + "\n\n...truncated. Check email for full list."

    client = Client(os.environ["TWILIO_ACCOUNT_SID"], os.environ["TWILIO_AUTH_TOKEN"])

    client.messages.create(
        body=sms_body,
        from_=os.environ["TWILIO_FROM"],
        to=os.environ["SMS_TO"]
    )

    print("SMS sent.")


def get_article_container(link):
    """
    Keep climbing only until we find the specific article block.
    Do NOT climb too high, otherwise we accidentally capture the whole page.
    """
    container = link

    for _ in range(5):
        if not container.parent:
            break

        container = container.parent
        text = clean_text(container.get_text(" ", strip=True))

        has_time = bool(extract_time(text))
        has_source = "Source:" in text
        has_title = clean_text(link.get_text(" ", strip=True)) in text

        if has_time and has_source and has_title:
            return container

    return link.parent if link.parent else link


def scrape():
    headers = {
        "User-Agent": "Mozilla/5.0 stock-news-monitor/1.0"
    }

    response = requests.get(URL, headers=headers, timeout=30)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    results = []
    seen_urls = set()

    for link in soup.find_all("a", href=True):
        href = link.get("href", "")
        title = clean_text(link.get_text(" ", strip=True))

        if not title:
            continue

        if "/news-release/" not in href:
            continue

        full_url = href if href.startswith("http") else "https://www.globenewswire.com" + href

        if full_url in seen_urls:
            continue

        seen_urls.add(full_url)

        container = get_article_container(link)
        article_text = clean_text(container.get_text(" ", strip=True))

        if not is_relevant(article_text):
            continue

        news_time = extract_time(article_text)
        tickers = extract_tickers(article_text)

        results.append({
            "id": make_id(title, full_url),
            "title": title,
            "time": news_time,
            "tickers": tickers,
            "url": full_url
        })

    return results


def format_alerts(items):
    lines = []

    for item in items:
        ticker_str = ",".join(item["tickers"]) if item["tickers"] else "N/A"

        # Fixed widths
        ticker_col = f"{ticker_str:<12}"   # 12 chars left-aligned
        time_col   = f"{item['time']:<22}" # 22 chars left-aligned

        line = f"{ticker_col} {time_col} {item['title']}"
        lines.append(line)

    return "\n".join(lines)


def main():
    print("Starting GlobeNewswire monitor...")
    print(f"URL: {URL}")

    seen = load_seen()
    items = scrape()

    print(f"\nFound {len(items)} matching item(s).")

    print("\n--- ALL MATCHES FOUND THIS RUN ---")
    if items:
        print(format_alerts(items))
    else:
        print("No matches found.")

    new_items = [item for item in items if item["id"] not in seen]

    print(f"\nFound {len(new_items)} new item(s).")

    if not new_items:
        print("No new alerts. Email/SMS not sent.")
        save_seen(seen)
        return

    consolidated_msg = format_alerts_html(new_items)

    print("\n--- NEW ALERTS ---")
    print(consolidated_msg)

    run_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    subject = (
        f"EntrySignals News Alerts | "
        f"{run_time} | "
        f"{len(new_items)} new item(s)"
    )
    
    recipients = get_active_subscribers()
    print(f"Sending email to {len(recipients)} subscriber(s).")
    send_email(subject, consolidated_msg, recipients)

    send_sms(consolidated_msg)

    for item in new_items:
        seen.add(item["id"])

    save_seen(seen)

    print("\nDone.")


if __name__ == "__main__":
    main()