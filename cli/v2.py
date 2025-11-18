from typing import List, Optional
import json
import asyncio

from openai.types.responses import (
    ResponseTextDeltaEvent,
    ResponseReasoningTextDeltaEvent,
    ResponseReasoningSummaryTextDeltaEvent,
)
from agents import (
    Agent,
    RawResponsesStreamEvent,
    Runner,
    RunResultStreaming,
    RunItemStreamEvent,
    TResponseInputItem,
    set_tracing_disabled,
)

from textual import on
from textual.app import App, ComposeResult
from textual.containers import (
    Container,
    Horizontal,
    Vertical,
    ScrollableContainer,
    Grid,
)
from textual.widgets import (
    Button,
    Input,
    Static,
    Footer,
    Label,
    ListView,
    ListItem,
    RichLog,
    Switch,
    RadioSet,
    RadioButton,
    LoadingIndicator,
)
from textual.binding import Binding
from textual.screen import Screen
from textual.css.query import NoMatches

from .art import get_art
from config.agent_config import Version, MAX_TURNS

# from stt.WhisperSTT import STT
from tts.KokoroTTS import KokoroTTS as TTS
from my_agents import context_agent, memory_agent


set_tracing_disabled(disabled=True)


MESSAGE_HISTORY: list[TResponseInputItem] = []

_tts = None


def get_tts():
    global _tts
    if _tts is None:
        _tts = TTS()
    return _tts


