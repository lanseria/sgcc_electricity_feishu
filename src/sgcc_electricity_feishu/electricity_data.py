import time
import logging
import os
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from dotenv import load_dotenv


class ElectricityDataFetcher:
    def __init__(self, driver):
        self.driver = driver
        load_dotenv(verbose=True)
        self.IGNORE_USER_ID = os.getenv("IGNORE_USER_ID", "").split(",")
        self.RETRY_WAIT_TIME_OFFSET_UNIT = int(os.getenv("RETRY_WAIT_TIME_OFFSET_UNIT", 1))
        self.DRIVER_IMPLICITY_WAIT_TIME = int(os.getenv("DRIVER_IMPLICITY_WAIT_TIME", 10))
        # 获取USER_ID字符串，并分割为列表
        user_id_str = os.getenv("USER_ID", "")
        self.user_id_list = user_id_str.split(",") if user_id_str else []
        
    def _click_button(self, driver, button_search_type, button_search_key):
        '''wrapped click function, click only when the element is clickable'''
        click_element = driver.find_element(button_search_type, button_search_key)
        WebDriverWait(driver, self.DRIVER_IMPLICITY_WAIT_TIME).until(EC.element_to_be_clickable(click_element))
        driver.execute_script("arguments[0].click();", click_element)
        
    def _choose_current_userid(self, driver, userid_index):
        elements = driver.find_elements(By.CLASS_NAME, "button_confirm")
        if elements:
            self._click_button(driver, By.XPATH, f'''//*[@id="app"]/div/div[2]/div/div/div/div[2]/div[2]/div/button''')
        time.sleep(self.RETRY_WAIT_TIME_OFFSET_UNIT)
        self._click_button(driver, By.CLASS_NAME, "el-input__suffix")
        time.sleep(self.RETRY_WAIT_TIME_OFFSET_UNIT)
        self._click_button(driver, By.XPATH, f"/html/body/div[2]/div[1]/div[1]/ul/li[{userid_index+1}]/span")
        
    def _get_current_userid(self, driver):
        current_userid = driver.find_element(By.XPATH, '//*[@id="app"]/div/div/article/div/div/div[2]/div/div/div[1]/div[2]/div/div/div/div[2]/div/div[1]/div/ul/div/li[1]/span[2]').text
        return current_userid
    
    def get_daily_electricity_data(self):
        """获取日用电量数据"""
        logging.info("Try to get the userid list")
        
        # Get all user IDs
        user_id_list = self.user_id_list
        if not user_id_list:
            logging.error("Failed to get user IDs")
            return {}
            
        logging.info(f"Here are a total of {len(user_id_list)} userids: {user_id_list}. Ignoring: {self.IGNORE_USER_ID}")
        time.sleep(self.RETRY_WAIT_TIME_OFFSET_UNIT)

        result_data = {}
        for userid_index, user_id in enumerate(user_id_list):           
            try: 
                try:
                    # 首先用JS模拟点击展开详情
                    js_click_expand = """
                    const element = document.evaluate(
                    '//*[@id="main"]/div/div[1]/div/ul/li/div[2]/div/input',
                    document,
                    null,
                    XPathResult.FIRST_ORDERED_NODE_TYPE,
                    null
                    ).singleNodeValue;

                    // 2. 检查元素是否存在
                    if (element) {
                    console.log("找到元素:", element);
                    // 3. 模拟点击
                    element.click();
                    console.log("已触发点击");
                    } else {
                    console.error("未找到该 XPath 元素！");
                    }
                    """
                    self.driver.execute_script(js_click_expand)
                    time.sleep(1)  # 等待详情展开


                    # 然后模拟点击用户选择菜单
                    js_click_user_menu = f"""
                    // 尝试通过XPath找到用户选择菜单项
                    function getElementByXpath(path) {{
                        return document.evaluate(path, document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue;
                    }}

                    const userMenuItem = getElementByXpath('/html/body/div[2]/div[1]/div[1]/ul/li[{userid_index + 1}]');
                    if (userMenuItem) {{
                        userMenuItem.click();
                        return true;
                    }}
                    return false;
                    """
                    self.driver.execute_script(js_click_user_menu)
                    time.sleep(3)  # 等待用户切换
                    # 点击"日用电量"按钮
                    self._click_button(self.driver, By.XPATH, '//*[@id="tab-second"]')
                    time.sleep(3)  # 等待数据加载

                    # 执行JS脚本获取数据
                    js_script = """
                    // 获取tbody元素
                    const tbody = document.querySelector('#pane-second > div:nth-child(2) > div.about > div.el-table.about-table.trcen.el-table--fit.el-table--enable-row-hover.el-table--enable-row-transition > div.el-table__body-wrapper.is-scrolling-none > table > tbody');
                    if (!tbody) return [];
                    
                    const trList = tbody.querySelectorAll('tr');
                    const result = [];
                    
                    async function getData(tr, index) {
                        const date = tr.querySelector('td:nth-child(1) div')?.innerText.trim() || '';
                        const reading = tr.querySelector('td:nth-child(2) div')?.innerText.trim() || '';
                        
                        const thirdTd = tr.querySelector('td:nth-child(3) div div');
                        if (!thirdTd) return {date, reading, highNum: '0', lowNum: '0'};
                        
                        // 模拟点击
                        thirdTd.click();
                        await new Promise(resolve => setTimeout(resolve, 100));
                        
                        const targetTr = tbody.querySelector('tr.el-table__row.expanded');
                        if (!targetTr) return {date, reading, highNum: '0', lowNum: '0'};
                        
                        const nextTr = targetTr.nextElementSibling;
                        if (!nextTr) return {date, reading, highNum: '0', lowNum: '0'};
                        
                        const pList = nextTr.querySelector('td > div > div.drop-box-left');
                        if (!pList) return {date, reading, highNum: '0', lowNum: '0'};
                        
                        const lowNum = pList.querySelector('p:nth-child(1) span.num')?.innerText.trim() || '0';
                        const highNum = pList.querySelector('p:nth-child(3) span.num')?.innerText.trim() || '0';
                        
                        return {date, reading, highNum, lowNum};
                    }
                    
                    // 逐个处理每行数据
                    for (let i = 0; i < trList.length; i++) {
                        const data = await getData(trList[i], i);
                        result.push(data);
                    }
                    
                    return result;
                    """
                    
                    # 执行JS并获取结果
                    data = self.driver.execute_script(js_script)
                    result_data[user_id] = data
                    # logging.info(f"成功获取用户{user_id}的用电数据: {json.dumps(data, indent=2, ensure_ascii=False)}")

                except Exception as e:
                    if userid_index != len(user_id_list) - 1:
                        logging.info(f"用户{user_id}数据获取失败{e}, 将继续处理下一个用户")
                    else:
                        logging.info(f"用户{user_id}数据获取失败{e}")
                    continue

            except Exception as e:
                logging.error(f"处理用户{user_id}时发生错误: {e}")
                continue
        
        return result_data