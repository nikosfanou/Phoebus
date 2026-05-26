import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import base64
import json

class ContentExtractor:
    url_attributes = ["src", "href", "data", "action", "formaction", "xlink:href"]
    can_create_new_browsing_contexts = ["iframe", "frame", "object", "embed"]

    def __init__(self, url):
        self.url = url
        self.visited_html = set() # avoid processing the same HTML twice

    def fetch(self, url):
        r = requests.get(url)
        return r.text

    def extract(self):
        html = self.fetch(self.url)
        results = []
        self.parse_html(html, results)
        return list(dict.fromkeys(results))

    # Must be implemented by subclasses
    def parse_html(self, html, results):
        raise NotImplementedError("Subclasses must implement parse_html()")


class JSContentExtractor(ContentExtractor):
    event_attributes_source = "configs/extensive-html-events-list.json"
    _cached_event_attributes = None  # class-level cache

    def __init__(self, url):
        super().__init__(url)

        # NOTE: heuristic for performance, if we got event_attributes once, keep it in a variable so that we don't need to load them every time.
        if JSContentExtractor._cached_event_attributes is None:
            JSContentExtractor._cached_event_attributes = self._get_all_event_attributes()
        self.event_attributes = JSContentExtractor._cached_event_attributes

    def _get_all_event_attributes(self):
        with open(self.event_attributes_source, 'r') as fp:
            obj = json.load(fp)
        all_event_attributes = []
        for values in obj.values():
            for event in values:
                all_event_attributes.append(f"on{event}")
        # deduplicate
        return list(dict.fromkeys(all_event_attributes))
        
    def parse_html(self, html, results):
        if html in self.visited_html:
            return
        self.visited_html.add(html)

        soup = BeautifulSoup(html, "html.parser")
        self.extract_inline_scripts(soup, results)
        self.extract_external_scripts(soup, results)
        self.extract_event_handlers(soup, results)
        self.extract_javascript_urls(soup, results)
        self.extract_srcdoc(soup, results)
        self.extract_data_urls(soup, results)

    def extract_inline_scripts(self, soup, results):
        scripts = soup.find_all("script")
        for script in scripts:
            if script.string is not None and script.string.strip():
                results.append(script.string)

    def extract_external_scripts(self, soup, results):
        scripts = soup.find_all("script", src=True)
        for script in scripts:
            src = script["src"]
            src = src.lstrip()
            if src.startswith("javascript:") or src.startswith("data:"): # will handle later
                continue
            if src.startswith("https:"): # avoid ssl errors
                src = 'http:' + src[len('https:'):]

            try:
                url = urljoin(self.url, src)
                results.append(self.fetch(url))
            except Exception:
                pass

    def extract_event_handlers(self, soup, results):
        for attr in self.event_attributes:
            elements = soup.find_all(attrs={attr: True})
            for el in elements:
                js = el.get(attr)
                if js.strip():
                    results.append(js)

    def extract_srcdoc(self, soup, results):
        iframes = soup.find_all("iframe", srcdoc=True)
        for iframe in iframes:
            html = iframe.get("srcdoc")
            if html.strip():
                self.parse_html(html, results) # NOTE: find js recursively for local schemes

    def extract_javascript_urls(self, soup, results):
        for attr in self.url_attributes:
            elements = soup.find_all(attrs={attr: True})
            for el in elements:
                value = el.get(attr)
                if not value.strip():
                    continue

                l_stripped_value = value.lstrip()
                if not l_stripped_value.startswith("javascript:"):
                    continue
                
                value = value[len("javascript:"):] # remove javascript:
                stripped_value = value.strip()

                # remove wrapping quotes if present
                if (stripped_value.startswith('"') and stripped_value.endswith('"')) or \
                (stripped_value.startswith("'") and stripped_value.endswith("'")) or \
                (stripped_value.startswith("`") and stripped_value.endswith("`")):
                    value = stripped_value[1:-1]
                    kind = "html" # when a javascript: URL returns a string (which means inside quotes) then the content is treated as HTML.
                else:
                    kind = "js"

                # If the attribute belongs to an element that creates a new browsing context
                # and the payload is HTML, parse it recursively.
                if kind == "js":
                    if value.strip():
                        results.append(value)
                elif kind == "html" and el.name in self.can_create_new_browsing_contexts:
                    if value.strip():
                        self.parse_html(value, results)

    def extract_data_urls(self, soup, results):
        for attr in self.url_attributes:
            elements = soup.find_all(attrs={attr: True})
            for el in elements:
                value = el.get(attr)
                if not value.strip():
                    continue

                l_stripped_value = value.lstrip()
                if not l_stripped_value.startswith("data:"):
                    continue

                value = value[len("data:"):] # remove data:
                try:
                    metadata, payload = value.split(",", 1)
                    metadata = metadata.lower().strip()
                    # We only extract javascript for these specific content-types, else we would need heuristics to determine the content type.
                    if metadata.startswith("text/html"):
                        kind = "html"
                        metadata = metadata[len("text/html"):]
                    elif metadata.startswith("text/javascript"):
                        kind = "js"
                        metadata = metadata[len("text/javascript"):]
                    else:
                        continue
                    
                    metadata = metadata.strip()
                    # if ;base64, then the payload is encoded
                    if metadata == ";base64":
                        decoded = base64.b64decode(payload).decode("utf-8", errors="ignore")
                    else:
                        decoded = payload
                        # or decoded = urllib.parse.unquote(payload) ?

                    # If the attribute belongs to an element that creates a new browsing context
                    # and the payload is HTML, parse it recursively.
                    if kind == "js":
                        if decoded.strip():
                            results.append(decoded)
                    elif kind == "html" and el.name in self.can_create_new_browsing_contexts:
                        if decoded.strip():
                            self.parse_html(decoded, results)
                
                except Exception:
                    pass


