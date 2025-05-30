import os
import subprocess
import openai
from dotenv import load_dotenv
import asyncio
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

import pyfiglet
from time import sleep
from datetime import datetime
# rich is used for Text and pyfiglet, not for Panel in Textual context directly for widgets
# from rich.console import Console # Already imported later
# from rich.layout import Layout # Not used
from rich.panel import Panel as RichPanel # Explicitly alias to avoid confusion
from rich.text import Text
# from pyfiglet import Figlet # Already imported
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical # Vertical not used directly but good for context
from textual.widgets import Static, Input, Header, Footer, Markdown
from textual.scroll_view import ScrollView
from textual.screen import Screen
from textual.binding import Binding
from typing import Union, List # Corrected List import
from rich.panel import Panel  # ✅ Use the Rich Panel
# For console printing outside Textual app (e.g., log_on)
from rich.console import Console
import platform
class ChatScreen(Screen):
    BINDINGS = [
        Binding("escape", "request_close", "Exit Chat", show=True),
    ]

    def __init__(self):
        super().__init__()
        self.chat_history = []

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        self.output_md = Markdown("**Welcome to Chat Mode!** Ask me anything.")
        # keep a reference to the Markdown widget so we can update it later
        self.output = ScrollView(self.output_md, id="chat_output")
        yield self.output
        yield Input(placeholder="Ask a question or type 'exit'", id="chat_input")
        yield Footer()

    async def action_request_close(self) -> None:
        """Close chat screen and refocus the main prompt."""
        await self.app.pop_screen()
        # Try to focus Student prompt first, then Dev prompt.
        try:
            self.app.query_one("#prompt_input", Input).focus()
        except Exception:
            try:
                self.app.query_one("#prompt_input_dev", Input).focus()
            except Exception:
                pass

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        user_msg = event.value.strip()
        self.query_one("#chat_input", Input).value = ""

        if user_msg.lower() == "exit":
            await self.app.pop_screen()
            try:
                self.app.query_one("#prompt_input", Input).focus()
            except Exception:
                try:
                    self.app.query_one("#prompt_input_dev", Input).focus()
                except Exception:
                    pass
            return

        self.chat_history.append({"role": "user", "content": user_msg})
        self.output_md.update("**STEPH:** Thinking…")

        import openai
        try:
            messages = [{"role": "system", "content": "You're a helpful terminal tutor."}] + self.chat_history[-8:]
            completion = await asyncio.to_thread(lambda: openai.ChatCompletion.create(
                model="gpt-4o-mini",
                messages=messages
            ))
            reply = completion.choices[0].message.content.strip()
            self.chat_history.append({"role": "assistant", "content": reply})
            conversation_md = "\n\n".join([
                f"**You:** {m['content']}" if m['role'] == "user" else f"**STEPH:** {m['content']}"
                for m in self.chat_history
            ])
            self.output_md.update(conversation_md)
            # Scroll to bottom
            self.output.scroll_end(animate=False)
        except Exception as e:
            self.output_md.update(f"**Error:** {e}")

def get_gpt_explanation(command_text: str) -> str:
    if not command_text.strip():
        return "No command was entered to explain."
    try:
        completion = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a helpful assistant that explains bash commands in one short sentence."},
                {"role": "user", "content": f"Explain this bash command in one sentence:\n{command_text}"}
            ]
        )
        return completion.choices[0].message.content.strip()
    except Exception as e:
        return f"Error getting explanation: {e}"

# Add at top level, outside any class:
def get_man_summary(command):
    try:
        # Fast one-liner first
        one_liner = subprocess.run(
            ["man", "-f", command], capture_output=True, text=True
        )
        if one_liner.returncode == 0 and " - " in one_liner.stdout:
            return one_liner.stdout.strip()

        # Fallback: parse NAME section
        full_page = subprocess.run(["man", command], capture_output=True, text=True)
        if full_page.returncode != 0:
            return f"(No man page entry found for {command})"

        lines = full_page.stdout.splitlines()
        grabbing = False
        name_lines = []
        for ln in lines:
            if ln.strip() == "NAME":
                grabbing = True
                continue
            if grabbing:
                if ln.strip() == "" or ln.strip().isupper():
                    break
                name_lines.append(ln.strip())
        summary = " ".join(name_lines).strip()
        return summary or f"(NAME section missing for {command})"
    except FileNotFoundError:
        return "(The 'man' command is not available.)"
    except Exception as e:
        return f"Error reading man page: {e}"


