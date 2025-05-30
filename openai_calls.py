import events
import os
import subprocess
import openai
from dotenv import load_dotenv
import asyncio
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

import pyfiglet
from textual import events # Keep this for general event handling if needed elsewhere
from textual.events import Key as TextualKey
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
        self.output = ScrollView(Markdown("**Welcome to Chat Mode!** Ask me anything."), id="chat_output")
        yield self.output
        yield Input(placeholder="Ask a question or type 'exit'", id="chat_input")
        yield Footer()

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        user_msg = event.value.strip()
        self.query_one("#chat_input", Input).value = ""

        if user_msg.lower() == "exit":
            await self.app.pop_screen()
            return

        self.chat_history.append({"role": "user", "content": user_msg})
        # Display "Thinking..." immediately
        current_conversation_md = "\n\n".join([
            f"**You:** {m['content']}" if m['role'] == "user" else f"**STEPH:** {m['content']}"
            for m in self.chat_history
        ])
        thinking_md = current_conversation_md + "\n\n**STEPH:** Thinking..."
        self.query_one("#chat_output", ScrollView).update(Markdown(thinking_md))


        import openai
        try:
            client = openai.OpenAI()
            messages = [{"role": "system", "content": "You're a helpful terminal tutor."}] + self.chat_history[-8:] # Keep last 8 messages for context
            completion = await asyncio.to_thread(lambda: client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages
            ))
            reply = completion.choices[0].message.content.strip()
            self.chat_history.append({"role": "assistant", "content": reply})
            # Update conversation with actual reply
            final_conversation_md = "\n\n".join([
                f"**You:** {m['content']}" if m['role'] == "user" else f"**STEPH:** {m['content']}"
                for m in self.chat_history
            ])
            self.query_one("#chat_output", ScrollView).update(Markdown(final_conversation_md))
            # Scroll to bottom after update
            self.query_one("#chat_output", ScrollView).scroll_end(animate=False)

        except Exception as e:
            error_md = current_conversation_md + f"\n\n**Error:** {e}" # Show error in context
            self.query_one("#chat_output", ScrollView).update(Markdown(error_md))
            self.query_one("#chat_output", ScrollView).scroll_end(animate=False)


def get_gpt_explanation(command_text: str) -> str:
    if not command_text.strip():
        return "No command was entered to explain."
    try:
        # Ensure you are using the OpenAI v1.x.x client initialization if this is a newer script
        client = openai.OpenAI()
        completion = client.chat.completions.create( # Corrected call
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
        # Sanitize command to prevent shell injection if it's part of a complex command string.
        # For `man`, we usually just need the command name.
        command_name = command.split()[0] if command else ""
        if not command_name:
            return "(No command specified for man page)"

        result = subprocess.run(["man", command_name], capture_output=True, text=True, check=False)
        if result.returncode == 0 and result.stdout:
            # A more robust way to find the NAME section and its description
            lines = result.stdout.split("\n")
            name_section_started = False
            description_lines = []
            # Try to find "NAME" heading, then capture lines until next common heading or blank line.
            # Man pages can be structured differently, this is a common heuristic.
            for i, line in enumerate(lines):
                if "NAME" in line and i < len(lines) -1: # Check if "NAME" is in the line
                    # The actual name and short description is often on the next line or lines immediately following
                    # We'll grab a few lines after "NAME" as a heuristic.
                    # And then look for common section enders like a fully uppercase word (another section) or significant white space.
                    # This part is tricky as man page formats vary.
                    # For simplicity, let's try to get the content directly under NAME.
                    start_line = i + 1
                    # Find where the description under NAME ends. Often before DESCRIPTION or SYNOPSIS.
                    # We will look for an empty line or an all-caps line (new section)
                    for j in range(start_line, len(lines)):
                        if lines[j].strip() == "": # Empty line often separates sections or parts
                            break
                        if lines[j].strip().isupper() and len(lines[j].strip().split()) <= 2 and j > start_line : # Likely a new section title e.g., SYNOPSIS, DESCRIPTION
                            break
                        # Heuristic: If line starts with command name again (sometimes happens in NAME section)
                        if lines[j].strip().startswith(command_name + " "):
                             description_lines.append(lines[j].strip())
                        elif name_section_started or lines[j].strip().startswith("       "): # Typical indentation for description
                            description_lines.append(lines[j].strip())
                        if " - " in lines[j]: # Often the format is "command - short description"
                            name_section_started = True # Start capturing after the " - "
                            description_lines.append(lines[j].strip())


                    # Limit to a reasonable summary length
                    summary = "\n".join(description_lines).strip()
                    if not summary and start_line < len(lines): # Fallback if above logic fails, just take line after NAME
                        summary = lines[start_line].strip()

                    # Further clean-up: often the NAME line itself is "command - description"
                    name_line_content = ""
                    if " - " in lines[i]:
                        name_line_content = lines[i].split(" - ", 1)[1].strip()

                    if name_line_content and (not summary or name_line_content not in summary):
                        summary = name_line_content + ("\n" + summary if summary else "")

                    return summary if summary else "(Could not parse NAME section from man page)"

            return "(NAME section not found or could not be parsed)"
        elif result.stderr:
             # Provide more specific feedback if man page doesn't exist
            if "No manual entry for" in result.stderr:
                return f"(No man page entry found for {command_name})"
            return f"(Error accessing man page for {command_name}: {result.stderr.strip()})"
        else:
            return f"(No man page entry found for {command_name} or error occurred)"
    except FileNotFoundError:
        return "(The 'man' command was not found on your system.)"
    except Exception as e:
        return f"Error reading man page: {e}"


def run_command(command: str) -> str:
    if not command.strip():
        return "(No command to execute)"
    # Special handling for 'cd' command
    if command.startswith("cd "):
        try:
            path = command[3:].strip()
            if not path: # Handle "cd " or "cd ~"
                path = os.path.expanduser("~")
            os.chdir(path)
            return f"Changed directory to {os.getcwd()}"
        except FileNotFoundError:
            return f"Error changing directory: No such file or directory: {path}"
        except Exception as e:
            return f"Error changing directory: {e}"
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True, check=False, timeout=15) # Added timeout
        output_parts = []
        if result.stdout:
            output_parts.append(f"Stdout:\n{result.stdout.strip()}")
        if result.stderr:
            output_parts.append(f"Stderr:\n{result.stderr.strip()}")

        if not output_parts:
            return "(Command produced no output)"
        # Make output potentially long - reduced multiplier for typical display
        return ("\n\n".join(output_parts) + "\nEnd of output.") # Removed * 3, can be too much
    except subprocess.TimeoutExpired:
        return f"Error executing command: Timeout after 15 seconds."
    except Exception as e:
        return f"Error executing command: {e}"

