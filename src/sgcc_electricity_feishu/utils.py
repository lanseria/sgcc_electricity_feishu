from datetime import datetime
from typing import List, Dict
import json
import os
from lark_oapi.api.bitable.v1 import AppTableRecord
from .login import LoginHelper
from .feishu_bitable import FeishuBitableHelper
from pathlib import Path

def get_sgcc_data_with_cache(cache_dir="sgcc_cache"):
    """
    获取国家电网数据，支持缓存功能
    
    Args:
        sgcc_helper: LoginHelper 实例
        cache_dir: 缓存目录名
        
    Returns:
        国家电网数据字典
    """
    # 确保缓存目录存在
    os.makedirs(cache_dir, exist_ok=True)
    
    # 生成缓存文件名 (基于当天日期)
    today = datetime.now().strftime("%Y-%m-%d")
    cache_file = os.path.join(cache_dir, f"{today}.json")
    
    # 如果缓存文件存在且非空，则直接读取
    if os.path.exists(cache_file) and os.path.getsize(cache_file) > 0:
        print(f"从缓存文件 {cache_file} 读取国家电网数据")
        with open(cache_file, "r", encoding="utf-8") as f:
            return json.load(f)
    
    # 否则从API获取数据并保存到缓存
    print("从API获取国家电网数据...")
    sgcc_helper = LoginHelper()
    sgcc_data = sgcc_helper.fetch_data()
    
    # 保存到缓存文件
    with open(cache_file, "w", encoding="utf-8") as f:
        json.dump(sgcc_data, f, ensure_ascii=False, indent=2)
    
    return sgcc_data

def convert_timestamp_to_date(timestamp: int) -> str:
    """将飞书的时间戳(毫秒)转换为YYYY-MM-DD格式的日期字符串"""
    return datetime.fromtimestamp(timestamp/1000).strftime('%Y-%m-%d')

def fill_missing_data(feishu_records: List[AppTableRecord], sgcc_data: Dict) -> tuple[List[Dict], int]:
    """
    填补飞书数据中的缺失用电数据
    
    Args:
        feishu_records: 飞书记录列表 (AppTableRecord 对象)
        sgcc_data: 国家电网数据字典
        
    Returns:
        填补后的记录列表(字典格式)
    """
    # 电表号映射
    METER_MAPPING = {
        '充电桩': '3309936803599',
        '家用': '3309936495378'
    }
    
    # 预处理国家电网数据
    sgcc_records = {}
    for meter_type, meter_id in METER_MAPPING.items():
        for record in sgcc_data.get(meter_id, []):
            date = record['date']
            if date not in sgcc_records:
                sgcc_records[date] = {}
            
            # 转换数据类型并处理可能的空值
            high_num = float(record['highNum']) if record['highNum'] else 0.0
            low_num = float(record['lowNum']) if record['lowNum'] else 0.0
            
            if meter_type == '充电桩':
                sgcc_records[date]['充电桩峰电度数'] = high_num
                sgcc_records[date]['充电桩谷电度数'] = low_num
            else:
                sgcc_records[date]['家用峰电度数'] = high_num
                sgcc_records[date]['家用谷电度数'] = low_num
    
    # 填补飞书数据
    filled_count = 0
    result = []
    
    for record in feishu_records:
        # 转换为字典格式便于处理
        fields = record.fields
        
        # 获取日期字符串
        try:
            date_str = convert_timestamp_to_date(fields['日期'])
        except KeyError:
            continue  # 如果没有日期字段则跳过
        
        if date_str not in sgcc_records:
            result.append(record.__dict__)
            continue
        
        # 获取该日期的国家电网数据
        sgcc_fields = sgcc_records[date_str]
        
        # 检查并填补各字段
        for field in ['充电桩峰电度数', '充电桩谷电度数', '家用峰电度数', '家用谷电度数']:
            # 如果字段不存在或值为0，则尝试填补
            if field not in fields or fields.get(field, 0) == 0:
                if field in sgcc_fields and sgcc_fields[field] != 0:
                    fields[field] = sgcc_fields[field]
                    filled_count += 1
                else:
                    fields[field] = 0
        
        result.append(record.__dict__)
    
    print(f"成功填补了 {filled_count} 条缺失数据")
    return result, filled_count



def update_filled_records_to_feishu(filled_records: List[Dict], feishu_helper: FeishuBitableHelper):
    """
    将填补后的数据更新回飞书表格
    
    Args:
        filled_records: 填补后的记录列表
        feishu_helper: FeishuBitableHelper 实例
    """
    updated_count = 0
    
    for record in filled_records:
        record_id = record.get("record_id")
        fields = record.get("fields", {})
        
        # 只更新包含用电量字段的记录
        if record_id and any(field in fields for field in ["充电桩峰电度数", "充电桩谷电度数", "家用峰电度数", "家用谷电度数"]):
            try:
                # 准备更新数据，只包含需要更新的字段
                update_fields = {
                    k: v for k, v in fields.items() 
                    if k in ["充电桩峰电度数", "充电桩谷电度数", "家用峰电度数", "家用谷电度数"]
                }
                
                if update_fields:
                    # 调用飞书API更新记录
                    feishu_helper.update_record(
                        record_id=record_id,
                        fields_dict=update_fields
                    )
                    updated_count += 1
                    print(f"已更新记录 {record_id}: {update_fields}")
            except Exception as e:
                print(f"更新记录 {record_id} 失败: {str(e)}")
    
    print(f"\n总共更新了 {updated_count} 条记录")


def save_to_json(data: List[Dict], filename: str, output_dir: str = "output"):
    """
    将数据保存为JSON文件
    
    Args:
        data: 要保存的数据列表
        filename: 文件名（不需要.json后缀）
        output_dir: 输出目录名
    """
    # 确保输出目录存在
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    # 添加时间戳确保文件名唯一
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = Path(output_dir) / f"{filename}_{timestamp}.json"
    
    # 保存为JSON文件
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    print(f"数据已保存到: {filepath}")