class CSSContentExtractor(ContentExtractor):
    def parse_html(self, html, results):
        if html in self.visited_html:
            return
        self.visited_html.add(html)

        soup = BeautifulSoup(html, "html.parser")
        self.extract_inline_styles(soup, results)
        self.extract_external_styles(soup, results)
        self.extract_style_attributes(soup, results)
        self.extract_srcdoc(soup=soup, results=results)
        self.extract_javascript_urls(soup=soup, results=results)
        self.extract_data_urls(soup=soup, results=results)

    def extract_inline_styles(self, soup, results):
        styles = soup.find_all("style")
        for style in styles:
            if style.string is not None and style.string.strip():
                results.append(style.string)
    
    def extract_external_styles(self, soup, results):
        links = soup.find_all("link")
        for link in links:
            rel = link.get("rel")
            if not rel or "stylesheet" not in rel:
                continue

            href = link.get("href")
            if not href:
                continue

            href = href.lstrip()
            if href.startswith("javascript:") or href.startswith("data:"): # will handle later
                continue
            
            if href.startswith("https:"): # avoid ssl errors
                href = 'http:' + href[len('https:'):]

            try:
                url = urljoin(self.url, href)
                results.append(self.fetch(url))
            except Exception:
                pass

    def extract_style_attributes(self, soup, results):
        elements = soup.find_all(style=True)
        for el in elements:
            css = el.get('style')
            if css.strip():
                results.append(css)

    def extract_srcdoc(self, soup, results):
        iframes = soup.find_all("iframe", srcdoc=True)
        for iframe in iframes:
            html = iframe.get("srcdoc")
            if html.strip():
                self.parse_html(html, results) # NOTE: find js recursively for local schemes

    def extract_javascript_urls(self, soup, results):
        for attr in self.url_attributes:
            elements = soup.find_all(attrs={attr: True})
            for el in elements:
                value = el.get(attr)
                if not value.strip():
                    continue

                l_stripped_value = value.lstrip()
                if not l_stripped_value.startswith("javascript:"):
                    continue
                
                value = value[len("javascript:"):] # remove javascript:
                stripped_value = value.strip()

                # remove wrapping quotes if present
                if (stripped_value.startswith('"') and stripped_value.endswith('"')) or \
                (stripped_value.startswith("'") and stripped_value.endswith("'")) or \
                (stripped_value.startswith("`") and stripped_value.endswith("`")):
                    value = stripped_value[1:-1]
                else:
                    continue

                # If the attribute belongs to an element that creates a new browsing context
                # and the payload is HTML, parse it recursively.
                if value.strip():
                    self.parse_html(value, results)

    def extract_data_urls(self, soup, results):
        for attr in self.url_attributes:
            elements = soup.find_all(attrs={attr: True})
            for el in elements:
                value = el.get(attr)
                if not value.strip():
                    continue

                l_stripped_value = value.lstrip()
                if not l_stripped_value.startswith("data:"):
                    continue

                value = value[len("data:"):] # remove data:
                try:
                    metadata, payload = value.split(",", 1)
                    metadata = metadata.lower().strip()
                    # We only extract css for these specific content-types, else we would need heuristics to determine the content type.
                    if metadata.startswith("text/html"):
                        kind = "html"
                        metadata = metadata[len("text/html"):]
                    elif metadata.startswith("text/css"):
                        kind = "css"
                        metadata = metadata[len("text/css"):]
                    else:
                        continue
                    
                    metadata = metadata.strip()
                    # if ;base64, then the payload is encoded
                    if metadata == ";base64":
                        decoded = base64.b64decode(payload).decode("utf-8", errors="ignore")
                    else:
                        decoded = payload
                        # or decoded = urllib.parse.unquote(payload) ?

                    # If the attribute belongs to an element that creates a new browsing context
                    # and the payload is HTML, parse it recursively.
                    if kind == "css":
                        if decoded.strip():
                            results.append(decoded)
                    elif kind == "html" and el.name in self.can_create_new_browsing_contexts:
                        if decoded.strip():
                            self.parse_html(decoded, results)
                
                except Exception:
                    pass