class HistoryScreen(Screen):
    BINDINGS = [
        Binding("q", "request_close", "Close History", show=True),
        Binding("escape", "request_close", "Close History", show=False),
        Binding("left, <", "previous_entry", "Previous", show=True), # Changed to left arrow
        Binding("right, >", "next_entry", "Next", show=True),      # Changed to right arrow
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
        self.history_index = 0 # Shows the latest command by default (index 0 from the end)

    def format_history_as_markdown(self) -> str:
        if not self.history_data:
            return "## Command History\n\nNo commands in history yet."
        # Display latest first, so index 0 is self.history_data[-1]
        # self.history_index means how many steps back from the most recent entry
        actual_idx = len(self.history_data) - 1 - self.history_index
        if not (0 <= actual_idx < len(self.history_data)): # Should not happen with guard
             return "Error: History index out of bounds."

        entry = self.history_data[actual_idx]
        ts = entry['timestamp'].strftime('%Y-%m-%d %H:%M:%S')
        command = entry['command']
        # Handle potentially missing keys gracefully
        translated = entry.get('translated_command', command) # Show original if no translation
        explanation = entry.get('explanation', 'N/A')
        output = entry.get('output', 'N/A')

        # Make sure command shown is the one that was actually run if nl: was used
        display_command = f"{translated}"
        if raw_command := entry.get('command', None):
            if raw_command.startswith("nl:") and translated != raw_command:
                display_command = f"{raw_command}\n**Interpreted as:** `{translated}`"
            else: # it's a direct command or translation failed to be different
                 display_command = f"`{raw_command}`"


        return (
            f"# Command History ({self.history_index + 1}/{len(self.history_data)})\n\n---\n"
            f"**Timestamp:** {ts}\n"
            f"**Command:** {display_command}\n"
            f"**Explanation:**\n```text\n{explanation}\n```\n"
            f"**Output:**\n```text\n{output}\n```\n"
            f"\n(Use `left`/`right` arrows to navigate. `q` to close.)"
        )

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True, name=self.title)
        markdown_content = self.format_history_as_markdown()
        yield ScrollView(Markdown(markdown_content), id="history_scroll")
        yield Footer()

    def on_mount(self) -> None:
        # Ensure the latest entry is shown (index 0 is most recent)
        self.history_index = 0
        self.update_scroll()


    def update_scroll(self):
        markdown_content = self.format_history_as_markdown()
        md_widget = self.query_one(Markdown) # More direct query if only one Markdown
        md_widget.update(markdown_content)
        # self.query_one("#history_scroll", ScrollView).scroll_home(animate=False) # Scroll to top of entry

    async def action_previous_entry(self): # Go to older entries
        if self.history_index < len(self.history_data) - 1:
            self.history_index += 1
            self.update_scroll()

    async def action_next_entry(self): # Go to newer entries
        if self.history_index > 0:
            self.history_index -= 1
            self.update_scroll()

    async def action_request_close(self) -> None:
        await self.app.pop_screen()

