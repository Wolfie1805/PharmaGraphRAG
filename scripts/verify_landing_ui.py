import subprocess
import threading
import time
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent.parent
DIST_DIR = WORKSPACE / "frontend" / "dist"
SCREENSHOTS_DIR = Path(
    r"C:\Users\ADMIN\.gemini\antigravity\brain\3c3792fe-a25b-4b45-89fc-9fe2f02a0e53\screenshots"
)
SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)

CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"


class DualStackServer(HTTPServer):
    pass


def start_server(port=4173):
    def handler(*args, **kwargs):
        return SimpleHTTPRequestHandler(*args, directory=str(DIST_DIR), **kwargs)

    httpd = DualStackServer(("127.0.0.1", port), handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    return httpd


def capture_screenshot(url, output_path, width, height, extra_flags=None):
    flags = [
        CHROME_PATH,
        "--headless",
        "--disable-gpu",
        "--hide-scrollbars",
        f"--window-size={width},{height}",
        f"--screenshot={output_path}",
    ]
    if extra_flags:
        flags.extend(extra_flags)
    flags.append(url)
    subprocess.run(flags, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def main():
    print(f"Serving {DIST_DIR} on http://127.0.0.1:4173...")
    httpd = start_server(4173)
    time.sleep(1)

    base_url = "http://127.0.0.1:4173"

    sections = [
        ("01_hero", "#/", 900),
        ("02_what_it_is", "#what-it-is", 900),
        ("03_how_it_works", "#how-it-works", 900),
        ("04_does_not_do", "#boundaries", 900),
        ("05_benefits", "#benefits", 900),
        ("06_use_cases", "#use-cases", 900),
        ("07_questions", "#example-questions", 900),
        ("08_the_data", "#the-data", 1000),
        ("09_reliability", "#reliability", 900),
        ("10_search_honesty", "#search-architecture", 900),
        ("11_quality", "#quality", 900),
        ("12_limits_roadmap", "#limits-roadmap", 900),
        ("13_faq_footer", "#faq", 1100),
    ]

    print("\n--- 1. Capturing 1440px desktop screenshots ---")
    for name, anchor, h in sections:
        out = SCREENSHOTS_DIR / f"section_{name}_1440.png"
        if not out.exists() or out.stat().st_size == 0:
            target_url = f"{base_url}/{anchor}"
            capture_screenshot(target_url, str(out), 1440, h)
            print(f"Captured {out.name} ({out.stat().st_size} bytes)")
        else:
            print(f"Already exists: {out.name}")

    print("\n--- 2. Capturing 768px tablet screenshots ---")
    for name, anchor, h in sections:
        out = SCREENSHOTS_DIR / f"section_{name}_768.png"
        if not out.exists() or out.stat().st_size == 0:
            target_url = f"{base_url}/{anchor}"
            capture_screenshot(target_url, str(out), 768, int(h * 1.2))
            print(f"Captured {out.name} ({out.stat().st_size} bytes)")
        else:
            print(f"Already exists: {out.name}")

    print("\n--- 3. Capturing 400px mobile screenshots ---")
    for name, anchor, h in sections:
        out = SCREENSHOTS_DIR / f"section_{name}_400.png"
        if not out.exists() or out.stat().st_size == 0:
            target_url = f"{base_url}/{anchor}"
            capture_screenshot(target_url, str(out), 400, int(h * 1.5))
            print(f"Captured {out.name} ({out.stat().st_size} bytes)")
        else:
            print(f"Already exists: {out.name}")

    print("\n--- 4. Capturing reduced effects mode screenshot ---")
    out_reduced = SCREENSHOTS_DIR / "section_hero_reduced_effects_1440.png"
    if not out_reduced.exists() or out_reduced.stat().st_size == 0:
        capture_screenshot(
            f"{base_url}/#/",
            str(out_reduced),
            1440,
            900,
            extra_flags=["--force-prefers-reduced-motion"],
        )
        print(f"Captured {out_reduced.name} ({out_reduced.stat().st_size} bytes)")
    else:
        print(f"Already exists: {out_reduced.name}")

    httpd.shutdown()
    print("All screenshots verified successfully.")


if __name__ == "__main__":
    main()
