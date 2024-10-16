import time
import tomllib
from typing import List, Optional, Union

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select
import undetected_chromedriver as uc

driver = None

def get_driver(browser: str) -> Union[webdriver.Firefox, webdriver.Chrome]:
    if browser.lower() == "firefox":
        driver = webdriver.Firefox()

    elif browser.lower() == "chrome":
        driver = uc.Chrome()

    else:
        raise ValueError("Unsupported browser was selected")

    return driver


def get_day_element(driver: WebDriver, day: str) -> WebElement:
    if day == "Day 1":
        elem = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.LINK_TEXT, "＜Day.1＞お申込み"))
        )

    elif day == "Day 2":
        elem = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.LINK_TEXT, "＜Day.2＞お申込み"))
        )
    return elem


def apply_for_single_day(
    driver: WebDriver, ballot_day: str, code: str, **kwargs
) -> None:
    day = get_day_element(driver, ballot_day)
    print(f"Applying to {ballot_day}")
    day.click()
    WebDriverWait(driver, 10).until(
        EC.all_of(
            EC.presence_of_element_located(
                (By.XPATH, "//input[@type='text' and @placeholder='シリアルナンバー']")
            ),
            EC.element_to_be_clickable((By.XPATH, "//button[text()='お申込みへ']")),
        )
    )
    serial_code_box = driver.find_element(
        By.XPATH, "//input[@type='text' and @placeholder='シリアルナンバー']"
    )

    print("Filling code")
    serial_code_box.send_keys(code)

    apply_button = driver.find_element(By.XPATH, "//button[text()='お申込みへ']")
    apply_button.click()

    WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable(
            (
                By.XPATH,
                "//button[text()='申込む' and @data-title='★ 必ずお読みください ★']",
            )
        ),
    )

    apply_button = WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable(
            (
                By.XPATH,
                "//button[text()='申込む' and @data-title='★ 必ずお読みください ★']",
            )
        )
    )
    apply_button.click()

    checkbox = WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable(
            (By.XPATH, "//label[text()='各種注意事項に同意します']")
        )
    )
    checkbox.click()

    apply_button = WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable(
            (By.XPATH, "//button[text()='申込みへ' and @type='submit']")
        )
    )
    apply_button.click()


def login(driver: WebDriver, username: str, password: str) -> None:
    login_button = WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable(
            (By.XPATH, "//span[@id='login-bt']/a[text()='ログイン画面へ']")
        )
    )
    login_button.click()

    username_form = WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable(
            (
                By.XPATH,
                "//input[@id='loginId' and @class='inputType01']",
            )
        )
    )
    username_form.send_keys(username)

    password_form = WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable(
            (
                By.XPATH,
                "//input[@id='loginPassword' and @class='inputType01 passwordInput']",
            )
        )
    )
    password_form.send_keys(password)

    login_button = WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable(
            (
                By.XPATH,
                "//button[@id='idPwLogin' and @type='submit']",
            )
        )
    )

    login_button.click()


def ballot_with_goods(
    driver: WebDriver, with_goods: bool = False, is_pair: bool = False
) -> None:
    if with_goods:
        box_text = "グッズ付き　-----"
    else:
        box_text = "グッズなし　-----"

    ticket_option = WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable(
            (By.XPATH, f"//tr/td[3]//select[option[text()='{box_text}']]")
        )
    )
    ticket_select = Select(ticket_option)
    ticket_select.select_by_index(is_pair + 1)


def ballot_without_goods(driver: WebDriver, is_pair: bool = False) -> None:
    ticket_option = WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable((By.XPATH, "//tr/td[3]//select"))
    )

    ticket_select = Select(ticket_option)
    ticket_select.select_by_index(is_pair + 1)


def get_number_of_selects(driver: WebDriver) -> int:
    ballot_element = driver.find_element(
        By.XPATH, "//div[@class='select-area']//tr/td[3]"
    )

    select_elements = ballot_element.find_elements(By.TAG_NAME, "select")
    return len(select_elements)


def fill_ballot_info(driver: WebDriver, with_goods: bool, is_pair: bool) -> None:
    day_option = WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable(
            (By.XPATH, "//tr/td[2]//select[option[text()='選択して下さい']]")
        )
    )
    day_select = Select(day_option)
    day_select.select_by_index(1)

    num_selects = get_number_of_selects(driver)

    if num_selects == 2:
        ballot_with_goods(driver, with_goods, is_pair)
    else:
        ballot_without_goods(driver, is_pair)

    submit_button = WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable(
            (By.XPATH, "//span[@id='enter-bt-zumi']/a[text()='申込み']")
        )
    )
    submit_button.click()