class StudentTARA(App):
    CSS = """
    Screen {
        layout: vertical;
        overflow: auto auto; /* Screen can scroll if its direct children overflow */
    }
    #header_panel {
        height: auto;
        dock: top;
        padding: 0 1;
        margin-bottom: 1;
    }
    #main {
        layout: horizontal;
        height: 4fr; /* Main area for command, explanation, suggestions */
    }

    /* These are the Vertical containers FOR the ScrollViews */
    #command, #explanation, #suggestion_scroll {
        width: 1fr;
        height: 100%; /* Children of #main will take its full height */
        /* REMOVED overflow: hidden; from here */
        padding: 1;
        border: solid #444;
        /* The Vertical container itself does not need to handle overflow, its child ScrollView will. */
    }

    #output { /* This is the Vertical container FOR the output ScrollView */
        height: 5fr; /* Area for command output */
        padding: 1;
        /* REMOVED overflow: hidden; from here */
        border: solid #444;
    }

    /* Target the ScrollView widgets INSIDE the above containers */
    #command > ScrollView,
    #explanation > ScrollView,
    #suggestion_scroll > ScrollView,
    #output > ScrollView {
        width: 100%;
        height: 100%; /* Make ScrollView fill its parent Vertical container */
    }

    #prompt_input {
        height: auto; /* Input field takes one line */
        dock: bottom;
    }
    #chat_output { /* Style for chat screen's scrollview */
        height: 1fr; /* Take available space, this should be fine */
    }
    #history_scroll { /* Style for history screen's scrollview */
        height: 1fr; /* Take available space, this should be fine */
    }
    Static { /* General style for Static widgets, often inside ScrollViews */
        width: 100%; /* Make Static fill ScrollView horizontally */
        height: auto;  /* Allow Static to grow vertically with its content */
    }
    """

    BINDINGS = [
        Binding("ctrl+c", "quit", "Quit", show=True, priority=True),
        Binding("ctrl+h", "view_history_binding", "History", show=True),
        Binding("ctrl+t", "chat_mode_binding", "Chat", show=True),
    ]

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

        with Horizontal(id="main"):
            # Each of these is a container for a ScrollView
            with Vertical(id="command"): # Container for the "Command" panel
                yield ScrollView(
                    Static(RichPanel("> Waiting for input...", title="Command", border_style="green"), id="command_content")
                )
            with Vertical(id="explanation"): # Container for the "Explanation" panel
                yield ScrollView(
                    Static(RichPanel("GPT Summary of command will appear here...", title="Explanation", border_style="blue"), id="explanation_content")
                )
            with Vertical(id="suggestion_scroll"): # Container for "Suggestions"
                yield ScrollView(
                    Static(RichPanel("Suggestions will appear here...", title="Command Suggestions", border_style="yellow"), id="suggestion_content")
                )
        
        # Output panel container
        with Vertical(id="output"):
            yield ScrollView(
                Static(RichPanel("(no output yet)", title="Output / Dry Run", border_style="magenta"), id="output_content")
            )
        yield Input(placeholder="> Type command, 'nl: <task>', 'chat', 'history', 'help', or 'quit'", id="prompt_input")
        yield Footer() # Displays bindings

    async def action_view_history_binding(self):
        """Called when ctrl+h is pressed."""
        await self.handle_view_history()

    async def action_chat_mode_binding(self):
        """Called when ctrl+t is pressed."""
        await self.app.push_screen(ChatScreen())


    async def handle_view_history(self):
        if not self.user.command_history:
            self.query_one("#output_content", Static).update(
                RichPanel("History is empty.", title="Output / Dry Run", border_style="magenta")
            )
        else:
            await self.app.push_screen(HistoryScreen(history_data=self.user.command_history))
        self.query_one("#prompt_input", Input).focus()


    async def on_input_submitted(self, event: Input.Submitted) -> None:
        cmd = event.value.strip()
        input_widget = self.query_one("#prompt_input", Input)
        input_widget.value = "" # Clear input

        # Update command panel immediately
        self.query_one("#command_content", Static).update(
            RichPanel(f"> {cmd if cmd else 'No command entered'}", title="Command", border_style="green")
        )
        # Clear other panels
        self.query_one("#explanation_content", Static).update(
            RichPanel("...", title="Explanation", border_style="blue")
        )
        self.query_one("#output_content", Static).update(
            RichPanel("...", title="Output / Dry Run", border_style="magenta")
        )
        self.query_one("#suggestion_content", Static).update(
            RichPanel("Fetching suggestions...", title="Command Suggestions", border_style="yellow")
        )


        if cmd.lower() == "quit":
            self.exit()
            return
        elif cmd.lower() == "chat":
            await self.app.push_screen(ChatScreen())
            return
        elif cmd.lower().startswith("room:"): # Not fully implemented, placeholder
            room_name = cmd[5:].strip()
            self.query_one("#output_content", Static).update(
                RichPanel(f"Switched to room: {room_name}", title="Output / Dry Run", border_style="cyan")
            )
            input_widget.focus()
            return
        elif cmd.lower() == "help":
            help_text = Text(
                """
## 🆘 Help - Available Commands / Features

- `nl: [description]` — Translate natural language to a terminal command.
  Example: `nl: list all files in current directory including hidden ones`
- `view history` or `Ctrl+H` — Show command history.
- `chat` or `Ctrl+T` — Open interactive chat mode for tutoring.
- `quit` or `Ctrl+C` — Exit the application.
- `[any shell command]` — Execute the command directly (e.g., `ls -l`, `echo "Hello"`).
  - `cd [directory]` is handled to change the application's working directory.

**Navigation:**
- Use `Tab` and `Shift+Tab` to move between focusable areas.
- Arrow keys often work for scrolling or navigation within widgets.
- `Esc` can be used to close pop-up screens like Chat or History.

**Interface:**
- **Command:** Shows the command being processed.
- **Explanation:** Provides a summary/explanation of the command (man page or GPT).
- **Command Suggestions:** Offers related commands based on your input.
- **Output / Dry Run:** Displays the standard output and error from the command.
                """, justify="left"
            )
            self.query_one("#output_content", Static).update(
                RichPanel(help_text, title="Help", border_style="cyan")
            )
            input_widget.focus()
            return
        elif cmd.lower() == "view history":
            await self.handle_view_history()
            input_widget.focus()
            return

        explanation_text = "N/A"
        output_text = "(no command to run)"
        translated_command = cmd # Default to raw command
        raw_command_for_history = cmd # The exact command typed by user

        if cmd:
            if cmd.startswith("cd "): # Handle 'cd' separately for immediate effect
                output_text = run_command(cmd) # run_command handles os.chdir
                explanation_text = get_man_summary("cd") # Standard explanation for cd
                self.query_one("#output_content", Static).update(
                    RichPanel(output_text, title="Output / Dry Run", border_style="magenta" if "Error" not in output_text else "red")
                )
                self.query_one("#explanation_content", Static).update(
                    RichPanel(explanation_text, title="Explanation", border_style="blue")
                )
            elif cmd.startswith("nl:"):
                self.query_one("#explanation_content", Static).update(
                    RichPanel("Translating natural language to bash command...", title="Explanation", border_style="blue")
                )
                nl_query = cmd[3:].strip()
                if not nl_query:
                    bash_cmd = "(Natural language query was empty)"
                    explanation_text = "Please provide a description after 'nl:'."
                    output_text = ""
                else:
                    bash_cmd = await asyncio.to_thread(self.convert_nl_to_bash, nl_query)
                    translated_command = bash_cmd # Store the translated command
                    # Update command panel to show NL and Bash
                    self.query_one("#command_content", Static).update(
                        RichPanel(f"Natural language: {nl_query}\n\nBash: {bash_cmd}", title="Command", border_style="green")
                    )
                    if bash_cmd.startswith("Error") or bash_cmd.startswith("(empty"):
                        explanation_text = "Could not translate to a valid command."
                        output_text = bash_cmd # Show the error from conversion
                    else:
                        explanation_text = await asyncio.to_thread(get_gpt_explanation, bash_cmd)
                        self.query_one("#output_content", Static).update(
                            RichPanel(f"Executing: {bash_cmd}\n---", title="Output / Dry Run", border_style="magenta")
                        )
                        output_text = await asyncio.to_thread(run_command, bash_cmd)
                
                self.query_one("#explanation_content", Static).update(
                    RichPanel(explanation_text, title="Explanation", border_style="blue")
                )
                self.query_one("#output_content", Static).update(
                    RichPanel(output_text, title="Output / Dry Run", border_style="magenta" if "Error" not in output_text and "Stderr" not in output_text else "red")
                )
            else: # Direct command
                translated_command = cmd
                self.query_one("#explanation_content", Static).update(
                    RichPanel(f"Fetching explanation for: '{cmd}'...", title="Explanation", border_style="blue")
                )
                command_name_for_man = cmd.split()[0] if cmd else ""
                explanation_text = await asyncio.to_thread(get_man_summary, command_name_for_man) # Use man page for direct commands
                
                self.query_one("#explanation_content", Static).update(
                    RichPanel(explanation_text, title="Explanation", border_style="blue")
                )
                self.query_one("#output_content", Static).update(
                    RichPanel(f"Executing: {cmd}\n---", title="Output / Dry Run", border_style="magenta")
                )
                output_text = await asyncio.to_thread(run_command, cmd)
                self.query_one("#output_content", Static).update(
                    RichPanel(output_text, title="Output / Dry Run", border_style="magenta" if "Error" not in output_text and "Stderr" not in output_text else "red")
                )

            # Add to history
            history_entry = {
                "timestamp": datetime.now(),
                "command": raw_command_for_history, # The original command typed
                "translated_command": translated_command if translated_command != raw_command_for_history else cmd, # Store translated if different
                "explanation": explanation_text,
                "output": output_text
            }
            self.user.command_history.append(history_entry)

            # Fetch suggestions based on the command that was actually (or intended to be) executed
            final_command_for_suggestions = translated_command
            if final_command_for_suggestions.startswith("Error") or final_command_for_suggestions.startswith("(empty") or final_command_for_suggestions.startswith("(Natural language query was empty)"):
                 self.query_one("#suggestion_content", Static).update(
                    RichPanel("Cannot fetch suggestions for invalid command.", title="Command Suggestions", border_style="yellow")
                )
            else:
                try:
                    client = openai.OpenAI() # Ensure client is initialized for async thread
                    suggestion_prompt = f"The user ran the command: '{final_command_for_suggestions}'. Suggest 3 useful and distinct follow-up bash commands. Provide only the commands, each on a new line, without explanations or numbering."
                    suggestion_completion = await asyncio.to_thread(
                        lambda: client.chat.completions.create(
                            model="gpt-4o-mini",
                            messages=[
                                {"role": "system", "content": "You are a shell assistant. Provide only bash commands as requested."},
                                {"role": "user", "content": suggestion_prompt}
                            ]
                        )
                    )
                    suggestion_text = suggestion_completion.choices[0].message.content.strip()
                    self.query_one("#suggestion_content", Static).update(
                        RichPanel(suggestion_text, title="Command Suggestions", border_style="yellow")
                    )
                except Exception as e:
                    self.query_one("#suggestion_content", Static).update(
                        RichPanel(f"Error fetching suggestions: {e}", title="Command Suggestions", border_style="red")
                    )
        else: # No command entered
            self.query_one("#command_content", Static).update(
                 RichPanel("> No command entered", title="Command", border_style="green")
            )
            self.query_one("#explanation_content", Static).update(
                RichPanel("Please enter a command to get an explanation.", title="Explanation", border_style="blue")
            )
            self.query_one("#output_content", Static).update(
                RichPanel("(no command to run)", title="Output / Dry Run", border_style="magenta")
            )
            self.query_one("#suggestion_content", Static).update(
                RichPanel("Enter a command to get suggestions.", title="Command Suggestions", border_style="yellow")
            )

        input_widget.focus()


    async def on_key(self, event: TextualKey) -> None: # Corrected import for events
        from textual import events # Ensure events is available
        import os # For listdir
        if event.key == "tab":
            event.prevent_default() # Prevent default tab behavior
            input_widget = self.query_one("#prompt_input", Input)
            current_value = input_widget.value
            cursor_pos = input_widget.cursor_position

            # Determine the part of the command to autocomplete (usually the last word)
            # If there's a space before cursor, autocomplete from there, else from start
            text_to_complete = current_value[:cursor_pos]
            last_space = text_to_complete.rfind(" ")
            
            if last_space != -1:
                prefix = text_to_complete[last_space+1:]
                base_path_str = text_to_complete[:last_space+1]
            else:
                prefix = text_to_complete
                base_path_str = ""

            # Basic file/directory path completion
            # More sophisticated completion would require context (e.g., after 'cd', after a command name for its options)
            try:
                # Simplistic: complete based on items in current directory
                # For commands, one might check PATH executables. For paths, listdir.
                # This example focuses on file/dir names for simplicity.
                
                # Determine search directory: if prefix contains path separators, use that
                if os.path.sep in prefix:
                    search_dir = os.path.dirname(prefix)
                    item_prefix = os.path.basename(prefix)
                    if not search_dir: search_dir = "." # if prefix is like "/file"
                else:
                    search_dir = "."
                    item_prefix = prefix

                if not os.path.isdir(search_dir): # Check if directory is valid
                     return


                matches = []
                for item in os.listdir(search_dir):
                    if item.startswith(item_prefix):
                        # If the original prefix included a path, prepend it to the item for the match
                        full_item_path = os.path.join(os.path.dirname(prefix), item) if os.path.sep in prefix else item
                        if os.path.isdir(os.path.join(search_dir,item)):
                            matches.append(full_item_path + os.path.sep) # Add trailing slash for directories
                        else:
                            matches.append(full_item_path)
                
                if matches:
                    # Basic cycle through matches or pick first
                    # For simplicity, pick the first match. A real app might show a dropdown.
                    completed_item = matches[0]
                    
                    new_value = base_path_str + completed_item + " " # Add space after completion
                    remaining_text = current_value[cursor_pos:]
                    
                    input_widget.value = new_value + remaining_text
                    input_widget.cursor_position = len(new_value)

            except Exception:
                # Autocomplete can fail for many reasons (permissions, etc.), so fail silently
                pass


    @staticmethod
    def convert_nl_to_bash(nl_command: str) -> str:
        try:
            client = openai.OpenAI() # Ensure client is initialized for async thread
            # Determine current OS for more accurate commands
            current_os = platform.system()
            if current_os == "Darwin": os_name = "macOS"
            elif current_os == "Windows": os_name = "Windows"
            elif current_os == "Linux": os_name = "Linux"
            else: os_name = current_os

            role = f"You are a natural language to {os_name} terminal command converter. Return ONLY the most appropriate command as a plain text string, and nothing else. No explanations, no backticks, just the command. If the request is ambiguous or cannot be reasonably converted to a single command, return 'Error: Ambiguous or unsupported request.'"
            
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": role},
                    {"role": "user", "content": nl_command}
                ],
                temperature=0.0 # For more deterministic output
            )
            content = response.choices[0].message.content.strip()
            # Further clean-up: remove backticks if OpenAI still adds them sometimes
            if content.startswith("`") and content.endswith("`"):
                content = content.strip("`")
            # Check for common non-commands
            if not content or "Error:" in content or "sorry" in content.lower() or "cannot" in content.lower() or "unable" in content.lower():
                return f"(Could not convert: {content if content else 'No command generated'})"

            return content
        except Exception as e:
            return f"Error converting to bash: {e}"