class AgentApp(App):
    """Main Textual application for the AI agent."""

    CSS = """
    Screen {
        background: $surface;
    }

    #welcome-art {
        text-align: center;
        color: $primary;
        margin: 1;
    }

    .header-title {
        text-align: center;
        text-style: bold;
        color: $text;
        margin-bottom: 1;
    }

    #header {
        height: auto;
        background: $primary;
        color: $text;
        padding: 1;
        border-bottom: solid $primary;
    }

    #chat-container {
        height: 1fr;
        border: solid $primary;
        margin: 1;
    }

    #input-container {
        height: 3;
        border-top: solid $primary;
        margin: 1 1 0 1;
    }

    #sidebar {
        width: 30;
        background: $panel;
        border-left: solid $primary;
        padding: 1;
    }

    .sidebar-title {
        text-style: bold;
        margin-bottom: 1;
    }

    Button {
        margin: 0 1 1 0;
        width: 100%;
    }

    Input {
        border: solid $primary;
        margin: 0;
    }

    RichLog {
        border: solid $primary;
        margin: 0;
        background: $surface;
    }

    #message-input {
        width: 100%;
    }

    .screen-title {
        text-align: center;
        text-style: bold;
        margin-bottom: 2;
    }

    .dialog-buttons {
        margin-top: 2;
        align: center middle;
    }

    RadioSet {
        margin: 1 0;
    }

    Switch {
        margin-left: 1;
    }
    """

    BINDINGS = [
        Binding("ctrl+c", "exit", "Quit"),
        Binding("ctrl+h", "show_help", "Help"),
        Binding("ctrl+r", "clear_chat", "Clear"),
        Binding("ctrl+a", "show_agents", "Agents"),
        Binding("ctrl+m", "show_modes", "Modes"),
        Binding("ctrl+y", "show_history", "History"),
        Binding("enter", "submit_message", "Send", show=False),
    ]

    def __init__(self):
        super().__init__()
        self.agents = {}
        self.current_agent = None
        self.hierarchy_mode = "managerial"
        self.interaction_mode = "text"
        self.use_context_agent = False
        self.session_context = ""
        self.message_history: List[TResponseInputItem] = []
        self.multi_line_mode = False
        self.multi_line_buffer = []

    def compose(self) -> ComposeResult:
        """Create the UI layout."""
        # Header with art and title
        with Vertical(id="header"):
            yield Static(get_art(), id="welcome-art")
            yield Static(f"Omen AI Assistant v{Version}", classes="header-title")

        with Horizontal():
            with Vertical(id="main-content"):
                # Chat container
                with ScrollableContainer(id="chat-container"):
                    yield RichLog(id="chat-log", markup=True)

                # Input container
                with Container(id="input-container"):
                    yield Input(
                        placeholder="Type your message or /help for commands...",
                        id="message-input",
                    )

            # Sidebar
            with Vertical(id="sidebar"):
                yield Label("Current Agent", classes="sidebar-title")
                yield Static("None", id="current-agent-display")

                yield Label("Modes", classes="sidebar-title")
                yield Static("Hierarchy: managerial", id="hierarchy-display")
                yield Static("Interaction: text", id="interaction-display")
                yield Static("Context: No", id="context-display")

                yield Label("Commands", classes="sidebar-title")
                yield Button("Help", id="help-btn", variant="primary")
                yield Button("History", id="history-btn")
                yield Button("Agents", id="agents-btn")
                yield Button("Modes", id="modes-btn")
                yield Button("Clear", id="clear-btn", variant="error")

        yield Footer()

    async def on_mount(self) -> None:
        """Initialize the app."""
        # Load agents
        self.agents = self.load_agents()
        if self.agents:
            self.current_agent = list(self.agents.values())[0]
            self.update_sidebar()

        # Show welcome message
        await self.show_welcome()

    def load_agents(self) -> dict:
        """Load available agents."""
        from agent_runtime import get_agent_registry

        agents, _ = get_agent_registry()
        return agents

    def update_sidebar(self):
        """Update sidebar displays."""
        try:
            agent_display = self.query_one("#current-agent-display", Static)
            agent_display.update(
                str(self.current_agent.name).capitalize()
                if self.current_agent
                else "None"
            )

            hierarchy_display = self.query_one("#hierarchy-display", Static)
            hierarchy_display.update(f"Hierarchy: {self.hierarchy_mode}")

            interaction_display = self.query_one("#interaction-display", Static)
            interaction_display.update(f"Interaction: {self.interaction_mode}")

            context_display = self.query_one("#context-display", Static)
            context_display.update(
                f"Context: {'Yes' if self.use_context_agent else 'No'}"
            )
        except NoMatches:
            pass

    async def show_welcome(self):
        """Show welcome message."""
        chat_log = self.query_one("#chat-log", RichLog)
        chat_log.write("[bold red]Welcome to Omen AI Assistant![/bold red]")
        chat_log.write(f"Version: {Version}")
        chat_log.write("")
        chat_log.write("Type your message below or use commands:")
        chat_log.write("- /help or Ctrl+H - Show help")
        chat_log.write("- /agents or Ctrl+A - List and switch agents")
        chat_log.write("- /modes or Ctrl+M - Change interaction modes")
        chat_log.write("- /history or Ctrl+Y - Show conversation history")
        chat_log.write("- /clear or Ctrl+R - Clear chat")
        chat_log.write("- /quit or Ctrl+C - Exit")
        chat_log.write("")

    @on(Input.Submitted, "#message-input")
    async def on_message_submitted(self, event: Input.Submitted) -> None:
        """Handle message input."""
        message = event.value.strip()
        if not message:
            return

        # Check for multi-line input
        if message.startswith("<ml>"):
            # Switch to multi-line mode
            input_widget = self.query_one("#message-input", Input)
            input_widget.placeholder = "Multi-line mode: end with </ml> on a new line"
            input_widget.value = ""
            self.multi_line_buffer = []
            self.multi_line_mode = True
            return

        if hasattr(self, "multi_line_mode") and self.multi_line_mode:
            if message.strip() == "</ml>":
                # End multi-line input
                full_message = "\n".join(self.multi_line_buffer)
                self.multi_line_mode = False
                input_widget = self.query_one("#message-input", Input)
                input_widget.placeholder = "Type your message or /help for commands..."
                await self.process_message(full_message)
            else:
                self.multi_line_buffer.append(message)
                input_widget = self.query_one("#message-input", Input)
                input_widget.value = ""
            return

        await self.process_message(message)

    async def process_message(self, message: str):
        """Process a complete message."""
        input_widget = self.query_one("#message-input", Input)
        input_widget.value = ""

        if message.startswith("/"):
            await self.handle_command(message)
        else:
            await self.send_message(message)

    async def handle_command(self, command: str):
        """Handle slash commands."""
        parts = command.split()
        cmd = parts[0].lower()

        if cmd == "/help":
            await self.show_help()
        elif cmd == "/agents":
            await self.show_agents()
        elif cmd == "/modes":
            await self.show_modes()
        elif cmd == "/history":
            await self.show_history()
        elif cmd == "/clear":
            await self.clear_chat()
        elif cmd == "/quit":
            self.exit()
        else:
            chat_log = self.query_one("#chat-log", RichLog)
            chat_log.write(f"[red]Unknown command: {cmd}[/red]")

    async def show_help(self):
        """Show help information."""
        chat_log = self.query_one("#chat-log", RichLog)
        chat_log.write("[bold]Available Commands:[/bold]")
        chat_log.write("/help - Show this help")
        chat_log.write("/agents - List and switch agents")
        chat_log.write("/modes - Change interaction modes")
        chat_log.write("/history - Show conversation history")
        chat_log.write("/clear - Clear chat history")
        chat_log.write("/quit - Exit application")
        chat_log.write("")

    async def show_agents(self):
        """Show available agents."""
        await self.show_agents_screen()

    async def show_modes(self):
        """Show mode selection screen."""
        await self.push_screen(ModeSelectionScreen())

    async def clear_chat(self):
        """Clear chat history."""
        chat_log = self.query_one("#chat-log", RichLog)
        chat_log.clear()
        self.message_history.clear()
        await self.show_welcome()

    async def send_message(self, message: str):
        """Send a message to the agent."""
        if not self.current_agent:
            chat_log = self.query_one("#chat-log", RichLog)
            chat_log.write("[red]No agent selected[/red]")
            return

        # Add user message to history
        self.message_history.append({"content": message, "role": "user"})

        # Display user message
        chat_log = self.query_one("#chat-log", RichLog)
        chat_log.write(f"[bold blue]You:[/bold blue] {message}")

        # Handle context agent if enabled
        if self.use_context_agent:
            await self.handle_context_agent(message)

        # Show loading indicator
        # loading = LoadingIndicator()
        # chat_log.write(loading)

        try:
            # Stream response
            agent, result = await self.stream_agent_response(
                self.current_agent, self.message_history.copy(), self.hierarchy_mode
            )

            # Update current agent if changed
            if agent != self.current_agent:
                self.current_agent = agent
                self.update_sidebar()

            # Update message history
            self.message_history = result.to_input_list()

            # Update context if using context agent
            if self.use_context_agent:
                await self.update_context_agent(result)

        except Exception as e:
            chat_log.write(f"[red]Error: {str(e)}[/red]")
        finally:
            # Remove loading indicator (this is simplified)
            pass

    async def handle_context_agent(self, message: str):
        """Handle context agent for memory."""
        try:
            from my_agents import context_agent

            # This would integrate with context agent
            # For now, just update session context
            pass
        except ImportError:
            pass

    async def update_context_agent(self, result):
        """Update context after response."""
        try:
            from my_agents import context_agent

            # This would update context
            pass
        except ImportError:
            pass

    async def stream_agent_response(
        self, agent: Agent, inputs: list[TResponseInputItem], hierarchy_mode: str
    ) -> tuple[Agent, RunResultStreaming]:
        """Stream the agent's response."""
        result = Runner.run_streamed(
            starting_agent=agent, input=inputs, max_turns=MAX_TURNS
        )

        chat_log = self.query_one("#chat-log", RichLog)
        full_response = ""
        events = []
        thinking_text = ""
        agent_name = str(agent.name).capitalize()

        # Start agent response
        chat_log.write(f"[bold green]{agent_name}:[/bold green] ")

        async for event in result.stream_events():
            if isinstance(event, RawResponsesStreamEvent):
                data = event.data

                if isinstance(data, ResponseTextDeltaEvent):
                    delta = data.delta

                    if "<think>" in delta:
                        thinking_text = ""
                        chat_log.write("[dim](thinking...)")
                    elif "</think>" in delta:
                        if thinking_text.strip():
                            chat_log.write(
                                f"\n[dim]Reasoning: {thinking_text.strip()}[/dim]\n"
                            )
                        thinking_text = ""
                    elif thinking_text:
                        thinking_text += delta
                    else:
                        full_response += delta
                        chat_log.write(delta)

                elif isinstance(data, ResponseReasoningTextDeltaEvent):
                    thinking_text += data.delta

            elif isinstance(event, RunItemStreamEvent):
                if event.name == "handoff_occured":
                    target_name = event.item.target_agent.name
                    display_target = str(target_name).capitalize()

                    if hierarchy_mode == "collaborative":
                        agent = event.item.target_agent
                        handoff_msg = (
                            f"[yellow]→ Handed-off to {display_target}[/yellow]"
                        )
                    else:
                        handoff_msg = (
                            f"[yellow]→ Delegated to {display_target}[/yellow]"
                        )
                    chat_log.write(f"\n{handoff_msg}\n")

                elif event.name == "tool_called":
                    tool_name = getattr(event.item.raw_item, "name", "unknown tool")
                    if tool_name.startswith("transfer_"):
                        continue
                    chat_log.write(f"\n[blue]Tool: {tool_name}[/blue]")

        # Finish the response
        chat_log.write("\n")
        return agent, result

    # Action handlers for bindings
    def action_exit(self):
        """Quit the application."""
        self.exit()

    def action_show_help(self):
        """Show help."""
        asyncio.create_task(self.show_help())

    def action_clear_chat(self):
        """Clear chat."""
        asyncio.create_task(self.clear_chat())

    def action_show_agents(self):
        """Show agents."""
        asyncio.create_task(self.show_agents())

    def action_show_modes(self):
        """Show modes."""
        asyncio.create_task(self.show_modes())

    def action_show_history(self):
        """Show history."""
        asyncio.create_task(self.show_history())

    # Button handlers
    @on(Button.Pressed, "#help-btn")
    async def on_help_pressed(self):
        await self.show_help()

    @on(Button.Pressed, "#history-btn")
    async def on_history_pressed(self):
        await self.show_history()

    @on(Button.Pressed, "#agents-btn")
    async def on_agents_pressed(self):
        await self.show_agents()

    @on(Button.Pressed, "#modes-btn")
    async def on_modes_pressed(self):
        await self.show_modes()

    @on(Button.Pressed, "#clear-btn")
    async def on_clear_pressed(self):
        await self.clear_chat()

    async def show_agents_screen(self):
        """Show agent selection screen."""
        await self.push_screen(AgentSelectionScreen())

    async def show_history(self):
        """Show conversation history."""
        await self.push_screen(HistoryScreen())


