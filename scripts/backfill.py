import argparse
import json
from pathlib import Path

import requests


def main() -> None:
    parser = argparse.ArgumentParser(description="Submit URL list to Hidden Spot job API")
    parser.add_argument("--api", default="http://localhost:8000", help="API base URL")
    parser.add_argument("--file", required=True, help="Text file with one URL per line")
    args = parser.parse_args()

    urls = [line.strip() for line in Path(args.file).read_text(encoding="utf-8").splitlines() if line.strip()]
    for url in urls:
        resp = requests.post(f"{args.api}/jobs", json={"url": url}, timeout=30)
        if resp.status_code >= 400:
            print(f"FAILED {url}: {resp.status_code} {resp.text}")
            continue
        print(json.dumps(resp.json(), ensure_ascii=False))


if __name__ == "__main__":
    main()
