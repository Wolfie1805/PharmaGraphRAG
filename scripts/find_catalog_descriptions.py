import re

import certifi
import httpx

resp = httpx.get("https://www.clinpgx.org/downloads", verify=certifi.where(), follow_redirects=True)
links = re.findall(r'/assets/[a-zA-Z0-9_\-\.]+\.js', resp.text)
print(f"Found {len(links)} JS assets")

for link in set(links):
    r = httpx.get("https://www.clinpgx.org" + link, verify=certifi.where())
    for target in ["clinpgxHaplotypes", "haplotypes.zip", "cpic.alleles"]:
        if target in r.text:
            print(f"Target '{target}' found in: {link}")
            pos = 0
            while True:
                idx = r.text.find(target, pos)
                if idx == -1:
                    break
                snippet = r.text[max(0, idx - 150): min(len(r.text), idx + 250)]
                print(f"Snippet at {idx}:\n{snippet}\n---")
                pos = idx + len(target)