class ModeSelectionScreen(Screen):
    """Screen for selecting interaction modes."""

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label("Select Modes", classes="screen-title")

            with Grid():
                # Hierarchy mode
                with Vertical():
                    yield Label("Hierarchy Mode")
                    with RadioSet(id="hierarchy-mode"):
                        yield RadioButton(
                            "Managerial (default)", value=True, id="managerial"
                        )
                        yield RadioButton(
                            "Collaborative", value=False, id="collaborative"
                        )

                # Interaction mode
                with Vertical():
                    yield Label("Interaction Mode")
                    with RadioSet(id="interaction-mode"):
                        yield RadioButton("Text (default)", value=True, id="text")
                        yield RadioButton("Voice", value=False, id="voice")

            # Context agent
            with Horizontal():
                yield Label("Use Context Agent")
                yield Switch(id="context-agent", value=False)

            with Horizontal(classes="dialog-buttons"):
                yield Button("OK", variant="primary", id="ok-btn")
                yield Button("Cancel", id="cancel-btn")

    @on(Button.Pressed, "#ok-btn")
    def on_ok_pressed(self):
        """Apply mode selections."""
        hierarchy_radio = self.query_one("#hierarchy-mode", RadioSet)
        interaction_radio = self.query_one("#interaction-mode", RadioSet)
        context_switch = self.query_one("#context-agent", Switch)

        hierarchy_mode = (
            "managerial"
            if hierarchy_radio.pressed_button.id == "managerial"
            else "collaborative"
        )
        interaction_mode = (
            "text" if interaction_radio.pressed_button.id == "text" else "voice"
        )
        use_context = context_switch.value

        # Update main app
        app = self.app
        app.hierarchy_mode = hierarchy_mode
        app.interaction_mode = interaction_mode
        app.use_context_agent = use_context
        app.update_sidebar()

        self.dismiss()

    @on(Button.Pressed, "#cancel-btn")
    def on_cancel_pressed(self):
        """Cancel mode selection."""
        self.dismiss()


