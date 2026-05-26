from mitmproxy.tools.dump import DumpMaster
from mitmproxy.options import Options
import multiprocessing
import importlib

class MiTMProxy():
    addons_module = "utils.MiTM_addons"
    # defeault_opts = {
        # 'listen_host': "127.0.0.1",
        # 'listen_port': 8080,
        # 'confdir': "./certs", 
        # 'ssl_insecure': True
    # }
    
    def __init__(self, name:str, queue:multiprocessing.Queue, options:dict={}):
        self.name = name
        self.queue = queue
        self.options = options
        self.addon_names = []
        self.addon_classes = []
        self.proxy = None
        self.proxy_options = None

    def create(self):
        if not self.proxy:
            print(f'Creating {self.name} proxy...')
            self.proxy_options = Options(**self.options)
            # with_termlog=False, with_dumper=False -> in order not to overflow the terminal with not needed logs!
            self.proxy = DumpMaster(self.proxy_options, with_termlog=False, with_dumper=False)

    def clear_addons(self):
        if self.proxy:
            print(f'Clearing {self.name} proxy addons...')
            self.proxy.addons.clear()
            self.addon_names = []
            self.addon_classes = []

    def add_addon(self, addon:str, **kwargs):
        if self.proxy:
            print(f'Adding addon {addon} on {self.name} proxy...')
            self.addon_names.append(addon)
            module = importlib.import_module(self.addons_module)
            addon_class = getattr(module, addon)
            addon_instance = addon_class(self.queue, **kwargs)
            self.addon_classes.append(addon_instance)
            self.proxy.addons.add(addon_instance)

    async def run(self):
        if self.proxy:
            print(f'Running {self.name} proxy...')
            await self.proxy.run()

    def shutdown(self):
        if self.proxy:
            print(f'Stopping {self.name} proxy...')
            self.proxy.shutdown()