def run_command(command: str) -> str:
    if not command.strip():
        return "(No command to execute)"
    # Special handling for 'cd' command
    if command.startswith("cd "):
        try:
            path = command[3:].strip()
            os.chdir(path)
            return f"Changed directory to {os.getcwd()}"
        except Exception as e:
            return f"Error changing directory: {e}"
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True, check=False)
        output_parts = []
        if result.stdout:
            output_parts.append(f"Stdout:\n{result.stdout.strip()}")
        if result.stderr:
            output_parts.append(f"Stderr:\n{result.stderr.strip()}")

        if not output_parts:
            return "(Command produced no output)"
        return "\n\n".join(output_parts)
    except Exception as e:
        return f"Error executing command: {e}"

class HistoryScreen(Screen):
    BINDINGS = [
        Binding("q", "request_close", "Close History", show=True),
        Binding("escape", "request_close", "Close History", show=False),
    ]

    def __init__(
        self,
        history_data: List[dict], # Use List from typing
        name: Union[str, None] = None,
        id: Union[str, None] = None,
        classes: Union[str, None] = None,
        **kwargs
    ):
        super().__init__(name=name, id=id, classes=classes, **kwargs)
        self.history_data = history_data
        self.title = "Command History"

    def format_history_as_markdown(self) -> str:
        """Render *all* history entries, newest first, into a single markdown blob."""
        if not self.history_data:
            return "## Command History\n\n_No commands recorded yet._"

        blocks = []
        for entry in reversed(self.history_data):   # newest first
            ts = entry["timestamp"].strftime("%Y-%m-%d %H:%M:%S")
            cmd = entry.get("command", "")
            explanation = entry.get("explanation", "N/A")
            output = entry.get("output", "N/A")

            blocks.append(
                f"### {ts}\n"
                f"**Command:** `{cmd}`\n\n"
                f"**Explanation:**\n```text\n{explanation}\n```\n"
                f"**Output:**\n```text\n{output}\n```\n"
                "---"
            )

        return "# Command History\n\n" + "\n\n".join(blocks)

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        markdown_content = self.format_history_as_markdown()
        yield ScrollView(Markdown(markdown_content), id="history_scroll")
        yield Footer()


    async def action_request_close(self) -> None:
        await self.app.pop_screen()

