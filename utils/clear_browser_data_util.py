from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

## Helpers
def wait_for_element(driver, selector, timeout=5):
    return WebDriverWait(driver, timeout).until(
        lambda d: d.execute_script(f"return document.querySelector('{selector}')")
    )

def wait_for_elements(driver, selector, timeout=5):
    return WebDriverWait(driver, timeout).until(
        lambda d: d.execute_script(f"return document.querySelectorAll('{selector}')")
    )

def wait_for_shadow_element_deep(driver, selectors, timeout=5):
    element = None
    for selector in selectors:
        element = WebDriverWait(driver, timeout).until(
            lambda d: d.execute_script(
                "return arguments[0] ? arguments[0].shadowRoot.querySelector(arguments[1]) : document.querySelector(arguments[1])", 
                element, selector
            )
        )
    return element

def wait_for_input_value(driver, element, input_text, timeout=5):
    WebDriverWait(driver,timeout).until(
        lambda d: d.execute_script("return arguments[0].value == arguments[1];", element, input_text)
    )

### Clear browser data Methods:
# Clear History data for Tor and Firefox
def firefox_clear_browser_data(driver):
    driver.get('about:preferences#privacy')
    # click on clear history button
    WebDriverWait(driver, 5).until(EC.element_to_be_clickable((driver.execute_script("return document.getElementById('clearHistoryButton')")))).click()
    # select all checkboxes (we click instead of doing checked=true to enable Clear button!)
    WebDriverWait(driver,5).until(EC.visibility_of(driver.execute_script("return document.getElementsByClassName('dialogFrame')[0];")))
    driver.execute_script("return document.getElementsByClassName('dialogFrame')[0].contentDocument.querySelectorAll('checkbox').forEach(box => !box.checked && box.click())")
    # click Clear Now
    driver.execute_script("return document.getElementsByClassName('dialogFrame')[0].contentDocument.querySelector('dialog').shadowRoot.getElementsByAttribute('label', 'Clear Now')[0].click()")

# Clear Browser Data for Chrome and Brave
def chrome_clear_browser_data(driver):
    # Go to clear browser data page
    driver.get("chrome://settings/clearBrowserData")
    # Wait for the dialog to open
    clear_browsing_data_dialog = wait_for_shadow_element_deep(driver, ["settings-ui", "#main", "settings-basic-page", "#basicPage > settings-section:nth-child(11) > settings-privacy-page", "settings-clear-browsing-data-dialog"])
    # Wait for advanced tab and click it
    advanced_tab = wait_for_shadow_element_deep(driver, ["settings-ui", "#main", "settings-basic-page", "#basicPage > settings-section:nth-child(11) > settings-privacy-page", "settings-clear-browsing-data-dialog", "#clearBrowsingDataDialog > div:nth-child(2) > cr-tabs", "div:nth-child(4)"])
    WebDriverWait(driver, 5).until(EC.element_to_be_clickable(advanced_tab)).click()
    # Get all checkboxes
    checkboxes = driver.execute_script(
        "return arguments[0].shadowRoot.querySelectorAll('settings-checkbox')", 
        clear_browsing_data_dialog
    )
    # Check all unchecked checkboxes
    for checkbox in checkboxes:
        driver.execute_script(
            "if (!arguments[0].shadowRoot.querySelector('cr-checkbox').checked) { arguments[0].shadowRoot.querySelector('cr-checkbox').click(); }", 
            checkbox
        )
    # Get the clear button
    clear_button = driver.execute_script(
        "return arguments[0].shadowRoot.querySelector('#clearBrowsingDataConfirm')", 
        clear_browsing_data_dialog
    )
    # Click the clear button
    WebDriverWait(driver, 5).until(EC.element_to_be_clickable(clear_button)).click()

