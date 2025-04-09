import typer
from typing import Optional
from rich.console import Console
from .login import LoginHelper

app = typer.Typer()
console = Console()

@app.command()
def hello(name: Optional[str] = typer.Argument(None)):
    """Simple greeting command"""
    if name:
        console.print(f"Hello [bold green]{name}[/bold green]!")
    else:
        console.print("Hello [bold blue]World[/bold blue]!")

@app.command()
def login():
    """执行国家电网账号登录"""
    helper = None
    console.print("开始执行登录...")
    try:
        helper = LoginHelper()
        if helper.login():
            console.print("[bold green]登录成功[/bold green]")
        else:
            console.print("[bold red]登录失败[/bold red]")
    except ValueError as ve:
        console.print(f"[bold red]配置错误: {ve}[/bold red]")
    except Exception as e:
        console.print(f"[bold red]执行过程中出错: {e}[/bold red]")
    finally:
        if helper:
            console.print("关闭浏览器...")
            helper.close()
        console.print("登录流程结束。")


if __name__ == "__main__":
    app()
