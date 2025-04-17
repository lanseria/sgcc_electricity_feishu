import lark_oapi as lark
from rich.console import Console
from lark_oapi.api.bitable.v1 import ListAppTableRecordRequest
from lark_oapi.api.contact.v3 import *
from dotenv import load_dotenv
import os

console = Console()

class FeishuBitableHelper:
    def __init__(self):
        load_dotenv()
        app_id = os.getenv("FEISHU_APP_ID")
        app_secret = os.getenv("FEISHU_APP_SECRET")
        console.print(app_id, app_secret)
        if not app_id or not app_secret:
            raise ValueError("请在.env文件中配置FEISHU_APP_ID和FEISHU_APP_SECRET")
        self.client = lark.Client.builder() \
            .app_id(app_id) \
            .app_secret(app_secret) \
            .log_level(lark.LogLevel.DEBUG) \
            .build()
        # 新增存储app_token和table_id
        self.app_token = os.getenv("BITABLE_APP_TOKEN")
        self.table_id = os.getenv("BITABLE_TABLE_ID")
        self.view_id = os.getenv("BITABLE_VIEW_ID")

    def list_records(self, field_names=None, sort=None, page_size=20):
        from lark_oapi.api.bitable.v1 import SearchAppTableRecordRequest, SearchAppTableRecordRequestBody, Sort

        request_body_builder = SearchAppTableRecordRequestBody.builder()

        if self.view_id:
            request_body_builder = request_body_builder.view_id(self.view_id)

        if field_names:
            request_body_builder = request_body_builder.field_names(field_names)

        if sort:
            sort_list = []
            for s in sort:
                sort_obj = Sort.builder() \
                    .field_name(s.get("field_name")) \
                    .desc(s.get("desc", False)) \
                    .build()
                sort_list.append(sort_obj)
            request_body_builder = request_body_builder.sort(sort_list)

        request_body = request_body_builder.automatic_fields(False).build()

        request = SearchAppTableRecordRequest.builder() \
            .app_token(self.app_token) \
            .table_id(self.table_id) \
            .page_size(page_size) \
            .request_body(request_body) \
            .build()

        response = self.client.bitable.v1.app_table_record.search(request)

        if response.success():
            # console.print("Records:", lark.JSON.marshal(response.data, indent=4))
            return response.data
        else:
            console.print(f"[red]Failed to search records, code: {response.code}, msg: {response.msg}[/red]")
            return None

    def list_table_fields(self, page_size=20):
        from lark_oapi.api.bitable.v1 import ListAppTableFieldRequest

        request_builder = ListAppTableFieldRequest.builder() \
            .app_token(self.app_token) \
            .table_id(self.table_id) \
            .page_size(page_size)

        if self.view_id:
            request_builder = request_builder.view_id(self.view_id)

        request = request_builder.build()

        response = self.client.bitable.v1.app_table_field.list(request)

        if response.success():
            console.print("Fields:", lark.JSON.marshal(response.data, indent=4))
            return response.data
        else:
            console.print(f"[red]Failed to list fields, code: {response.code}, msg: {response.msg}[/red]")
            return None

    def update_record(self, record_id=None, fields_dict=None):
        from lark_oapi.api.bitable.v1 import UpdateAppTableRecordRequest, AppTableRecord

        request = UpdateAppTableRecordRequest.builder() \
            .app_token(self.app_token) \
            .table_id(self.table_id) \
            .record_id(record_id) \
            .request_body(
                AppTableRecord.builder()
                .fields(fields_dict)
                .build()
            ) \
            .build()

        response = self.client.bitable.v1.app_table_record.update(request)

        if response.success():
            # console.print("Update success:", lark.JSON.marshal(response.data, indent=4))
            return response.data
        else:
            console.print(f"[red]Failed to update record, code: {response.code}, msg: {response.msg}[/red]")
            return None
