import re

import certifi
import httpx

r = httpx.get("https://www.clinpgx.org/downloads", verify=certifi.where(), follow_redirects=True)
scripts = re.findall(r'src="([^"]+\.js)"', r.text) + re.findall(r'href="([^"]+\.js)"', r.text)
print("Scripts found:", len(scripts))

for s in set(scripts):
    url = s if s.startswith("http") else "https://www.clinpgx.org" + s
    try:
        s_text = httpx.get(url, verify=certifi.where()).text
        for target in ["clinpgxHaplotypes", "haplotypes.zip", "cpic.alleles"]:
            if target.lower() in s_text.lower():
                print(f"Match for {target} in {url}")
                matches = [m.start() for m in re.finditer(re.escape(target), s_text, re.IGNORECASE)]
                for pos in matches[:3]:
                    print(s_text[max(0, pos - 150): min(len(s_text), pos + 250)])
                    print("-" * 50)
    except Exception as e:
        print(f"Error fetching {url}: {e}")

