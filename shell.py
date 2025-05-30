# demo_scroll.py
from textual.app import App, ComposeResult
from textual.widgets import Static
from textual.scroll_view import ScrollView
from textual.containers import Horizontal

class DemoScrollApp(App):
    CSS = """
    /* Make the app fill your terminal */
    Screen {
        display: grid;
        grid-template-rows: 1fr;
        height: 100%;
        padding: 0;
    }

    /* Single-row grid: our two panels side by side */
    #main {
        grid-row: 1;
        display: grid;
        grid-template-columns: 1fr 1fr;
        height: 100%;
    }

    /* Each ScrollView panel: fill cell and scroll its own content */
    #left, #right {
        height: 100%;
        overflow-y: auto;
        padding: 1;
        border: solid green;
    }
    """

    def compose(self) -> ComposeResult:
        yield Horizontal(id="main")
        yield ScrollView(
                Static("\n".join(f"Left line {i}" for i in range(200))),
                id="left"
            )
        yield ScrollView(
                Static("\n".join(f"Right line {i}" for i in range(200))),
                id="right"
            )

if __name__ == "__main__":
    DemoScrollApp().run()