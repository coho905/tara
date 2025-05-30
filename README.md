## 🧠 Features (Prioritized by Importance)

> These features are listed in order of implementation priority, based on innovation value, technical impact, and user experience.

---

### 🧱 Core Experience (Essential)

1. **Natural Language to Shell**
   - Converts natural language input into shell commands using GPT.

2. **Secure-by-Design Execution**
   - Blocks or warns on dangerous commands like `rm -rf`, `shutdown`, `mkfs`.
   - Supports confirmation and dry-run mode before running risky operations.

3. **Clarification Loop**
   - Detects ambiguity in user input and asks for clarification before proceeding.

4. **Memory + Context Awareness**
   - Remembers last commands and working directories.
   - Supports context-based follow-ups like “run it again” or “open the same folder.”

5. **Undo Last Command**
   - Reverses safe actions like `cd`, `mkdir`, `touch`.
   - Warns or blocks undo for destructive actions.

6. **Adaptive Personality Modes**
   - Supports `student`, `dev`, and `admin` modes with tailored GPT prompts and responses.

7. **Auto Mode Switching**
   - Detects context (e.g., root user, git repo) and automatically switches personality modes.

---

### 🎓 Learnability + Innovation (High-Impact)

8. **Embedded Help Mode (Student)**
   - Offers simplified explanations of executed commands using `man`, `tldr`, and GPT.
   - Automatically suggests command breakdowns in student mode.

9. **Command Plan Preview**
   - Before execution, shows a step-by-step explanation of what the command will do.

10. **Dry Run / Fake Execution Mode**
   - `--dry` flag prevents execution and shows what would happen instead.

11. **Intelligent Autocomplete**
   - GPT-powered command suggestions based on context and prior usage.

12. **Semantic Command Search**
   - Stores and embeds the last 200 commands for NL-based search and retrieval.

13. **Session Logging**
   - Saves inputs, commands, outputs, and explanations to `session_log.md`.

---

### 🧠 Stretch Feature (Optional but Powerful)

14. **Live Tutor Mode**
   - Offers an optional post-command Q&A that helps the user understand what just happened.
   - Great for education and making the assistant feel more like a teacher.

---

🧪 *These features combine usability, safety, intelligence, and transparency into a single assistant. Prioritization ensures focus while preserving extensibility.*