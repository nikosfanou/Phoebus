from mitmproxy import http
from multiprocessing import Queue
from utils import RequestsHandler

class CaptureRequestsAddon():
    def __init__(self, queue: Queue):
        self.requests = queue
        self.status_codes_drop_content = [100, 101, 102, 103, 204, 205, 304] # https://fetch.spec.whatwg.org/#null-body-status + a few more we found.
    
    def request(self, flow: http.HTTPFlow) -> None:
        self.requests.put(flow.request)

    def response(self, flow: http.HTTPFlow) -> None:
        # NOTE: Mitmproxy may drop the content e.g., on some responses with Status Code 1XX. I send a raw but equal http request and craft the response.
        if flow.response.status_code in self.status_codes_drop_content and not flow.response.raw_content:
            # print('NO CONTENT', flow.response.status_code)
            request = flow.request
            raw_request = f"{request.method} {request.path} {request.http_version}\r\n"
            for header_name, header_value in flow.request.headers.items(multi=True):
                if header_name == 'Proxy-Connection' or header_name == 'Connection':
                    continue
                raw_request += f"{header_name}: {header_value}\r\n"
            raw_request += "Connection: close\r\n" # for fast response
            raw_request += '\r\n'
            if request.raw_content:
                raw_request += request.raw_content.decode(errors="ignore")
            # print(raw_request)
            if request.scheme == 'http':
                resp = RequestsHandler.send_raw_http_request(host=request.pretty_host, port=request.port, request=raw_request)
            elif request.scheme == 'https':
                resp = RequestsHandler.send_raw_https_request(host=request.pretty_host, port=request.port, request=raw_request)
            _, headers, body = RequestsHandler.parse_raw_http_response(response=resp)
            if body.strip():
                # Craft body
                flow.response.set_text(text=body)
                # Craft headers
                flow.response.headers.clear()
                for header_name, header_value in headers:
                    flow.response.headers[header_name] = header_value
            # print(flow.response.data)
        # print(flow.response.headers)