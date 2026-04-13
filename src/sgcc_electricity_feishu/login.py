import os
import time
import logging
import re
import base64
import random
import json
from io import BytesIO
from PIL import Image
from datetime import datetime, timedelta, timezone

from selenium import webdriver
from selenium.webdriver import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.chrome.service import Service
from dotenv import load_dotenv

# 假设 const.py 和 onnx.py 在同一目录下或已正确配置路径
from .electricity_data import ElectricityDataFetcher
from .const import LOGIN_URL, LOGIN_INFO_FILE
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
        self.chromedriver_path = os.getenv("CHROMEDRIVER_PATH")
        if not self.chromedriver_path:
            self.chromedriver_path = "/usr/bin/chromedriver"
            logging.warning("使用默认位置，如开发，请在 .env 文件中设置 CHROMEDRIVER_PATH")
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
        # 定义存储登录信息的文件路径（项目根目录下）
        self.login_info = self.load_login_info()

    def load_login_info(self):
        """从文件加载登录信息"""
        try:
            logging.info("正在加载登录信息...")
            with open(LOGIN_INFO_FILE, "r") as f:
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
            # 尝试获取 localStorage 和 sessionStorage
            try:
                login_info["localStorage"] = self.driver.execute_script(
                    "return Object.keys(localStorage).reduce((acc, key) => ({...acc, [key]: localStorage.getItem(key)}), {});"
                )
            except Exception as e:
                logging.warning(f"获取localStorage失败: {e}")
                login_info["localStorage"] = {}
            
            try:
                login_info["sessionStorage"] = self.driver.execute_script(
                    "return Object.keys(sessionStorage).reduce((acc, key) => ({...acc, [key]: sessionStorage.getItem(key)}), {});"
                )
            except Exception as e:
                logging.warning(f"获取sessionStorage失败: {e}")
                login_info["sessionStorage"] = {}
            
            with open(LOGIN_INFO_FILE, "w") as f:
                json.dump(login_info, f, indent=4)
        except Exception as e:
            logging.error(f"保存登录信息失败: {e}")
            # 不再抛出异常，仅记录错误

    def is_login_info_valid(self):
        """检查登录信息是否有效（例如，检查过期时间）"""
        if self.login_info and "expiration_time" in self.login_info:
            try:
                logging.info("正在检查登录信息是否有效...")
                expiration_time = datetime.fromisoformat(self.login_info["expiration_time"].replace("Z", "+00:00"))
                expiration_ts = expiration_time.timestamp()  # 转为时间戳
                now_ts = datetime.now(timezone.utc).timestamp()  # 当前时间戳
                logging.info(f"登录信息过期时间: {expiration_ts}")
                logging.info(f"当前时间: {now_ts}")
                return expiration_ts > now_ts  # 直接比较即可
            except ValueError:
                logging.warning("登录信息过期时间格式错误")
                return False
        return False

    def resume_session(self):
        """尝试使用已保存的Cookie和Storage恢复会话"""
        if not self.login_info:
            return False
            
        try:
            # 先访问目标域名以设置cookie和storage
            self.driver.get("https://www.95598.cn")
            
            # 恢复cookies
            if "cookies" in self.login_info:
                for cookie in self.login_info["cookies"]:
                    try:
                        cookie_dict = {
                            'name': cookie['name'],
                            'value': cookie['value'],
                            'domain': cookie.get('domain', 'www.95598.cn'),
                            'path': cookie.get('path', '/'),
                            'secure': cookie.get('secure', False),
                            'httpOnly': cookie.get('httpOnly', False)
                        }
                        if 'expiry' in cookie:
                            cookie_dict['expiry'] = int(cookie['expiry'])
                        if 'sameSite' in cookie:
                            cookie_dict['sameSite'] = cookie['sameSite']
                        self.driver.add_cookie(cookie_dict)
                    except Exception as e:
                        logging.warning(f"添加cookie {cookie.get('name')} 失败: {e}")

            # 恢复localStorage
            if "localStorage" in self.login_info:
                for key, value in self.login_info["localStorage"].items():
                    try:
                        self.driver.execute_script(f"window.localStorage.setItem('{key}', '{value}');")
                    except Exception as e:
                        logging.warning(f"恢复localStorage {key} 失败: {e}")

            # 恢复sessionStorage
            if "sessionStorage" in self.login_info:
                for key, value in self.login_info["sessionStorage"].items():
                    try:
                        self.driver.execute_script(f"window.sessionStorage.setItem('{key}', '{value}');")
                    except Exception as e:
                        logging.warning(f"恢复sessionStorage {key} 失败: {e}")

            # 跳转到目标页面验证登录状态
            self.driver.get("https://www.95598.cn/osgweb/electricityCharge")
            time.sleep(2)  # 等待页面加载
            
            # 检查是否在目标页面
            if "electricityCharge" in self.driver.current_url:
                logging.info("成功恢复会话并跳转到目标页面")
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
        # chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--start-maximized")

        # 反爬虫检测
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_experimental_option('excludeSwitches', ['enable-automation'])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        chrome_options.add_argument(
            'user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
            '(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36')

        chromedriver_path = self.chromedriver_path
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

    def _sliding_track(self, distance):
        """模拟人类滑动轨迹：加速 → 匀速 → 减速 → 微回弹"""
        try:
            slider = WebDriverWait(self.driver, self.retry_wait_time).until(
                EC.presence_of_element_located((By.CLASS_NAME, "slide-verify-slider-mask-item"))
            )
            logging.info(f"找到滑块元素，准备滑动距离: {distance}")
            ActionChains(self.driver).click_and_hold(slider).perform()

            moved = 0
            accel_end = distance * 0.4
            cruise_end = distance * 0.8

            while moved < distance:
                remaining = distance - moved
                if moved < accel_end:
                    step = random.randint(8, 16)
                    delay = random.uniform(0.005, 0.02)
                elif moved < cruise_end:
                    step = random.randint(4, 10)
                    delay = random.uniform(0.01, 0.03)
                else:
                    step = random.randint(1, 4)
                    delay = random.uniform(0.02, 0.06)

                step = min(step, remaining)
                y_jitter = random.uniform(-1, 1)
                ActionChains(self.driver).move_by_offset(xoffset=step, yoffset=y_jitter).perform()
                moved += step
                time.sleep(delay)

            # 微回弹，模拟真实滑动后的松手
            rebound = random.randint(1, 3)
            ActionChains(self.driver).move_by_offset(xoffset=-rebound, yoffset=0).perform()
            time.sleep(random.uniform(0.05, 0.15))
            ActionChains(self.driver).release().perform()
            logging.info("滑块释放")
            return True
        except Exception as e:
            logging.error(f"滑动验证码失败: {e}")
            return False

    def _handle_captcha(self):
        """处理滑块验证码，使用 ONNX 模型识别缺口并计算正确的滑动距离"""
        if not self.onnx:
            logging.error("ONNX模型未加载，无法处理验证码。")
            return False

        try:
            WebDriverWait(self.driver, self.retry_wait_time).until(
                EC.presence_of_element_located((By.ID, "slideVerify"))
            )
            logging.info("检测到滑块验证码容器")
            time.sleep(1)

            # 获取背景图片
            background_JS = 'return document.getElementById("slideVerify").childNodes[0].toDataURL("image/png");'
            im_info = self.driver.execute_script(background_JS)
            if not im_info or 'base64' not in im_info:
                logging.error("获取验证码背景图Base64失败")
                return False

            background = im_info.split(',')[1]
            background_image = base64_to_PLI(background)
            if background_image is None:
                logging.error("转换验证码背景图失败")
                return False
            logging.info("成功获取验证码背景图")

            # 使用 ONNX 模型计算距离
            distance = self.onnx.get_distance(background_image)
            if distance == 0:
                logging.warning("ONNX模型未能检测到缺口")
                return False

            # ONNX 模型在 416x416 空间检测，缩放到实际画布宽度
            canvas_width = self.driver.execute_script(
                'return document.getElementById("slideVerify").childNodes[0].width;'
            )
            scale = canvas_width / 416.0
            img_distance = distance * scale

            # 滑块滑动和图片空缺的移动不一致
            max_sliding = 410 - 40  # 滑块最多可以滑动的距离
            img_max_sliding = 418 - 68  # 图片最多可以滑动的距离
            sliding_scale = max_sliding / img_max_sliding
            scaled_distance = round(img_distance * sliding_scale)

            logging.info(
                f"验证码距离: distance={distance}, img_distance={img_distance:.3f}, "
                f"canvas_width={canvas_width}, scale={scale:.3f}, "
                f"sliding_scale={sliding_scale:.3f}, scaled={scaled_distance}"
            )

            if not self._sliding_track(scaled_distance):
                return False

            time.sleep(self.retry_wait_time / 2)
            return True

        except Exception as e:
            logging.error(f"处理验证码过程中出错: {e}")
            return False

    def _get_error_message(self):
        """获取页面错误信息"""
        self.driver.implicitly_wait(0)
        try:
            element = self.driver.find_element(By.XPATH, "//div[@class='errmsg-tip']//span")
            return element.text
        except Exception:
            return None
        finally:
            self.driver.implicitly_wait(self.driver_wait_time)

    def login(self):
        """执行登录操作，包含验证码处理"""
        if not self.driver:
            logging.error("浏览器驱动未成功初始化")
            return False

        try:
            self.driver.get(LOGIN_URL)
            logging.info(f"访问登录页面: {LOGIN_URL}")

            # 等待页面加载
            try:
                WebDriverWait(self.driver, self.driver_wait_time * 3).until(
                    EC.visibility_of_element_located((By.CLASS_NAME, "user")))
            except Exception:
                logging.debug("登录页面加载超时")

            time.sleep(self.retry_wait_time)

            # 等待加载遮罩消失
            self.driver.implicitly_wait(0)
            try:
                WebDriverWait(self.driver, 10).until(
                    EC.invisibility_of_element_located((By.CLASS_NAME, 'el-loading-mask')))
            finally:
                self.driver.implicitly_wait(self.driver_wait_time)

            # 切换到用户名密码登录
            element = WebDriverWait(self.driver, self.driver_wait_time).until(
                EC.presence_of_element_located((By.CLASS_NAME, 'user')))
            self.driver.execute_script("arguments[0].click();", element)
            logging.info("切换到用户名密码登录")

            self._click_element(By.XPATH, '//*[@id="login_box"]/div[1]/div[1]/div[2]/span')
            time.sleep(self.retry_wait_time)

            # 点击同意按钮
            self._click_element(By.XPATH, '//*[@id="login_box"]/div[2]/div[1]/form/div[1]/div[3]/div/span[2]')
            logging.info("点击同意按钮")
            time.sleep(self.retry_wait_time)

            # 输入用户名和密码
            input_elements = self.driver.find_elements(By.CLASS_NAME, "el-input__inner")
            input_elements[0].send_keys(self.username)
            logging.info(f"输入用户名: {self.username}")
            input_elements[1].send_keys(self.password)
            logging.info("输入密码")

            # 点击登录按钮
            self._click_element(By.CLASS_NAME, "el-button.el-button--primary")
            time.sleep(self.retry_wait_time * 2)
            logging.info("点击登录按钮")

            # 验证码处理循环
            for attempt in range(1, self.retry_limit + 1):
                logging.info(f"验证码处理 (尝试 {attempt}/{self.retry_limit})")

                # 检查是否已登录成功
                if LOGIN_URL not in self.driver.current_url:
                    logging.info("登录成功")
                    return True

                # 处理验证码
                if not self._handle_captcha():
                    logging.warning("验证码处理失败")
                    try:
                        self._click_element(By.CLASS_NAME, "el-button.el-button--primary")
                        time.sleep(self.retry_wait_time * 2)
                    except Exception:
                        pass
                    continue

                time.sleep(self.retry_wait_time)

                # 检查是否登录成功
                if LOGIN_URL not in self.driver.current_url:
                    logging.info("验证码验证成功，登录完成")
                    return True

                # 获取错误信息
                error_msg = self._get_error_message()
                if error_msg:
                    logging.info(f"滑块验证失败 [{error_msg}]，重新尝试")
                else:
                    logging.info("滑块验证失败，重新尝试")

                # 重新点击登录按钮触发新验证码
                try:
                    self._click_element(By.CLASS_NAME, "el-button.el-button--primary")
                    time.sleep(self.retry_wait_time * 2)
                except Exception:
                    pass

            logging.error(f"尝试 {self.retry_limit} 次后登录仍失败")
            return False

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

    def fetch_data(self):
        """获取用电量数据"""
        try:
            # 尝试使用已保存的登录信息
            if self.login_info and self.is_login_info_valid():
                logging.info("使用已保存的登录信息")
                self.resume_session()
            else:
                self.wrapped_login()
            # 跳转到电费查询页面
            self.driver.get("https://www.95598.cn/osgweb/electricityCharge")
            time.sleep(3)  # 等待页面加载
            # 检查并点击指定按钮
            # try:
            #     button = self.driver.find_element(
            #         By.XPATH, '//*[@id="app"]/div/div[2]/div/div/div/div[2]/div[2]/div/button')
            #     button.click()
            #     time.sleep(1)
            # except:
            #     logging.warning("未找到指定按钮，可能已自动展开")
            
            # 使用ElectricityDataFetcher获取用电数据
            data_fetcher = ElectricityDataFetcher(self.driver)
            data = data_fetcher.get_daily_electricity_data()
            logging.info(data)
            return data
            
        except Exception as e:
            logging.error(f"获取用电数据失败: {e}")
            raise

    def close(self):
        """关闭浏览器"""
        if self.driver:
            self.driver.quit()
            logging.info("浏览器已关闭")