def fill_payment_info(driver: WebDriver) -> None:
    conbini_option = WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable(
            (By.XPATH, "//div[@class='con']//input[@type='radio']")
        )
    )

    conbini_option.click()

    submit_button = WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable(
            (By.XPATH, "//span[@class='enter-bt']//*/a[text()='次へ']")
        )
    )
    submit_button.click()


def has_goods_ballot(driver: WebDriver) -> bool:
    try:
        WebDriverWait(driver, 10).until(
            EC.visibility_of_element_located((By.XPATH, "//div[@class='enq-info']"))
        )
        return True
    except:
        return False


def fill_goods_info(
    driver: WebDriver,
    with_goods: bool = False,
    shipping_info: Optional[List[str]] = None,
) -> None:
    body = driver.find_element(
        By.XPATH, "//div[@class='enq-info']//div[@class='cont-block']"
    )
    forms = body.find_elements(By.XPATH, "//fieldset")

    for idx, form in enumerate(forms):
        if idx == 0:
            # If with_goods is true we need to click the 0th button
            # which is the "I verifed"
            form.find_elements(By.TAG_NAME, "input")[not with_goods].click()
        if idx == 1:
            # If with_goods is true we need to click the 1st button
            # which is the "I didn't verify"
            form.find_elements(By.TAG_NAME, "input")[with_goods].click()

        if idx == 3 or idx == 4:
            # We are at the half width form
            inp = form.find_element(By.TAG_NAME, "input")
            if not shipping_info:
                inp.send_keys("0")
            else:
                inp.send_keys(shipping_info[idx - 2])

        else:
            # We are at any other form which needs to be filled with full-width 0
            inp = form.find_element(By.TAG_NAME, "input")
            if not shipping_info:
                inp.send_keys("０")
            else:
                inp.send_keys(shipping_info[idx - 2])


def fill_renban_info(driver: WebDriver, renban: Union[Dict[str, str], int]) -> None:
    renban_form = WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable(
            (By.XPATH, "//tr/td[2]//select[option[text()='同行者1を選択してください']]")
        )
    )

    select_renban = Select(renban_form)
    if isinstance(renban, int):
        select_renban.select_by_index(renban_id)
    elif isinstance(renban, dict) and len(renban) == 2:
        renban_name = f"{name}（{address}）".format(name=renban["name"], address=renban["address"])
        for option in select_renban.options:
            if option.text == renban_name:
                option.click()

    else:
        raise ValueError("Renban value is invalid, please either specify a number or a dictionary of two elements with name and address")



def start_single_ballot_process(
    driver: WebDriver, entry_url: str, **ballot_info
) -> None:
    available_codes = ballot_info["Codes"]
    day = ballot_info["Days"]
    pair = ballot_info.get("Pair", False)
    goods = ballot_info.get("Goods", False)
    shipping_info = ballot_info.get("Shipping Info", None)
    while available_codes:
        code = available_codes.pop()
        print(f"Applying with code: {code}")

        for ballot_day in ["Day 1", "Day 2"]:
            if day == ballot_day or day == "Both":
                driver.get(entry_url)
                apply_for_single_day(driver, ballot_day, code, **ballot_info)

                login(
                    driver,
                    ballot_info["Credentials"]["username"],
                    ballot_info["Credentials"]["password"],
                )

                fill_ballot_info(driver, goods, pair)
                fill_payment_info(driver)
                if pair:
                    fill_renban_info(driver, ballot_info["Renban"])

                if has_goods_ballot(driver):
                    fill_goods_info(driver, goods, shipping_info)

                red_attention = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable(
                        (
                            By.XPATH,
                            "//td[@class='checkbox-area']//label[text()='内容を確認しました']",
                        )
                    )
                )

                red_attention.find_element(
                    By.XPATH, "//input[@type='checkbox']"
                ).click()

                submit_button = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable(
                        (
                            By.XPATH,
                            "//span[id='apply-button-area']//*/a[text()='同意して申込み']",
                        )
                    )
                )
                submit_button.click()


def main() -> None:
    with open("config.toml", "rb") as fd:
        config = tomllib.load(fd)

    global driver
    driver = get_driver(config["Browser"])

    for ballot_info in config["Ballots"]:
        start_single_ballot_process(driver, config["URL"], **ballot_info)

    driver.close()


if __name__ == "__main__":
    main()