class DevTARA(App):
    CSS = """
    Screen {
        layout: vertical;
        overflow: auto auto; /* horizontal vertical */
    }
    /* Main Horizontal container for the three columns */
    #dev_main_horizontal {
        layout: horizontal;
        height: 20fr; /* Allocate significant space for these three columns */
    }
    /* Vertical container for Interpreted and Explanation */
    #dev_left_vertical {
        layout: vertical;
        width: 2fr; /* Takes 2/3 of the #dev_main_horizontal space with #dev_suggestions */
        height: 100%;
    }
    #interpreted_scroll_view, #explanation_dev_scroll_view {
        width: 100%;
        height: 1fr; /* Share space equally within #dev_left_vertical */
        margin-bottom: 1;
        overflow: hidden; /* ScrollView handles its own scrolling */
        border: solid #444;
        padding: 1;
    }
    #suggestion_dev_scroll_view {
        width: 1fr; /* Takes 1/3 of the #dev_main_horizontal space */
        height: 100%; 
        overflow: hidden;
        border: solid #444;
        padding: 1;
    }
    #output_dev_scroll_view {
        height: 6fr; /* Output area below the main three columns */
        overflow: hidden;
        border: solid #444;
        padding: 1;
        margin-top: 1;
    }
    #prompt_input_dev {
        height: auto; /* Single line for input */
        dock: bottom;
    }
    Static { /* Ensure static widgets within scrollviews expand */
        width: 100%;
        height: auto; /* Content determines height */
    }
    #history_scroll {
        height: 1fr;
    }
    """
    BINDINGS = [
        Binding("ctrl+c", "quit", "Quit", show=True, priority=True),
        Binding("ctrl+h", "view_history_binding", "History", show=True),
    ]


    def on_mount(self) -> None:
        self.command_history: List[dict] = [] # Type hint
        self.query_one("#prompt_input_dev", Input).focus()
        self.suggestion_task = asyncio.create_task(self.update_suggestions_loop())


    def on_unmount(self):
        # Clean up background task when app exits
        if self.suggestion_task:
            self.suggestion_task.cancel()

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True, name="Developer TARA")
        with Horizontal(id="dev_main_horizontal"):
            with Vertical(id="dev_left_vertical"):
                with Vertical(id="interpreted_scroll_view"):
                    yield ScrollView(
                        Static(RichPanel("Waiting for input...", title="Interpreted Command", border_style="green"), id="interpreted_content_static")
                    )
                with Vertical(id="explanation_dev_scroll_view"): # Renamed from "Warnings" to "Explanation/Warnings"
                    yield ScrollView(
                        Static(RichPanel("Explanation or warnings will appear here...", title="Explanation / Warnings", border_style="red"), id="explanation_dev_content_static")
                    )
            with Vertical(id="suggestion_dev_scroll_view"):
                yield ScrollView(
                    Static(RichPanel("Suggestions will appear here...", title="Command Suggestions", border_style="yellow"), id="suggestion_dev_static")
                )
        
        with Vertical(id="output_dev_scroll_view"):
            yield ScrollView(
                Static(RichPanel("(no output yet)", title="Command Output", border_style="magenta"), id="output_dev_content_static")
            )
        yield Input(placeholder="> Type your command, 'history', 'help', or 'quit'", id="prompt_input_dev")
        yield Footer()

    async def action_view_history_binding(self):
        await self.handle_view_history()

    async def handle_view_history(self):
        if not self.command_history:
            self.query_one("#output_dev_content_static", Static).update(
                RichPanel("History is empty.", title="Command Output", border_style="magenta")
            )
        else:
            await self.app.push_screen(HistoryScreen(history_data=self.command_history))
        self.query_one("#prompt_input_dev", Input).focus()


    async def on_input_submitted(self, event: Input.Submitted) -> None:
        cmd = event.value.strip()
        input_widget = self.query_one("#prompt_input_dev", Input)
        input_widget.value = "" # Clear input

        # Update interpreted command panel
        self.query_one("#interpreted_content_static", Static).update(
            RichPanel(f"> {cmd if cmd else 'No command entered'}", title="Interpreted Command", border_style="green")
        )
        # Clear other panels
        self.query_one("#explanation_dev_content_static", Static).update(
            RichPanel("...", title="Explanation / Warnings", border_style="red")
        )
        self.query_one("#output_dev_content_static", Static).update(
            RichPanel("...", title="Command Output", border_style="magenta")
        )
        # Suggestions are updated by the loop, but we can trigger it or reset its display
        self.query_one("#suggestion_dev_static", Static).update(
            RichPanel("Fetching suggestions...", title="Command Suggestions", border_style="yellow")
        )


        if cmd.lower() == "quit":
            self.exit()
            return
        elif cmd.lower() == "help":
            help_text = """
            ## 🆘 DevTARA Help - Available Commands

            - `view history` or `Ctrl+H` — Show all previous commands and outputs.
            - `quit` or `Ctrl+C` — Exit the program.
            - `[any valid command]` — Run that command and show explanation/output.
              (Natural Language `nl:` prefix is NOT supported in Dev Mode, use Student Mode for that.)
            - `cd [directory]` is handled to change the application's working directory.

            **Interface:**
            - **Interpreted Command:** Shows the command being processed.
            - **Explanation / Warnings:** Provides a summary/explanation (man page) or warnings.
            - **Command Suggestions:** Continuously updates with related commands based on current input.
            - **Command Output:** Displays the standard output and error from the command.
            """
            self.query_one("#output_dev_content_static", Static).update(
                RichPanel(Text(help_text, justify="left"), title="Help", border_style="cyan")
            )
            input_widget.focus()
            return
        elif cmd.lower() == "view history":
            await self.handle_view_history()
            input_widget.focus()
            return
        
        explanation_text = "N/A"
        output_text = "(no command to run)" 

        if cmd:
            # Dev mode does not use nl: prefix, directly executes commands
            if cmd.startswith("cd "):
                output_text = run_command(cmd)
                explanation_text = get_man_summary("cd")
            else:
                self.query_one("#explanation_dev_content_static", Static).update(
                    RichPanel(f"Fetching explanation for: '{cmd}'...", title="Explanation / Warnings", border_style="red")
                )
                command_name_for_man = cmd.split()[0] if cmd else ""
                explanation_text = await asyncio.to_thread(get_man_summary, command_name_for_man)
                
                self.query_one("#output_dev_content_static", Static).update(
                    RichPanel(f"Executing: {cmd}\n---", title="Command Output", border_style="magenta")
                )
                output_text = await asyncio.to_thread(run_command, cmd)

            self.query_one("#explanation_dev_content_static", Static).update(
                RichPanel(explanation_text, title="Explanation / Warnings", border_style="red")
            )
            self.query_one("#output_dev_content_static", Static).update(
                RichPanel(output_text, title="Command Output", border_style="magenta" if "Error" not in output_text and "Stderr" not in output_text else "red")
            )

            history_entry = {
                "timestamp": datetime.now(),
                "command": cmd,
                "explanation": explanation_text, # No separate 'translated_command' in dev mode
                "output": output_text
            }
            self.command_history.append(history_entry)
        else: # No command entered
            self.query_one("#explanation_dev_content_static", Static).update(
                RichPanel("Please enter a command to get an explanation.", title="Explanation / Warnings", border_style="red")
            )
            self.query_one("#output_dev_content_static", Static).update(
                RichPanel("(no command to run)", title="Command Output", border_style="magenta")
            )
        input_widget.focus()
        # Suggestion loop will pick up the new command from the input if needed,
        # or we can pass the executed command to the suggestion logic if preferred.

    async def update_suggestions_loop(self):
        import openai # Ensure openai is imported in this async context if not already module-level
        client = openai.OpenAI() # Initialize client once for the loop
        last_processed_input_for_suggestion = ""

        while True:
            await asyncio.sleep(2)  # Check every 2 seconds
            try:
                # Check if the app is still running and the input widget exists
                if not self.is_running or not self.is_mounted: break
                if not self.query("#prompt_input_dev"): break # Widget might be gone

                input_widget = self.query_one("#prompt_input_dev", Input)
                current_input_value = input_widget.value.strip()

                # Only generate new suggestions if the input has meaningfully changed
                # or if there's a command in history to base suggestions on.
                target_command_for_suggestions = ""
                if current_input_value and current_input_value != last_processed_input_for_suggestion:
                    target_command_for_suggestions = current_input_value
                    last_processed_input_for_suggestion = current_input_value
                elif not current_input_value and self.command_history: # If input is empty, use last command from history
                    target_command_for_suggestions = self.command_history[-1]['command']
                    if target_command_for_suggestions == last_processed_input_for_suggestion : # avoid re-processing same history command if input was cleared
                        await asyncio.sleep(2) # wait a bit longer if no new info
                        continue
                    last_processed_input_for_suggestion = target_command_for_suggestions # track history command used

                else: # No new input, no history, or same input as last time
                    await asyncio.sleep(2) # wait a bit longer
                    continue


                if target_command_for_suggestions and not target_command_for_suggestions.startswith("Error"):
                    # Check if suggestion panel exists before updating
                    suggestion_panels = self.query("#suggestion_dev_static")
                    if not suggestion_panels: break


                    suggestion_prompt = f"Based on the command or current input '{target_command_for_suggestions}', suggest 3 useful and distinct follow-up or related bash commands. Prioritize commands relevant to system administration, file management, or development. Provide only the commands, each on a new line, without explanations or numbering."
                    
                    # Use `asyncio.to_thread` for the blocking OpenAI call
                    suggestion_completion = await asyncio.to_thread(
                        lambda: client.chat.completions.create(
                            model="gpt-4o-mini",
                            messages=[
                                {"role": "system", "content": "You are a shell assistant. Provide only bash commands as requested."},
                                {"role": "user", "content": suggestion_prompt}
                            ],
                            temperature=0.5 # A bit of creativity
                        )
                    )
                    suggestion_text = suggestion_completion.choices[0].message.content.strip()
                    
                    # Check again if panel exists before update (might have closed screen)
                    if not self.query("#suggestion_dev_static"): break
                    self.query_one("#suggestion_dev_static", Static).update(
                        RichPanel(suggestion_text if suggestion_text else "No suggestions available.", title="Command Suggestions", border_style="yellow")
                    )
            except openai.RateLimitError:
                if not self.query("#suggestion_dev_static"): break
                self.query_one("#suggestion_dev_static", Static).update(
                    RichPanel("Suggestion rate limit reached. Please wait.", title="Command Suggestions", border_style="red")
                )
                await asyncio.sleep(60) # Wait longer if rate limited
            except asyncio.CancelledError:
                break # Exit loop if task is cancelled
            except Exception as e:
                # Only update if the widget still exists
                if self.query("#suggestion_dev_static"):
                    self.query_one("#suggestion_dev_static", Static).update(
                        RichPanel(f"Suggestion error: {type(e).__name__}", title="Command Suggestions", border_style="red")
                    )
                await asyncio.sleep(10) # Wait a bit before retrying on other errors


