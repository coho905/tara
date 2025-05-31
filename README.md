# **TARA – Terminal Assistant for Responsive Action**
*Author: Colin · Semi-Autonomous Terminal Assistant*

---

## 1  Project Overview
| Aspect | Details |
|--------|---------|
|**Problem**| Command-line power ≠ usability. Novices get lost; pros waste keystrokes.|
|**Solution**| **TARA** adds a Textual TUI atop any shell: natural-language `nl:` prompts, GPT tutor, autocomplete, scrollable panels, full logs.|
|**Users**| Students, DevOps, researchers, accessibility advocates.|
|**Benefits**| 1. English → Bash 2. Never lose output (logs) 3. Safer dry-runs 4. In-app chat tutor.|

### Feature bullets
* `nl:` natural-language → command  
* Context-aware suggestions after each run  
* Full session logs (`vfo`)  
* Scrollable history & panels  
* Live **Chat** overlay  
* Dark-mode CSS via *Textual*

---

## 2  User Instructions
### 2.1  Setup
```bash
python -m venv tara && source tara/bin/activate
pip install -r requirements.txt
echo "OPENAI_API_KEY=sk-…" >> .env   # add your key