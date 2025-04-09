import os
import time
import logging
import re
import base64
import random
import json
import os
from io import BytesIO
from PIL import Image
from datetime import datetime, timedelta

from selenium import webdriver
from selenium.webdriver import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.chrome.service import Service
from dotenv import load_dotenv

# 假设 const.py 和 onnx.py 在同一目录下或已正确配置路径
from .const import LOGIN_URL
from .onnx import ONNX # 导入ONNX类
# 配置日志格式
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('sgcc_electricity_feishu.log'),
        logging.StreamHandler()
    ]
)
# --- Helper function from DataFetcher example ---
def base64_to_PLI(base64_str: str):
    """Converts base64 image string to PIL Image object."""
    try:
        base64_data = re.sub('^data:image/.+;base64,', '', base64_str)
        byte_data = base64.b64decode(base64_data)
        image_data = BytesIO(byte_data)
        img = Image.open(image_data)
        return img
    except Exception as e:
        logging.error(f"转换Base64到PIL图像失败: {e}")
        return None
# --- End Helper function ---

class LoginHelper:
    def __init__(self):
        load_dotenv(verbose=True)
        self.username = os.getenv("USERNAME")
        self.password = os.getenv("PASSWORD")
        if not self.username or not self.password:
            logging.error("请在 .env 文件中设置 USERNAME 和 PASSWORD")
            raise ValueError("未设置用户名或密码")

        self.driver_wait_time = int(os.getenv("DRIVER_IMPLICITY_WAIT_TIME", 60))
        self.retry_wait_time = int(os.getenv("RETRY_WAIT_TIME_OFFSET_UNIT", 10))
        self.retry_limit = int(os.getenv("RETRY_TIMES_LIMIT", 5))

        # 初始化 ONNX 模型
        onnx_model_path = os.getenv("ONNX_MODEL_PATH", "captcha.onnx") # 允许通过环境变量配置路径
        if not os.path.exists(onnx_model_path):
             logging.warning(f"ONNX模型文件未找到: {onnx_model_path}, 将无法处理验证码。请确保文件存在或配置ONNX_MODEL_PATH环境变量。")
             self.onnx = None
        else:
            try:
                self.onnx = ONNX(onnx_model_path)
                logging.info(f"ONNX模型加载成功: {onnx_model_path}")
            except Exception as e:
                logging.error(f"加载ONNX模型失败: {e}")
                self.onnx = None

        # 初始化浏览器驱动
        self.driver = self._init_driver()
        self.login_info_file = "login_info.json"  # 定义存储登录信息的文件名
        self.login_info = self.load_login_info()
        # 尝试使用已保存的登录信息
        if self.login_info and self.is_login_info_valid():
            logging.info("使用已保存的登录信息")
            if self.resume_session():
                logging.info("成功恢复会话")
                return  # 如果会话恢复成功，则无需再次登录
            else:
                logging.warning("恢复会话失败，将重新登录")
                self.login_info = None  # 清除无效的登录信息

    def load_login_info(self):
        """从文件加载登录信息"""
        try:
            logging.info("正在加载登录信息...")
            with open(self.login_info_file, "r") as f:
                return json.load(f)
        except FileNotFoundError:
            logging.info("未找到登录信息文件，将重新登录")
            return None
        except json.JSONDecodeError:
            logging.warning("登录信息文件损坏，将重新登录")
            return None

    def save_login_info(self, login_info):
        """将登录信息保存到文件"""
        try:
            # 打印 JSON 数据
            print("即将保存的登录信息（JSON 格式）:", json.dumps(login_info, indent=4))
            # 确保目录存在
            os.makedirs(os.path.dirname(self.login_info_file), exist_ok=True)
            
            with open(self.login_info_file, "w") as f:
                json.dump(login_info, f, indent=4)
            logging.info(f"登录信息已保存: {login_info}")
        except Exception as e:
            logging.error(f"保存登录信息失败: {e}")
            raise  # 可以考虑抛出异常让调用方处理

    def is_login_info_valid(self):
        """检查登录信息是否有效（例如，检查过期时间）"""
        if self.login_info and "expiration_time" in self.login_info:
            try:
                logging.info("正在检查登录信息是否有效...")
                expiration_time = datetime.fromisoformat(self.login_info["expiration_time"].replace("Z", "+00:00"))
                return expiration_time > datetime.now()
            except ValueError:
                logging.warning("登录信息过期时间格式错误")
                return False
        return False

    def resume_session(self):
        """尝试使用已保存的Cookie恢复会话"""
        if self.login_info and "cookies" in self.login_info:
            try:
                for cookie in self.login_info["cookies"]:
                    if 'expiry' in cookie:
                        cookie['expiry'] = int(cookie['expiry']) # selenium 需要int类型
                    self.driver.add_cookie(cookie)
                self.driver.refresh()  # 刷新页面以应用Cookie
                current_url = self.driver.current_url
                if LOGIN_URL not in current_url:
                    logging.info("成功恢复会话")
                    return True
                else:
                    logging.warning("恢复会话失败，需要重新登录")
                    return False
            except Exception as e:
                logging.error(f"恢复会话失败: {e}")
                return False

    def _init_driver(self):
        """初始化浏览器驱动"""
        chrome_options = webdriver.ChromeOptions()
        # 根据需要取消注释下一行以启用无头模式
        # if os.getenv("DEBUG_MODE", "false").lower() != "true":
        #     chrome_options.add_argument('--headless')
        chrome_options.add_argument('--incognito')
        chrome_options.add_argument('--window-size=1200,800')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--disable-dev-shm-usage')

        # 指定chromedriver路径 (根据用户之前的反馈)
        chromedriver_path = "/Users/zhangchao/Documents/cmd/chromedriver"
        service = Service(executable_path=chromedriver_path)

        try:
            driver = webdriver.Chrome(service=service, options=chrome_options)
            driver.implicitly_wait(self.driver_wait_time)
            logging.info("Chrome驱动初始化成功")
            return driver
        except Exception as e:
            logging.error(f"初始化Chrome驱动失败: {str(e)}")
            raise

    def _click_element(self, by, value, timeout=None):
        """封装点击操作，增加等待和日志"""
        wait_time = timeout if timeout is not None else self.driver_wait_time
        try:
            logging.debug(f"等待点击元素: {by}={value} (超时: {wait_time}s)")
            element = WebDriverWait(self.driver, wait_time).until(
                EC.element_to_be_clickable((by, value))
            )
            logging.debug(f"尝试点击元素: {by}={value}")
            self.driver.execute_script("arguments[0].click();", element)
            logging.debug(f"成功点击元素: {by}={value}")
            time.sleep(0.5 + self.retry_wait_time / 20)
        except Exception as e:
            logging.error(f"点击元素失败: {by}={value}, 错误: {str(e)}")
            raise

    def _input_text(self, by, value, text, timeout=None):
        """封装输入操作，增加等待和日志"""
        wait_time = timeout if timeout is not None else self.driver_wait_time
        try:
            logging.debug(f"等待输入框元素: {by}={value} (超时: {wait_time}s)")
            element = WebDriverWait(self.driver, wait_time).until(
                EC.presence_of_element_located((by, value))
            )
            logging.debug(f"清空并输入文本到: {by}={value}")
            element.clear()
            element.send_keys(text)
            logging.debug(f"成功输入文本到: {by}={value}")
        except Exception as e:
            logging.error(f"输入文本失败: {by}={value}, 错误: {str(e)}")
            raise

    # --- Sliding track method from DataFetcher example ---
    def _sliding_track(self, distance):
        """Simulates human-like sliding track."""
        try:
            # 等待滑块元素出现
            slider = WebDriverWait(self.driver, self.retry_wait_time).until(
                EC.presence_of_element_located((By.CLASS_NAME, "slide-verify-slider-mask-item"))
            )
            logging.info(f"找到滑块元素，准备滑动距离: {distance}")
            ActionChains(self.driver).click_and_hold(slider).perform()
            time.sleep(0.2) # 短暂按住

            # 模拟非匀速滑动轨迹 (简化版，可以根据需要细化)
            current_offset = 0
            while current_offset < distance:
                move = random.randint(10, 25) # 每次移动一小段随机距离
                if current_offset + move > distance:
                    move = distance - current_offset
                
                yoffset_random = random.uniform(-2, 3) # Y轴轻微随机抖动
                ActionChains(self.driver).move_by_offset(xoffset=move, yoffset=yoffset_random).perform()
                current_offset += move
                time.sleep(random.uniform(0.01, 0.05)) # 模拟停顿

            # 微调，确保到达目标位置
            remaining = distance - current_offset
            if remaining > 0:
                 ActionChains(self.driver).move_by_offset(xoffset=remaining, yoffset=random.uniform(-1, 1)).perform()
            
            time.sleep(0.3 + random.uniform(0, 0.2)) # 滑动后稍作停顿
            ActionChains(self.driver).release().perform()
            logging.info("滑块释放")
            return True
        except Exception as e:
            logging.error(f"滑动验证码失败: {e}")
            return False
    # --- End Sliding track method ---

    def _handle_captcha(self):
        """Handles the sliding CAPTCHA."""
        if not self.onnx:
            logging.error("ONNX模型未加载，无法处理验证码。")
            return False

        try:
            # 等待验证码画布出现 (使用ID，更稳定)
            WebDriverWait(self.driver, self.retry_wait_time).until(
                EC.presence_of_element_located((By.ID, "slideVerify"))
            )
            logging.info("检测到滑块验证码容器")
            time.sleep(1) # 等待图片加载

            # 获取背景图片 base64 (参考示例)
            # 注意：JS路径可能需要根据实际页面调整
            background_JS = 'return document.getElementById("slideVerify").childNodes[0].toDataURL("image/png");'
            im_info = self.driver.execute_script(background_JS)
            if not im_info or 'base64' not in im_info:
                 logging.error("获取验证码背景图Base64失败")
                 return False

            background_image = base64_to_PLI(im_info)
            if background_image is None:
                logging.error("转换验证码背景图失败")
                return False
            logging.info("成功获取并转换验证码背景图")

            # 使用 ONNX 模型计算距离
            distance = self.onnx.get_distance(background_image)
            if distance == 0:
                 logging.warning("ONNX模型未能检测到缺口或距离为0")
                 # 可以选择重试或放弃
                 return False # 距离为0通常意味着识别失败

            logging.info(f"ONNX模型计算出的滑动距离: {distance}")

            # 执行滑动操作 (参考示例，补偿系数可调)
            # 补偿系数可能需要根据实际测试调整
            compensation_factor = float(os.getenv("SLIDER_COMPENSATION_FACTOR", 1.06)) 
            actual_distance = round(distance * compensation_factor)
            logging.info(f"应用补偿系数 {compensation_factor} 后，实际滑动距离: {actual_distance}")
            
            if not self._sliding_track(actual_distance):
                return False # 滑动操作本身失败

            time.sleep(self.retry_wait_time / 2) # 滑动后等待验证结果
            return True

        except Exception as e:
            logging.error(f"处理验证码过程中出错: {e}")
            return False

    def login(self):
        """执行登录操作，包含验证码处理"""
        if not self.driver:
            logging.error("浏览器驱动未成功初始化")
            return False

        try:
            self.driver.get(LOGIN_URL)
            logging.info(f"访问登录页面: {LOGIN_URL}")
            time.sleep(self.retry_wait_time / 2)

            logging.info("查找并点击 'user' 切换按钮")
            self._click_element(By.CLASS_NAME, "user")
            logging.info("查找并点击切换到密码登录的 span")
            self._click_element(By.XPATH, '//*[@id="login_box"]/div[1]/div[1]/div[2]/span')
            time.sleep(self.retry_wait_time / 5)

            logging.info("查找并点击同意选项")
            self._click_element(By.XPATH, '//*[@id="login_box"]/div[2]/div[1]/form/div[1]/div[3]/div/span[2]')
            time.sleep(self.retry_wait_time / 5)

            # 移除 phone_code 相关逻辑块
            # 用户名密码登录逻辑 (现在是默认且唯一的逻辑)
            logging.info("用户名密码登录模式...")
            logging.info("输入用户名...")
            self._input_text(By.XPATH, '//input[@placeholder="请输入用户名/手机号/邮箱"]', self.username)
            logging.info("输入密码...")
            self._input_text(By.XPATH, '//input[@placeholder="请输入密码"]', self.password)

            logging.info("点击登录按钮...")
            self._click_element(By.CLASS_NAME, "el-button--primary")
            time.sleep(self.retry_wait_time / 2) # 等待验证码或跳转

            # --- 验证码处理循环 ---
            for attempt in range(1, self.retry_limit + 1):
                logging.info(f"检查是否需要验证码 (尝试次数: {attempt}/{self.retry_limit})")
                
                # 检查是否已登录成功 (URL变化)
                current_url = self.driver.current_url
                if LOGIN_URL not in current_url:
                    logging.info("登录成功 (URL已改变)")
                    return True

                # 检查是否出现验证码 (通过ID查找容器)
                try:
                    captcha_container = self.driver.find_element(By.ID, "slideVerify")
                    if captcha_container.is_displayed():
                        logging.info("检测到滑块验证码，开始处理...")
                        if self._handle_captcha():
                            # 处理成功后，再次检查登录状态
                            time.sleep(self.retry_wait_time / 2)
                            current_url = self.driver.current_url
                            if LOGIN_URL not in current_url:
                                logging.info("验证码处理后登录成功 (URL已改变)")
                                return True
                            else:
                                    logging.warning("验证码处理后URL未改变，可能验证失败，继续重试...")
                                    # 可能需要刷新验证码或重新点击登录按钮
                                    try:
                                        # 尝试刷新验证码（如果页面提供刷新按钮）
                                        refresh_button = self.driver.find_element(By.XPATH, "//*[contains(@class, 'refresh') or contains(@class, 'reload')]") # 假设的刷新按钮选择器
                                        if refresh_button.is_displayed():
                                            self._click_element(By.XPATH, "//*[contains(@class, 'refresh') or contains(@class, 'reload')]")
                                            logging.info("尝试刷新验证码")
                                            time.sleep(1)
                                        else:
                                            # 如果没有刷新按钮，可能需要重新点击登录触发新的验证码
                                            logging.info("未找到刷新按钮，尝试重新点击登录按钮触发新验证码")
                                            self._click_element(By.CLASS_NAME, "el-button--primary")
                                            time.sleep(self.retry_wait_time / 2)

                                    except:
                                        logging.warning("刷新验证码或重新点击登录失败，继续等待或下次重试")
                                        time.sleep(self.retry_wait_time) # 等待一段时间再试

                        else:
                            logging.error("验证码处理失败，继续重试...")
                            # 处理失败后也可能需要刷新或重新点击登录
                            try:
                                    refresh_button = self.driver.find_element(By.XPATH, "//*[contains(@class, 'refresh') or contains(@class, 'reload')]")
                                    if refresh_button.is_displayed():
                                        self._click_element(By.XPATH, "//*[contains(@class, 'refresh') or contains(@class, 'reload')]")
                                        logging.info("尝试刷新验证码")
                                        time.sleep(1)
                                    else:
                                        logging.info("未找到刷新按钮，尝试重新点击登录按钮触发新验证码")
                                        self._click_element(By.CLASS_NAME, "el-button--primary")
                                        time.sleep(self.retry_wait_time / 2)
                            except:
                                    logging.warning("刷新验证码或重新点击登录失败，继续等待或下次重试")
                                    time.sleep(self.retry_wait_time)

                    else:
                        # 没有验证码，但URL没变，可能是其他错误
                        logging.warning("未检测到验证码，但登录URL未改变，等待重试...")
                        time.sleep(self.retry_wait_time)

                except Exception as find_captcha_e:
                    # 没找到验证码容器，可能已登录或页面结构变化
                    logging.info(f"未找到验证码容器 (可能已登录或页面结构变化): {find_captcha_e}")
                    # 再次检查URL
                    current_url = self.driver.current_url
                    if LOGIN_URL not in current_url:
                        logging.info("登录成功 (URL已改变)")
                        return True
                    else:
                        logging.warning("未找到验证码且URL未变，等待重试...")
                        time.sleep(self.retry_wait_time)

            # 如果循环结束仍未成功
            logging.error(f"尝试 {self.retry_limit} 次后登录仍失败")
            return False
            # 移除 phone_code 相关的检查块

        except Exception as e:
            logging.error(f"登录过程中发生严重错误: {str(e)}")
            return False
    
    def wrapped_login(self):
        """包裹 login 方法，实现登录成功后保存 Cookies"""
        if self.login():
            login_data = {
                "cookies": self.driver.get_cookies(),
                "expiration_time": str(datetime.now() + timedelta(days=1))
            }
            self.save_login_info(login_data)
            return True
        else:
            return False

    def close(self):
        """关闭浏览器"""
        if self.driver:
            self.driver.quit()
            logging.info("浏览器已关闭")