def brave_clear_browser_data(driver):
    # Go to clear browser data page
    driver.get("brave://settings/clearBrowserData")
    # Wait for the dialog to open
    clear_browsing_data_dialog = wait_for_shadow_element_deep(driver, ["settings-ui", "#main", "settings-basic-page", "#basicPage > settings-section:nth-child(19) > settings-privacy-page", "settings-clear-browsing-data-dialog"])
    # Wait for advanced tab and click it
    advanced_tab = wait_for_shadow_element_deep(driver, ["settings-ui", "#main", "settings-basic-page", "#basicPage > settings-section:nth-child(19) > settings-privacy-page", "settings-clear-browsing-data-dialog", "#clearBrowsingDataDialog > div:nth-child(2) > cr-tabs", "div:nth-child(4)"])
    WebDriverWait(driver, 5).until(EC.element_to_be_clickable(advanced_tab)).click()
    # Get all checkboxes
    checkboxes = driver.execute_script(
        "return arguments[0].shadowRoot.querySelectorAll('settings-checkbox')", 
        clear_browsing_data_dialog
    )
    # Check all unchecked checkboxes
    for checkbox in checkboxes:
        driver.execute_script(
            "if (!arguments[0].shadowRoot.querySelector('cr-checkbox').checked) { arguments[0].shadowRoot.querySelector('cr-checkbox').click(); }", 
            checkbox
        )
    # Get the clear button
    clear_button = driver.execute_script(
        "return arguments[0].shadowRoot.querySelector('#clearBrowsingDataConfirm')", 
        clear_browsing_data_dialog
    )
    # Click the clear button
    WebDriverWait(driver, 5).until(EC.element_to_be_clickable(clear_button)).click()

def edge_clear_browser_data(driver):
    # Go to clear browser data page
    driver.get("edge://settings/clearBrowserData")
    # Sometimes it shows a blank page, so refresh to show the desired page
    # driver.refresh()
    # Get all checkboxes
    checkboxes = wait_for_elements(driver, "input[id^=\"settings-checkbox-input-\"]")
    # Check all unchecked checkboxes
    for checkbox in checkboxes:
        driver.execute_script(
            "if (!arguments[0].checked) { arguments[0].click(); }", 
            checkbox
        )
    # Get the clear button
    clear_button = wait_for_element(driver, "#clear-now")
    # Click the clear button
    WebDriverWait(driver, 5).until(EC.element_to_be_clickable(clear_button)).click()

def opera_clear_browser_data(driver):
    # Go to clear browser data page
    driver.get("opera://settings/clearBrowserData")
    # Wait for the dialog to open
    clear_browsing_data_dialog = wait_for_shadow_element_deep(driver, ["main-view", "settings-ui", "#main", "settings-basic-page", "#basicPage > settings-section:nth-child(8) > settings-privacy-page", "settings-clear-browsing-data-dialog"])
    # Wait for the advanced tab and click it
    advanced_tab = wait_for_shadow_element_deep(driver, ["main-view", "settings-ui", "#main", "settings-basic-page", "#basicPage > settings-section:nth-child(8) > settings-privacy-page", "settings-clear-browsing-data-dialog", "cr-tabs", "div:nth-child(4)"])
    WebDriverWait(driver, 5).until(EC.element_to_be_clickable(advanced_tab)).click()
    # Get all checkboxes
    checkboxes = driver.execute_script(
        "return arguments[0].shadowRoot.querySelectorAll('settings-checkbox')", 
        clear_browsing_data_dialog
    )
    # Check all unchecked checkboxes
    for checkbox in checkboxes:
        driver.execute_script(
            "if (!arguments[0].shadowRoot.querySelector('cr-checkbox').checked) { arguments[0].shadowRoot.querySelector('cr-checkbox').click(); }", 
            checkbox
        )
    # Get the clear button
    clear_button = driver.execute_script(
        "return arguments[0].shadowRoot.querySelector('#clearBrowsingDataConfirm')", 
        clear_browsing_data_dialog
    )
    # Click the clear button
    WebDriverWait(driver, 5).until(EC.element_to_be_clickable(clear_button)).click()
