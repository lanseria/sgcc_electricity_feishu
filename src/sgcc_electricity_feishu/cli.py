import os
from dotenv import load_dotenv
import typer
from typing import Optional
from rich.console import Console
from .login import LoginHelper
from .feishu_bitable import FeishuBitableHelper

load_dotenv()

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
def sgcc_login():
    """执行国家电网账号登录"""
    helper = None
    console.print("开始执行登录...")
    try:
        helper = LoginHelper()
        if helper.wrapped_login():
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


@app.command()
def bitable_list():
    """列出飞书多维表格应用"""
    console.print("初始化 FeishuBitableHelper ...")
    try:
        helper = FeishuBitableHelper()
        # helper.list_table_fields(view_id="veweYY5B8i")
        helper.list_records(view_id="veweYY5B8i", 
            field_names=["日期", "家用峰电度数", "家用谷电度数", "充电桩峰电度数", "充电桩谷电度数"], 
            sort=[{"field_name": "日期", "desc": True}]
        )
    except Exception as e:
        console.print(f"[bold red]获取多维表格应用失败: {e}[/bold red]")

@app.command()
def bitable_update():
    """列出飞书多维表格应用"""
    console.print("初始化 FeishuBitableHelper ...")
    try:
        helper = FeishuBitableHelper()
        helper.update_record(record_id="recuHJjGgBE8F0", fields_dict={
            "充电桩峰电度数": 0,
            "充电桩谷电度数": 0,
            "家用峰电度数": 0,
            "家用谷电度数": 0
        })
    except Exception as e:
        console.print(f"[bold red]获取多维表格应用失败: {e}[/bold red]")


if __name__ == "__main__":
    app()
