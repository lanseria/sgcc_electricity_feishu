import time
import json
import logging
import os
import re
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from dotenv import load_dotenv
from .const import BALANCE_URL


class ElectricityDataFetcher:
    def __init__(self, driver):
        self.driver = driver
        load_dotenv(verbose=True)
        self.IGNORE_USER_ID = os.getenv("IGNORE_USER_ID")
        self.RETRY_WAIT_TIME_OFFSET_UNIT = int(os.getenv("RETRY_WAIT_TIME_OFFSET_UNIT"))
        self.DRIVER_IMPLICITY_WAIT_TIME = 10

    def _get_user_ids(self, driver):
        try:
            # 刷新网页
            driver.refresh()
            time.sleep(self.RETRY_WAIT_TIME_OFFSET_UNIT*2)
            element = WebDriverWait(driver, self.DRIVER_IMPLICITY_WAIT_TIME).until(
                EC.presence_of_element_located((By.CLASS_NAME, 'el-dropdown')))
            # click roll down button for user id
            self._click_button(driver, By.XPATH, "//div[@class='el-dropdown']/span")
            logging.debug(f'''self._click_button(driver, By.XPATH, "//div[@class='el-dropdown']/span")''')
            time.sleep(self.RETRY_WAIT_TIME_OFFSET_UNIT)
            # wait for roll down menu displayed
            target = driver.find_element(By.CLASS_NAME, "el-dropdown-menu.el-popper").find_element(By.TAG_NAME, "li")
            logging.debug(f'''target = driver.find_element(By.CLASS_NAME, "el-dropdown-menu.el-popper").find_element(By.TAG_NAME, "li")''')
            time.sleep(self.RETRY_WAIT_TIME_OFFSET_UNIT)
            WebDriverWait(driver, self.DRIVER_IMPLICITY_WAIT_TIME).until(EC.visibility_of(target))
            time.sleep(self.RETRY_WAIT_TIME_OFFSET_UNIT)
            logging.debug(f'''WebDriverWait(driver, self.DRIVER_IMPLICITY_WAIT_TIME).until(EC.visibility_of(target))''')
            WebDriverWait(driver, self.DRIVER_IMPLICITY_WAIT_TIME).until(
                EC.text_to_be_present_in_element((By.XPATH, "//ul[@class='el-dropdown-menu el-popper']/li"), ":"))
            time.sleep(self.RETRY_WAIT_TIME_OFFSET_UNIT)

            # get user id one by one
            userid_elements = driver.find_element(By.CLASS_NAME, "el-dropdown-menu.el-popper").find_elements(By.TAG_NAME, "li")
            userid_list = []
            for element in userid_elements:
                userid_list.append(re.findall("[0-9]+", element.text)[-1])
            return userid_list
        except Exception as e:
            logging.error(
                f"Webdriver quit abnormly, reason: {e}. get user_id list failed.")
            driver.quit()

    def get_daily_electricity_data(self):
        """获取日用电量数据"""
        logging.info(f"Try to get the userid list")
        user_id_list = self._get_user_ids(self.driver)
        logging.info(f"Here are a total of {len(user_id_list)} userids, which are {user_id_list} among which {self.IGNORE_USER_ID} will be ignored.")
        time.sleep(self.RETRY_WAIT_TIME_OFFSET_UNIT)

        result_data = {}
        for userid_index, user_id in enumerate(user_id_list):           
            try: 
                # switch to electricity charge balance page
                self.driver.get(BALANCE_URL) 
                time.sleep(self.RETRY_WAIT_TIME_OFFSET_UNIT)
                self._choose_current_userid(self.driver, userid_index)
                time.sleep(self.RETRY_WAIT_TIME_OFFSET_UNIT)
                current_userid = self._get_current_userid(self.driver)
                if current_userid in self.IGNORE_USER_ID:
                    logging.info(f"The user ID {current_userid} will be ignored in user_id_list")
                    continue

                try:
                    # 点击"日用电量"按钮
                    daily_button = self.driver.find_element(
                        By.XPATH, '//div[contains(text(), "日用电量")]')
                    daily_button.click()
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
                    logging.info(f"成功获取用户{user_id}的用电数据: {json.dumps(data, indent=2, ensure_ascii=False)}")

                except Exception as e:
                    if (userid_index != len(user_id_list) - 1):
                        logging.info(f"用户{user_id}数据获取失败{e}, 将继续处理下一个用户")
                    else:
                        logging.info(f"用户{user_id}数据获取失败{e}")
                    continue

            except Exception as e:
                logging.error(f"处理用户{user_id}时发生错误: {e}")
                continue
        
        return result_data
