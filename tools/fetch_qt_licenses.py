"""Vendor upstream license texts at the exact Qt/PySide release for packaging."""

import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
DESTINATION = ROOT / "licenses/qt-6.10.2"
REPOSITORIES = ("qt/qtbase", "qt/qtdeclarative", "pyside/pyside-setup")


def fetch(url):
    with urlopen(
        Request(url, headers={"User-Agent": "DesktopStats-license-builder"}), timeout=30
    ) as response:
        return response.read()


def main():
    jobs = []
    for repository in REPOSITORIES:
        items = json.loads(
            fetch(f"https://api.github.com/repos/{repository}/contents/LICENSES?ref=v6.10.2")
        )
        for item in items:
            if item["type"] == "file" and item["name"].endswith(".txt") and item["download_url"]:
                path = DESTINATION / repository.replace("/", "-") / item["name"]
                jobs.append((path, item["download_url"]))

    def write(job):
        path, url = job
        content = fetch(url)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)

    with ThreadPoolExecutor(max_workers=6) as executor:
        list(executor.map(write, jobs))
    (DESTINATION / "SOURCES.txt").write_text(
        "Upstream, unmodified license texts at v6.10.2:\n"
        + "\n".join(
            "https://github.com/" + repository + "/tree/v6.10.2/LICENSES"
            for repository in REPOSITORIES
        ),
        encoding="utf-8",
    )
    print("Vendored license texts:", len(jobs))


if __name__ == "__main__":
    main()
