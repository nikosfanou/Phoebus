from utils.utility import extract_log_msg

'''
Arguments:
driver                := The Selenium WebDriver instance controlling the browser.
url_extension         := The path of the test file returned by the tester, including some query parameters (e.g., /test1.php?browser=Firefox&deployment_id=1).
mechanisms_per_domain := A dictionary mapping domains to the mechanisms and mechanism values that are applied for each domain.
setup_info            := A dictionary containing information about the domains and their corresponding IP addresses used in this tester instance. It also includes the currently active testing domain (setup_info['testing_domain']).
logger                := Logger used to record important information during browser execution (info, warning, error, exception, critical).
semaphore             := A semaphore used to coordinate browser actions when ordering is required. It supports the acquire() and release() methods to lock and unlock execution.
'''
def test_method(driver, url_extension, mechanisms_per_domain, setup_info, logger, semaphore):
    try:
        driver.set_page_load_timeout(25) # should load under 25 sec, else timeout
    except Exception as e:
        logger.error(f"Attempt to change the page load timeout failed!")
        log_msg = extract_log_msg(exception=e)
        logger.error(log_msg)

    url = f"http://{setup_info['testing_domain']}" + url_extension
    try:
        driver.get(url) # visit the test page
    except Exception as e:
        logger.error(f'driver.get("{url}") failed')
        log_msg = extract_log_msg(exception=e)
        logger.exception(log_msg)
        return {}

    # This JS code waits for all the images in the document to load or timeout, and then stores their status ('timeout' / 'loaded' / 'blocked')
    results = driver.execute_async_script("""
        const callback = arguments[arguments.length - 1];

        const images = [...document.images];

        const promises = images.map(img => {
            if (img.complete) {
                return Promise.resolve();
            }

            return new Promise(resolve => {
                img.addEventListener('load', resolve, { once: true });
                img.addEventListener('error', resolve, { once: true });
                setTimeout(resolve, 10000);
            });
        });

        Promise.all(promises).then(() => {
            const results = {};

            for (const img of images) {
                if (!img.id) {
                    continue;
                }
                
                if (!img.complete) {
                    results[img.id] = 'timeout';
                } else {
                    results[img.id] =
                        img.naturalWidth > 0
                            ? 'loaded'
                            : 'blocked';
                }
            }

            callback(results);
        });
        """)

    print(results)
    return results


'''
The methods below will be executed by the Tester module.
Whatever they return, will be stored in results field in browser_results table of the central database.
CAUTION: DON'T change the name `METHODS_TO_EXECUTE`!
'''
METHODS_TO_EXECUTE = [test_method]