class AgentSelectionScreen(Screen):
    """Screen for selecting agents."""

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label("Select Agent", classes="screen-title")

            with ScrollableContainer():
                agent_list = []
                for key, agent in self.app.agents.items():
                    agent_list.append(
                        ListItem(Label(f"{key}: {agent.name}"), id=f"agent-{key}")
                    )
                yield ListView(*agent_list, id="agent-list")

            with Horizontal(classes="dialog-buttons"):
                yield Button("Switch", variant="primary", id="switch-btn")
                yield Button("Cancel", id="cancel-btn")

    @on(Button.Pressed, "#switch-btn")
    def on_switch_pressed(self):
        """Switch to selected agent."""
        agent_list = self.query_one("#agent-list", ListView)
        if agent_list.highlighted_child:
            item_id = agent_list.highlighted_child.id
            if item_id and item_id.startswith("agent-"):
                agent_key = item_id[6:]  # Remove "agent-" prefix
                if agent_key in self.app.agents:
                    self.app.current_agent = self.app.agents[agent_key]
                    self.app.update_sidebar()
                    self.app.query_one("#chat-log", RichLog).write(
                        f"[yellow]Switched to {agent_key} agent[/yellow]"
                    )

        self.dismiss()

    @on(Button.Pressed, "#cancel-btn")
    def on_cancel_pressed(self):
        """Cancel agent selection."""
        self.dismiss()


