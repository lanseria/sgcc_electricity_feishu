import typer
from typing import Optional
from rich.console import Console
from .login import LoginHelper
import time
from datetime import datetime, timedelta
from .feishu_bitable import FeishuBitableHelper
from .utils import fill_missing_data, get_sgcc_data_with_cache, update_filled_records_to_feishu, save_to_json

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
        data = helper.fetch_data()
        if data:
            console.print(data)
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
        helper.list_records(field_names=["日期", "家用峰电度数", "家用谷电度数", "充电桩峰电度数", "充电桩谷电度数"], 
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

@app.command()
def run_sync_job():
    # 初始化飞书助手
    feishu_helper = FeishuBitableHelper()
    
    # 获取飞书数据 (返回的是AppTableRecord对象列表)
    feishu_response = feishu_helper.list_records(field_names=["日期", "家用峰电度数", "家用谷电度数", "充电桩峰电度数", "充电桩谷电度数"], 
        sort=[{"field_name": "日期", "desc": True}]
    )
    
    # 获取国家电网数据(带缓存)
    sgcc_data = get_sgcc_data_with_cache()

    # 填补缺失数据
    filled_records, filled_count = fill_missing_data(feishu_response.items, sgcc_data)
    
    # 保存填补后的数据用于调试
    save_to_json(filled_records, "filled_records")
    # 将填补后的数据更新回飞书
    if filled_count > 0:
        update_filled_records_to_feishu(filled_records, feishu_helper)


@app.command()
def schedule_daily(hour: int = typer.Option(18, help="每天执行的小时（24小时制）"), minute: int = typer.Option(0, help="每天执行的分钟")):
    """
    每天定时执行一次数据同步，默认每天 18:00 执行
    """
    console.print(f"[bold green]定时任务启动，每天{hour:02d}:{minute:02d}执行一次...[/bold green]")
    while True:
        now = datetime.now()
        next_run = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if now >= next_run:
            # 已过今天执行时间，则定到明天
            next_run += timedelta(days=1)
        sleep_seconds = (next_run - now).total_seconds()
        console.print(f"距离下次执行还有 {int(sleep_seconds)} 秒，预计下次执行时间: {next_run}")
        time.sleep(sleep_seconds)
        try:
            run_sync_job()
        except Exception as e:
            console.print(f"[bold red]定时任务执行失败: {e}[/bold red]")
if __name__ == "__main__":
    app()