# dotenv.load_dotenv() # Not used in this scope

class User:
    def __init__(self):
        self.mode = "dev" # Default mode
        self.dry_mode = False # Not actively used in TUI, but part of state
        self.chat_on = False # Not actively used in TUI, but part of state
        self.command_history: List[dict] = [] # Ensure it's initialized as a list

        logs_dir = "logs"
        os.makedirs(logs_dir, exist_ok=True)
        self.log_file_path = os.path.join(logs_dir, f"session_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.log")

        # Defer file opening to when actually logging to avoid issues with app lifecycle / pickling if User is passed around
        self._log_state_to_file(f"Session started at {datetime.now().strftime('%Y-%m-%d %H-%M-%S')}\n", initial=True)

    def _log_state_to_file(self, message: str, initial: bool = False):
        # Appends message to the log file.
        try:
            with open(self.log_file_path, "a") as lf:
                lf.write(message)
                if not initial: # Don't log full state for every message, only for explicit state changes.
                    lf.write(f"  Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M-%S')}\n")
                    lf.write(f"  Mode: {self.mode}\n")
                    lf.write(f"  Dry mode: {self.dry_mode}\n")
                    lf.write(f"  Chat on: {self.chat_on}\n")
                lf.flush()
        except Exception as e:
            # If logging fails, print to console for awareness, but don't crash app.
            print(f"Error writing to log file: {e}", file=sys.stderr)


    def add_history_and_log(self, entry: dict):
        self.command_history.append(entry)
        log_message = (
            f"Command Logged:\n"
            f"  Timestamp: {entry['timestamp'].strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"  Command: {entry['command']}\n"
            f"  Translated: {entry.get('translated_command', 'N/A')}\n"
            f"  Explanation: {entry['explanation'][:100]}...\n" # Log snippet
            f"  Output: {entry['output'][:100]}...\n" # Log snippet
        )
        self._log_state_to_file(log_message)


    def set_mode(self, mode):
        if self.mode != mode:
            self.mode = mode
            self._log_state_to_file(f"Mode changed to: {self.mode}\n")

    def set_dry_mode(self, dry_mode): # Included for completeness if state is used elsewhere
        if self.dry_mode != dry_mode:
            self.dry_mode = dry_mode
            self._log_state_to_file(f"Dry mode changed to: {self.dry_mode}\n")

    def set_chat_on(self, chat_on): # Included for completeness
        if self.chat_on != chat_on:
            self.chat_on = chat_on
            self._log_state_to_file(f"Chat on changed to: {self.chat_on}\n")

    def close_log(self):
        self._log_state_to_file(f"Session ended at {datetime.now().strftime('%Y-%m-%d %H:%M-%S')}\n")

    # def __del__(self): # __del__ can be unreliable; prefer explicit close.
    #     self.close_log()


