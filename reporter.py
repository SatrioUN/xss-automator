import os
import json
from typing import List, Dict, Any
from pathlib import Path
from utils import ensure_dir, now_ts

class Reporter:
    def __init__(self, out_dir="./reports", json_out=True, html_out=False, screenshot_dir="./reports/screenshots"):
        self.out_dir = out_dir
        self.json_out = json_out
        self.html_out = html_out
        self.screenshot_dir = screenshot_dir
        ensure_dir(self.out_dir)
        ensure_dir(self.screenshot_dir)

    def save(self, findings: List[Dict[str, Any]], meta_name="report"):
        """
        Save findings; return dict with paths.
        """
        ts = now_ts()
        base = Path(self.out_dir)
        base.mkdir(parents=True, exist_ok=True)
        paths = {}
        if self.json_out:
            jpath = base / f"{meta_name}_{ts}.json"
            with open(jpath, "w", encoding="utf-8") as fh:
                json.dump({"generated_at": ts, "findings": findings}, fh, indent=2, ensure_ascii=False)
            paths["json"] = str(jpath)
        if self.html_out:
            hpath = base / f"{meta_name}_{ts}.html"
            # Simple HTML summary
            try:
                with open(hpath, "w", encoding="utf-8") as fh:
                    fh.write("<html><body>\n")
                    fh.write(f"<h1>Report {ts}</h1>\n")
                    for f in findings:
                        fh.write("<pre>\n")
                        fh.write(json.dumps(f, indent=2, ensure_ascii=False))
                        fh.write("\n</pre>\n")
                    fh.write("</body></html>\n")
                paths["html"] = str(hpath)
            except Exception:
                pass
        return paths