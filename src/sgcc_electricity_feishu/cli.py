import typer
from typing import Optional
from rich.console import Console
from .login import LoginHelper
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
def main():
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

if __name__ == "__main__":
    app()
