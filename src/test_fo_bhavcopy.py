"""
One-off TEST script: download a single day of NSE F&O bhavcopy data and
inspect it. Not a general pipeline yet -- this is just to see the real
file shape before designing anything reusable.

Paper-trading research only. No broker, no order execution.
"""

import datetime as dt
import zipfile
from pathlib import Path

import pandas as pd
import requests

REPO_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = REPO_ROOT / "data" / "raw"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.nseindia.com/all-reports-derivatives",
}

MAX_DAYS_BACK = 7


def bhavcopy_url(date: dt.date) -> str:
    d = date.strftime("%Y%m%d")
    return f"https://nsearchives.nseindia.com/content/fo/BhavCopy_NSE_FO_0_0_0_{d}_F_0000.csv.zip"


def get_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(HEADERS)
    try:
        resp = session.get("https://www.nseindia.com/", timeout=15)
        print(f"[session] homepage request status: {resp.status_code}")
    except Exception as exc:
        print(f"[session] homepage request failed (continuing anyway): {exc}")
    return session


def try_download(session: requests.Session, date: dt.date):
    url = bhavcopy_url(date)
    try:
        resp = session.get(url, timeout=20)
    except Exception as exc:
        print(f"  {date}: request error -- {exc}")
        return None, url, None

    if resp.status_code == 200 and resp.headers.get("content-type", "").startswith("application/zip"):
        return resp.content, url, resp.status_code

    print(f"  {date}: HTTP {resp.status_code}, content-type={resp.headers.get('content-type')}")
    return None, url, resp.status_code


def find_and_download():
    session = get_session()
    today = dt.date.today()

    for i in range(1, MAX_DAYS_BACK + 1):
        candidate = today - dt.timedelta(days=i)
        content, url, status = try_download(session, candidate)
        if content is not None:
            print(f"Success: {candidate} -> {url}")
            return content, url, candidate

    return None, None, None


def main() -> None:
    content, url, date = find_and_download()

    if content is None:
        print()
        print("BLOCKED: could not download a bhavcopy file for any of the last "
              f"{MAX_DAYS_BACK} days. NSE did not return a usable zip file. "
              "Stopping here -- not substituting another data source.")
        return

    download_time = dt.datetime.now().isoformat(timespec="seconds")

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    zip_filename = url.rsplit("/", 1)[-1]
    zip_path = RAW_DIR / zip_filename
    zip_path.write_bytes(content)

    note_path = RAW_DIR / (zip_path.stem + "_SOURCE.txt")
    note_path.write_text(
        f"Source URL: {url}\n"
        f"Downloaded at: {download_time}\n"
        f"Bhavcopy trading date: {date.isoformat()}\n"
    )

    print(f"Raw zip saved to: {zip_path}")
    print(f"Source note saved to: {note_path}")
    print()

    with zipfile.ZipFile(zip_path) as zf:
        inner_names = zf.namelist()
        print(f"Files inside zip: {inner_names}")
        csv_name = inner_names[0]
        with zf.open(csv_name) as f:
            df = pd.read_csv(f)

    print()
    print(f"Column names ({len(df.columns)}):")
    print(list(df.columns))
    print()
    print(f"Total row count: {len(df)}")
    print()

    nifty_opts = df[(df["TckrSymb"] == "NIFTY") & (df["FinInstrmTp"] == "IDO")]
    print(f"NIFTY option rows: {len(nifty_opts)}")
    print()
    print("10 sample NIFTY option rows:")
    print(nifty_opts.head(10).to_string(index=False))


if __name__ == "__main__":
    main()
