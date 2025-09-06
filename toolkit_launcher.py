import os
import importlib
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table
from rich.text import Text

console = Console()
CONFIG_FILE = "config.ini"

def banner():
    logo = Text("""
███╗   ██╗ ██████╗  ██████╗  █████╗  ██████╗
████╗  ██║██╔═══██╗██╔════╝ ██╔══██╗██╔════╝
██╔██╗ ██║██║   ██║██║  ███╗███████║╚█████╗
██║╚██╗██║██║   ██║██║   ██║██╔══██║ ╚═══██╗
██║ ╚████║╚██████╔╝╚██████╔╝██║  ██║██████╔╝
╚═╝  ╚═══╝ ╚═════╝  ╚═════╝ ╚═╝  ╚═╝╚═════╝
CryptoToolkit v1.0 | Gemini | Python
""", style="bold magenta")
    console.print(logo, justify="center")

def main_menu():
    while True:
        console.clear()
        banner()
        table = Table(title="[bold cyan]Crypto Toolkit Menu[/bold cyan]", show_header=True, header_style="bold green")
        table.add_column("Key", style="cyan", width=6)
        table.add_column("Chức năng", style="yellow")
        table.add_row("1", "Thu thập ví từ wordlist (Collector)")
        table.add_row("2", "Kiểm tra số dư ví (Checker)")
        table.add_row("3", "Hunter (Brute-force ETH/BTC)")
        table.add_row("4", "Giám sát Blockchain (Watcher)")
        table.add_row("5", "Seed Phrase Generator & Checker")
        table.add_row("6", "Tiện ích (Export/Phân tích/Backup)")
        table.add_row("P", "Các plugin bổ sung")
        table.add_row("C", "Cấu hình (Nhập/chỉnh sửa API Key, link, v.v.)")
        table.add_row("Q", "Thoát")
        console.print(table)
        choice = Prompt.ask("Chọn chức năng", choices=["1","2","3","4","5","6","P","C","Q"], default="Q").upper()
        if choice == "Q":
            break
        elif choice == "C":
            config_menu()
        elif choice == "P":
            plugin_menu()
        else:
            run_builtin(choice)

def config_menu():
    console.print(Panel("[bold green]Cấu hình hệ thống[/bold green]\nBạn có thể nhập/chỉnh sửa API key, endpoint, số luồng, wordlist, ...\nMọi tham số đều được lưu vào config và có thể thay đổi bất kỳ lúc nào.", expand=False))
    while True:
        op = Prompt.ask("Nhập [api/endpoint/wordlist/threads/back/exit]", default="back")
        if op == "back" or op == "exit": break
        # TODO: Thực hiện lưu vào config.ini
        console.print(f"[yellow]Chức năng nhập tham số '{op}' sẽ được hoàn thiện ngay![/yellow]")

def plugin_menu():
    plugins = []
    plugins_dir = "plugins"
    if not os.path.exists(plugins_dir):
        os.makedirs(plugins_dir)
    for fname in os.listdir(plugins_dir):
        if fname.endswith(".py"):
            try:
                mod_name = fname[:-3]
                mod = importlib.import_module(f"plugins.{mod_name}")
                plugins.append((mod_name, mod))
            except Exception:
                continue
    if not plugins:
        console.print("[yellow]Không có plugin nào.[/yellow]")
        Prompt.ask("Nhấn Enter để tiếp tục...")
        return
    for idx, (name, mod) in enumerate(plugins, 1):
        desc = getattr(mod, 'description', 'Không có mô tả')
        console.print(f"{idx}. {name} - {desc}")
    pidx = Prompt.ask("Chọn plugin số", default="1")
    try:
        idx = int(pidx) - 1
        plugins[idx][1].run()
    except:
        console.print("[red]Lựa chọn plugin không hợp lệ.[/red]")
        Prompt.ask("Nhấn Enter để tiếp tục...")

def run_builtin(choice):
    # TODO: Refactor các script chính thành module collector.py, checker.py, hunter.py, watcher.py, seed_tool.py, utils.py để gọi ở đây
    if choice == "1":
        console.print("[yellow]Đang chạy Collector...[/yellow]")
        # import collector; collector.run()
    elif choice == "2":
        console.print("[yellow]Đang chạy Checker...[/yellow]")
        # import checker; checker.run()
    elif choice == "3":
        console.print("[yellow]Đang chạy Hunter...[/yellow]")
        # import hunter; hunter.run()
    elif choice == "4":
        console.print("[yellow]Đang chạy Watcher...[/yellow]")
        # import watcher; watcher.run()
    elif choice == "5":
        console.print("[yellow]Đang chạy Seed Phrase Tool...[/yellow]")
        # import seed_tool; seed_tool.run()
    elif choice == "6":
        console.print("[yellow]Đang chạy Tiện ích...[/yellow]")
        # import utils; utils.run()
    Prompt.ask("Nhấn Enter để quay lại menu...")

if __name__ == "__main__":
    main_menu()