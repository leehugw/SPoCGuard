from rich.panel import Panel
from rich.table import Table
from typing import List

def make_prompt_panel(code:str, prompt:str, panel_title:str) -> Panel:
    return f"\n--- {panel_title} ---\nKnowledge: {prompt}\nCode:\n{code}\n"

def make_response_panel(response:str, panel_title:str) -> Panel:
    return f"\n--- {panel_title} ---\n{response}\n"

def make_args_table(args:List[str], title:str) -> Table:
    table = Table(title=title)
    table.add_column("Argument")
    table.add_column("Value")
    for index, arg in enumerate(args):
        if isinstance(arg, str):
            table.add_row(f"arg\[{index}]", arg)
        elif isinstance(arg, list):
            table.add_row(f"arg\[{index}]", "\[" + ", ".join(arg) + "]")
        else:
            breakpoint()
    return table