class StudentTARA(App):
    CSS = """
Screen {
  layout: vertical;
  overflow: hidden;
}

/* header */
#header_panel {
  dock: top;
  padding: 0 1;
  margin-bottom: 1;
}

/* root: left‑hand stack + right‑hand suggestions */
#root {
  layout: horizontal;
  height: 1fr;
  min-height: 0;
}

/* left column (commands / explanation / output) takes 2⁄3 width */
#left {
  layout: vertical;
  width: 2fr;
  min-height: 0;
}

/* top row inside #left */
#main {
  layout: horizontal;
  height: 4fr;
  min-height: 0;
}

/* two panes inside #main */
#command,
#explanation {
  width: 1fr;
  min-width: 0;
  min-height: 0;
  overflow: auto;
  padding: 1;
  scrollbar-gutter: stable;
  border: solid #444;
}

/* output under #main, still scrollable */
#output {
  height: 5fr;
  min-height: 0;
  overflow: auto;
  padding: 1;
  scrollbar-gutter: stable;
  border: solid #444;
}

/* suggestion column on the right spans full height, 1⁄3 width */
#suggestion_scroll {
  width: 1fr;
  min-width: 0;
  min-height: 0;
  overflow: auto;
  padding: 1;
  scrollbar-gutter: stable;
  border: solid #444;
}

/* history screen scroll view */
#history_scroll {
  min-height: 0;
  overflow: auto;
  padding: 1;
  scrollbar-gutter: stable;
  border: solid #444;
}

#prompt_input {
  dock: bottom;
}
"""

    def __init__(self, user):
        super().__init__()
        self.user = user

    def on_mount(self) -> None:
        self.query_one("#prompt_input", Input).focus()

    def compose(self) -> ComposeResult:
        fig = pyfiglet.Figlet(font="small")
        header_art = fig.renderText("STEPH")
        tagline = "🧠 STEPH — Semi-autonomous Terminal for Responsive Action"
        yield Static(
            RichPanel(Text(header_art + "\n" + tagline, justify="center"), border_style="white"),
            id="header_panel"
        )

        # -----  BEGIN NEW LAYOUT  -----
        with Horizontal(id="root"):
            with Vertical(id="left"):
                # top row: command + explanation
                with Horizontal(id="main"):
                    # Command ScrollView
                    yield ScrollView(
                        Static(Panel("> Waiting for input...", title="Command", border_style="green"),
                               expand=True, id="command_content"),
                        id="command"
                    )
                    # Explanation ScrollView
                    yield ScrollView(
                        Static(Panel("GPT Summary of command will appear here...",
                                     title="Explanation", border_style="blue"),
                               expand=True, id="explanation_content"),
                        id="explanation"
                    )
                # Output ScrollView (below the top row)
                yield ScrollView(
                    Static(Panel("(no output yet)", title="Output / Dry Run",
                                 border_style="magenta"), expand=True, id="output_content"),
                    id="output"
                )

            # suggestions column (full‑height)
            suggestion_scroll = ScrollView(id="suggestion_scroll")
            yield suggestion_scroll
            self.call_after_refresh(lambda: suggestion_scroll.mount(
                Static(Panel("Suggestions will appear here...", title="Command Suggestions",
                             border_style="yellow"), id="suggestion_content", expand=True)
            ))
        # -----  END NEW LAYOUT  -----

        yield Input(placeholder="> Type command, 'nl: <task>', 'chat', 'vfo', 'help', or 'quit'", id="prompt_input")

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        cmd = event.value.strip()
        self.query_one("#prompt_input", Input).value = ""

        # New: handle quit and chat commands before anything else
        if cmd.lower() == "quit":
            self.exit()
            return
        elif cmd.lower() == "chat":
            await self.app.push_screen(ChatScreen())
            return
        # --- Room switching logic ---
        # Special handling for 'cd' command
        if cmd.startswith("cd "):
            try:
                path = cmd[3:].strip()
                os.chdir(path)
                self.query_one("#output_content", Static).update(
                    Panel(f"Changed directory to {os.getcwd()}", title="Output / Dry Run", border_style="magenta")
                )
                return
            except Exception as e:
                self.query_one("#output_content", Static).update(
                    Panel(f"Error changing directory: {e}", title="Output / Dry Run", border_style="red")
                )
                return
        elif cmd.lower().startswith("room:"):
            room_name = cmd[5:].strip()
            self.query_one("#output_content", Static).update(
                Panel(f"Switched to room: {room_name}", title="Output / Dry Run", border_style="cyan")
            )
            self.query_one("#prompt_input", Input).focus()
            return

        if cmd.lower() == "help":
            help_text = """
            ## 🆘 Help - Available Commands

            - `nl: [description]` — Translate natural language to terminal command
            - `vfo` or `Ctrl+H` — Show log‑file location (full session output).
            - `chat` — Open chat mode for tutoring
            - `quit` — Exit the program
            - `[any valid command]` — Run that command and show explanation/output
            """
            self.query_one("#output_content", Static).update(
                Panel(help_text.strip(), title="Help", border_style="cyan")
            )
            self.query_one("#prompt_input", Input).focus()
            return

        if cmd.lower() == "vfo":
            self.query_one("#output_content", Static).update(
                Panel(f"Full session log saved at:\n{self.user.log_file_path}",
                      title="Log Location", border_style="cyan")
            )
            self.query_one("#prompt_input", Input).focus()
            return

        self.query_one("#command_content", Static).update(
            Panel(f"> {cmd if cmd else 'No command entered'}", title="Command", border_style="green")
        )

        explanation_text = "N/A"
        output_text = "(no command to run)"
        # Ensure translated_command is always defined
        translated_command = ""
        raw_command = cmd

        # --- Explanation logic update for non-GPT commands ---

        if cmd:
            # If command starts with nl:, use OpenAI API to convert to bash command
            if cmd.startswith("nl:"):
                self.query_one("#explanation_content", Static).update(
                    Panel("Translating natural language to bash command...", title="Explanation", border_style="blue")
                )
                nl_query = cmd[3:].strip()
                bash_cmd = self.convert_nl_to_bash(nl_query)
                translated_command = bash_cmd
                self.query_one("#command_content", Static).update(
                    Panel(f"Natural language: {cmd}\n\nBash: {bash_cmd}", title="Command", border_style="green")
                )
                explanation_text = get_gpt_explanation(bash_cmd)
                self.query_one("#explanation_content", Static).update(
                    Panel(explanation_text, title="Explanation", border_style="blue")
                )
                output_text = run_command(bash_cmd)
                self.query_one("#output_content", Static).update(
                    Panel(output_text, title="Output / Dry Run", border_style="magenta")
                )
                history_entry = {
                    "timestamp": datetime.now(),
                    "command": raw_command,
                    "translated_command": bash_cmd,
                    "explanation": explanation_text,
                    "output": output_text
                }
                self.user.add_history_and_log(history_entry)
            else:
                translated_command = cmd
                self.query_one("#explanation_content", Static).update(
                    Panel(f"Fetching explanation for: '{cmd}'...", title="Explanation", border_style="blue")
                )
                # No explanation for raw commands
                explanation_text = ""  # No explanation for raw commands
                self.query_one("#explanation_content", Static).update(
                    Panel("(no explanation)", title="Explanation", border_style="blue")
                )
                output_text = run_command(cmd)
                self.query_one("#output_content", Static).update(
                    Panel(output_text, title="Output / Dry Run", border_style="magenta")
                )
                history_entry = {
                    "timestamp": datetime.now(),
                    "command": cmd,
                    "translated_command": translated_command,
                    "explanation": explanation_text,
                    "output": output_text
                }
                self.user.add_history_and_log(history_entry)
            # Check if translated_command indicates error
            if translated_command.startswith("Error") or translated_command.startswith("(empty"):
                self.query_one("#output_content", Static).update(
                    Panel(translated_command, title="Output / Dry Run", border_style="red")
                )
                return
        else:
            self.query_one("#explanation_content", Static).update(
                Panel("Please enter a command to get an explanation.", title="Explanation", border_style="blue")
            )
            self.query_one("#output_content", Static).update(
                Panel("(no command to run)", title="Output / Dry Run", border_style="magenta")
            )

        self.query_one("#prompt_input", Input).focus()

        # Suggestions logic after output panel update
        try:
            suggestion_prompt = f"Using the previous command '{translated_command}' and its output, suggest 3 useful next bash commands to try."
            suggestion_completion = await asyncio.to_thread(lambda: openai.ChatCompletion.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a shell assistant that recommends 3 helpful follow-up commands based on prior command usage and output."},
                    {"role": "user", "content": suggestion_prompt}
                ]
            ))
            suggestion_text = suggestion_completion.choices[0].message.content.strip()
            self.query_one("#suggestion_content", Static).update(
                Panel(suggestion_text, title="Command Suggestions", border_style="yellow")
            )
        except Exception as e:
            self.query_one("#suggestion_content", Static).update(
                Panel(f"Error fetching suggestions: {e}", title="Command Suggestions", border_style="red")
            )

    async def on_key(self, event) -> None:
        # Autocomplete logic for Tab key
        from textual import events
        import os
        if hasattr(event, "key") and event.key == "tab":
            input_widget = self.query_one("#prompt_input", Input)
            text = input_widget.value
            if not text.strip():
                return
            parts = text.rsplit(" ", 1)
            prefix = parts[-1]
            base = parts[0] if len(parts) > 1 else ""
            try:
                files = os.listdir('.')
                matches = [f for f in files if f.startswith(prefix)]
                if matches:
                    completed = matches[0]
                    new_value = f"{base} {completed}".strip()
                    input_widget.value = new_value
                    input_widget.cursor_position = len(new_value)
            except Exception:
                pass

    import platform
    @staticmethod
    def convert_nl_to_bash(nl_command: str) -> str:
        try:
            role = "I am going to tell you what I want to do, and you are going to convert it to instructions for a " + platform.system() + " terminal. Return ONLY the command as a plain text string, and nothing else."
            response = openai.ChatCompletion.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": role},
                    {"role": "user", "content": nl_command}
                ]
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            return f"Error converting to bash: {e}"

