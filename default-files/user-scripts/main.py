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
    '''
    Write your code here!
    '''


'''
The methods below will be executed by the Tester module.
Whatever they return, will be stored in results field in browser_results table of the central database.
CAUTION: DON'T change the name `METHODS_TO_EXECUTE`!
'''
METHODS_TO_EXECUTE = [test_method]