RED = '\033[91m'
GREEN = '\033[92m'
BLUE = '\033[94m'
RESET = '\033[0m'

rich_console = Console() 

def clear_screen():
    os.system("cls" if os.name == "nt" else "clear")

import sys
import termios
import tty

def get_single_keypress():
    # This function is problematic in a Textual app environment if called outside Textual's event loop.
    # For mode selection before app.run(), it's okay.
    if not sys.stdin.isatty(): # Check if stdin is a TTY
        # Fallback for non-TTY environments (e.g., piped input, some test runners)
        try:
            return sys.stdin.read(1)
        except:
            return "1" # Default to student mode or handle error

    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    return ch

def log_on(user: User): # This is the pre-TUI setup
    clear_screen()
    rich_console.print(f"{GREEN}Initializing STEPH/TARA...{RESET}")
    sleep(0.5) # Reduced sleep
    clear_screen()
    user._log_state_to_file(f"User login process started at {datetime.now().strftime('%Y-%m-%d %H-%M-%S')}\n")

    while True:
        rich_console.print("Select mode: \n1. Student (STEPH)\n2. Developer (TARA)\nChoice: ", end="", highlight=False)
        sys.stdout.flush() # Ensure prompt is shown before raw input
        mode_choice = get_single_keypress()
        print(mode_choice) 
        if mode_choice == "1":
            user.set_mode("student")
            break
        elif mode_choice == "2":
            user.set_mode("dev")
            break
        else:
            rich_console.print(f"{RED}Invalid choice. Please press 1 or 2.{RESET}")
            sleep(1)
            clear_screen() # Redraw prompt

    user._log_state_to_file(f"Mode selected: {user.mode}\n") # Log after mode is set.
    clear_screen()

    fig_banner_font = "small" if user.mode == "student" else "slant"
    fig_banner = pyfiglet.Figlet(font=fig_banner_font)
    banner_text = "STEPH" if user.mode == "student" else "TARA"
    ascii_banner = fig_banner.renderText(banner_text)
    
    rich_console.print(Text(ascii_banner, style="bold blue")) # Simpler banner display

    if user.mode == "student":
        rich_console.print(Text.assemble(
            ("🧠 STEPH — ", "white bold"),
            ("Semi-autonomous", "blue"), " ",
            ("Terminal", "magenta"), " for ",
            ("Responsive", "green"), " ",
            ("Action", "white")
        ), justify="center")
    else: # dev mode
        rich_console.print(Text.assemble(
            ("👩‍💻 TARA — ", "white bold"),
            ("Terminal", "blue"), " ",
            ("Assistant", "magenta"), " for ",
            ("Responsive", "green"), " ",
            ("Action", "white")
        ), justify="center")
    
    rich_console.print("\nLoading application...", style="italic")
    sleep(1) # Reduced sleep
    clear_screen()


def main():
    current_user = User()
    
    # Check if OPENAI_API_KEY is set
    if not openai.api_key:
        rich_console.print("[bold red]Error: OPENAI_API_KEY environment variable is not set.[/bold red]")
        rich_console.print("Please set it in your .env file or environment.")
        current_user.close_log() # Close log before exiting
        return

    try:
        log_on(current_user) # Pre-TUI setup
        if current_user.mode == "student":
            app = StudentTARA(user=current_user)
        else: # dev mode
            app = DevTARA() # DevTARA manages its own history for now.
                           # If User object's history is to be shared, pass `user=current_user`
                           # and DevTARA must use `self.user.command_history`.
                           # For this version, DevTARA has self.command_history

        app.run()
    except Exception as e:
        rich_console.print(f"[bold red]An unexpected error occurred in main: {e}[/bold red]")
        import traceback
        rich_console.print(traceback.format_exc())
    finally:
        current_user.close_log() # Ensure log is closed
        rich_console.print("Thanks for using the application! Find output in the logs/ folder.", style="bold green")

if __name__ == "__main__":
    main()