class DevTARA(App):
    CSS = """
    Screen {
      layout: vertical;
      overflow: hidden;
    }

    /* all DevTARA scroll views grow evenly to fill the grey area */
    #interpreted_scroll_view,
    #explanation_dev_scroll_view,
    #suggestion_dev_scroll_view,
    #output_dev_scroll_view,
    #history_scroll {
      height: 1fr;
      min-height: 0;
      overflow: auto;
      padding: 1;
      scrollbar-gutter: stable;
      border: solid #444;
    }

    #prompt_input_dev {
      dock: bottom;
    }
    """

    def __init__(self, user: "User"):
        super().__init__()
        self.user = user          # share the same User object as StudentTARA

    def on_mount(self) -> None:
        self.command_history: List[dict] = [] # Type hint
        self.query_one("#prompt_input_dev", Input).focus()
        # Kickstart asyncio event loop in Textual and start suggestion updater
        self.set_interval(0.1, lambda: None)
        import asyncio
        asyncio.create_task(self.update_suggestions_loop())

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True, name="Developer TARA")

        with Horizontal():
            # LEFT column (interpreted + explanation)
            with Vertical():
                # Interpreted command pane
                yield ScrollView(
                    Static(
                        RichPanel("Waiting for input...", title="Interpreted Command", border_style="green"),
                        id="interpreted_content_static",
                        expand=True,
                    ),
                    id="interpreted_scroll_view",
                )

                # Explanation / warnings pane
                yield ScrollView(
                    Static(
                        RichPanel("Explanation or warnings will appear here...", title="Warnings", border_style="red"),
                        id="explanation_dev_content_static",
                        expand=True,
                    ),
                    id="explanation_dev_scroll_view",
                )

            # RIGHT column (suggestions)
            yield ScrollView(
                Static(
                    RichPanel("Suggestions will appear here...", title="Command Suggestions", border_style="yellow"),
                    id="suggestion_dev_static",
                    expand=True,
                ),
                id="suggestion_dev_scroll_view",
            )

        # Output pane (full‑width below)
        yield ScrollView(
            Static(
                RichPanel("(no output yet)", title="Command Output", border_style="magenta"),
                id="output_dev_content_static",
                expand=True,
            ),
            id="output_dev_scroll_view",
        )

        # Prompt
        yield Input(
            placeholder="> Type your command, 'vfo', 'help', or 'quit'",
            id="prompt_input_dev",
        )

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        cmd = event.value.strip()
        self.query_one("#prompt_input_dev", Input).value = ""

        # New: handle quit before anything else
        if cmd.lower() == "quit":
            self.exit()
            return

        if cmd.lower() == "help":
            help_text = """
            ## 🆘 Help - Available Commands

            - `vfo` or `Ctrl+H` — Show log‑file location (full session output).
            - `quit` — Exit the program
            - `[any valid command]` — Run that command and show explanation/output
            """
            self.query_one("#output_dev_content_static", Static).update(
                RichPanel(help_text.strip(), title="Help", border_style="cyan")
            )
            self.query_one("#prompt_input_dev", Input).focus()
            return

        if cmd.lower() == "vfo":
            self.query_one("#output_dev_content_static", Static).update(
                RichPanel(f"Full session log saved at:\n{self.user.log_file_path}",
                          title="Log Location", border_style="cyan")
            )
            self.query_one("#prompt_input_dev", Input).focus()
            return

        self.query_one("#interpreted_content_static", Static).update(
            RichPanel(f"> {cmd if cmd else 'No command entered'}", title="Interpreted Command", border_style="green")
        )

        # ----- SUGGESTIONS LOGIC -----
        # (Suggestions are now updated asynchronously and continuously.)
        # ----- END SUGGESTIONS LOGIC -----

        explanation_text = "N/A"
        output_text = "(no command to run)" # Default

        if cmd:
            self.query_one("#explanation_dev_content_static", Static).update(
                RichPanel(f"Fetching explanation for: '{cmd}'...", title="Warnings", border_style="red")
            )
            # No explanation for raw commands
            explanation_text = ""  # No explanation for raw commands
            self.query_one("#explanation_dev_content_static", Static).update(
                RichPanel("(no explanation)", title="Warnings", border_style="red")
            )

            output_text = run_command(cmd)
            self.query_one("#output_dev_content_static", Static).update(
                RichPanel(output_text, title="Command Output", border_style="magenta")
            )

            history_entry = {
                "timestamp": datetime.now(),
                "command": cmd,
                "explanation": explanation_text,
                "output": output_text
            }
            self.command_history.append(history_entry)
            self.user.add_history_and_log(history_entry)
        else:
            self.query_one("#explanation_dev_content_static", Static).update(
                RichPanel("Please enter a command to get an explanation.", title="Warnings", border_style="red")
            )
            self.query_one("#output_dev_content_static", Static).update(
                RichPanel("(no command to run)", title="Command Output", border_style="magenta")
            )
        self.query_one("#prompt_input_dev", Input).focus()

    async def update_suggestions_loop(self):
        import asyncio
        import openai
        while True:
            await asyncio.sleep(3)  # Adjust refresh rate as needed
            try:
                input_widget = self.query_one("#prompt_input_dev", Input)
                cmd = input_widget.value.strip()
                # Use prompt logic for any previous command (not just nl:)
                if cmd:
                    suggestion_prompt = f"Using the previous command '{cmd}' and its output, suggest 3 useful next bash commands to try."
                    suggestion_completion = await asyncio.to_thread(lambda: openai.ChatCompletion.create(
                        model="gpt-4o-mini",
                        messages=[
                            {"role": "system", "content": "You are a shell assistant that recommends 3 helpful follow-up commands based on prior command usage and output."},
                            {"role": "user", "content": suggestion_prompt}
                        ]
                    ))
                    suggestion_text = suggestion_completion.choices[0].message.content.strip()
                    self.query_one("#suggestion_dev_static", Static).update(
                        RichPanel(suggestion_text, title="Command Suggestions", border_style="yellow")
                    )
            except Exception as e:
                self.query_one("#suggestion_dev_static", Static).update(
                    RichPanel(f"Error: {e}", title="Command Suggestions", border_style="red")
                )


