# Here, we add the webdriver methods we want to wrap/change!
class GenericDriverWrapper:
    def get(self, url):
        try:
            return super().get(url)
        except Exception as e:
            print(f"driver.get() failed, will retry!")
        return super().get(url)  # Final try, let error raise if it fails

# This returns dynamically a new class, which inherits from two classes, firstly from the wrapped class,
# and then (with super()) from the driver_class (webdriver.Chrome/Firefox/Edge/WebKitGTK etc.)
def wrap_driver(driver_class):
    class WrappedDriver(GenericDriverWrapper, driver_class):
        pass
    return WrappedDriver