class HistoryScreen(Screen):
    """Screen for viewing conversation history."""

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label("Conversation History", classes="screen-title")

            with ScrollableContainer():
                yield RichLog(id="history-log", markup=True)

            with Horizontal(classes="dialog-buttons"):
                yield Button("Close", id="close-btn")

    async def on_mount(self) -> None:
        """Load and display history."""
        history_log = self.query_one("#history-log", RichLog)
        if not self.app.message_history:
            history_log.write("[dim]No conversation history available.[/dim]")
            return

        for entry in self.app.message_history:
            role = entry.get("role", "") or entry.get("type", "unknown")
            role = str(role)
            content = entry.get("content", "")

            if content:
                if isinstance(content, str):
                    history_log.write(f"# {role.capitalize()}\n\n{content}\n\n")
                elif isinstance(content, list):
                    for item in content:
                        if isinstance(item, dict) and "text" in item:
                            if item["text"].strip() != "":
                                history_log.write(
                                    f"# {role.capitalize()}\n\n{item['text']}\n\n"
                                )
                        else:
                            history_log.write(f"# {role.capitalize()}\n\n{item}\n\n")
                elif isinstance(content, dict):
                    history_log.write(
                        f"# {role.capitalize()}\n\n```json\n{json.dumps(content, indent=2)}\n```\n\n"
                    )
            else:
                # Handle function calls
                if "name" in entry:
                    name: str = entry["name"]
                    if entry["name"].startswith("transfer_"):
                        name = name.replace("_", " ").capitalize()
                        history_log.write(f"# Tool Call\n\n`{name}`\n\n")
                        continue
                    history_log.write(f"# Tool Call\n\n`{name}`\n\n")
                    if "arguments" in entry:
                        args = (
                            json.loads(entry["arguments"])
                            if isinstance(entry["arguments"], str)
                            else entry["arguments"]
                        )
                        history_log.write(
                            f"**Arguments:**\n\n```json\n{json.dumps(args, indent=2)}\n```\n\n"
                        )
                if "output" in entry:
                    output = entry["output"]
                    output = str(output)
                    if output.startswith('{"'):
                        continue
                    history_log.write(f"**Output:**\n```\n{output}\n```\n")

    @on(Button.Pressed, "#close-btn")
    def on_close_pressed(self):
        """Close history screen."""
        self.dismiss()


def main():
    """Main entry point."""
    app = AgentApp()
    app.run()


if __name__ == "__main__":
    main()