# dotenv.load_dotenv() # Not used in this scope

class User:
    def __init__(self):
        self.mode = "dev"
        self.dry_mode = False
        self.chat_on = False
        self.command_history = []
        logs_dir = "logs"
        os.makedirs(logs_dir, exist_ok=True)
        self.save_location = os.path.join(logs_dir, f"session_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.log")

        self.log_file = open(self.save_location, "a")
        self.log_file.write(f"Session started at {datetime.now().strftime('%Y-%m-%d %H-%M-%S')}\n")
        self._log_state()

    def _log_state(self):
        self.log_file.write(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        self.log_file.write(f"  Mode: {self.mode}\n")
        self.log_file.write(f"  Dry mode: {self.dry_mode}\n")
        self.log_file.write(f"  Chat on: {self.chat_on}\n")
        self.log_file.flush()

    def set_mode(self, mode):
        if self.mode != mode:
            self.mode = mode
            self.log_file.write(f"Mode changed to: {self.mode}\n")
            self._log_state()

    def set_dry_mode(self, dry_mode):
        if self.dry_mode != dry_mode:
            self.dry_mode = dry_mode
            self.log_file.write(f"Dry mode changed to: {self.dry_mode}\n")
            self._log_state()

    def set_chat_on(self, chat_on):
        if self.chat_on != chat_on:
            self.chat_on = chat_on
            self.log_file.write(f"Chat on changed to: {self.chat_on}\n")
            self._log_state()

    def __del__(self):
        if hasattr(self, 'log_file') and self.log_file and not self.log_file.closed:
            self.log_file.write(f"Session ended at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            self.log_file.close()

    @property
    def log_file_path(self):
        """Return the full path of the current session log file."""
        return self.save_location

    def add_history_and_log(self, entry: dict):
        """Append entry to in‑memory history and dump full command + output to the log."""
        self.command_history.append(entry)
        try:
            self.log_file.write(
                f"\n[{entry['timestamp'].strftime('%Y-%m-%d %H:%M:%S')}]\n"
                f"CMD: {entry['command']}\n"
                "OUTPUT:\n"
                f"{entry.get('output', '').rstrip()}\n"
                "-----\n"
            )
            self.log_file.flush()
        except Exception as e:
            print(f"Could not write command to log: {e}", file=sys.stderr)

RED = '\033[91m'
GREEN = '\033[92m'
BLUE = '\033[94m'
# YELLOW = '\033[93m' # Not used
# MAGENTA = '\033[95m' # Not used
# CYAN = '\033[96m' # Not used
# WHITE = '\033[97m' # Not used
RESET = '\033[0m'

rich_console = Console() # Renamed to avoid conflict if textual.Console is ever used

def clear_screen():
    os.system("cls" if os.name == "nt" else "clear")

import sys
import termios
import tty

def get_single_keypress():
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    return ch

def log_on(user: User):
    clear_screen()

    print(f"{GREEN}Signed in{RESET}")
    sleep(1)
    clear_screen()
    user.log_file.write(f"User logged in at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    user.log_file.flush()

    while True:
        print("Enter mode: \n1. Student\n2. Developer\nChoice: ", end="", flush=True)
        mode_choice = get_single_keypress()
        print(mode_choice)  # Echo the key back
        if mode_choice == "1":
            user.set_mode("student")
            break
        elif mode_choice == "2":
            user.set_mode("dev")
            break
        else:
            print(f"{RED}Invalid mode selected. Please press 1 or 2.{RESET}")

    user.log_file.flush()
    clear_screen()

    fig_banner_font = "small" if user.mode == "student" else "slant"
    fig_banner = pyfiglet.Figlet(font=fig_banner_font)

    for i in range(0, 10, 3):
        clear_screen()
        banner_text = "STEPH" if user.mode == "student" else "TARA"
        ascii_banner = fig_banner.renderText(banner_text)
        print(ascii_banner)

        if user.mode == "student":
            rich_console.print(Text.assemble(
                ("🧠 STEPH — ", "white"),
                ("Semi-autonomous", "blue"), " ",
                ("Terminal", "magenta"), " for ",
                ("Responsive", "green"), " ",
                ("Action", "white")
            ), justify="center")
        else:
            rich_console.print(Text.assemble(
                ("Terminal", "blue"), " ",
                ("Assistant", "magenta"), " for ",
                ("Responsive", "green"), " ",
                ("Action", "white")
            ), justify="center")
        print("-" * (i * 6))
        sleep(0.7)
    clear_screen()


def main():
    current_user = User()
    log_on(current_user)

    if current_user.mode == "student":
        app = StudentTARA(user=current_user)
    else:
        app = DevTARA(user=current_user)

    app.run()
    rich_console.print("Thanks! Find output in the logs/ folder", style="bold green")

if __name__ == "__main__":
    main()