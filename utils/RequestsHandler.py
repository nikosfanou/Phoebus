import socket
import ssl

# Example: request = f"GET /test.html HTTP/1.1\r\nHost: {host}\r\nConnection: close\r\n\r\n"
def send_raw_http_request(host, port, request):
    with socket.create_connection((host, port)) as sock:
        sock.sendall(request.encode())
        response = b""
        while True:
            chunk = sock.recv(4096)
            if not chunk:
                    break
            response += chunk
        return response.decode(errors="ignore")

def send_raw_https_request(host, port, request):
    context = ssl.create_default_context()
    with socket.create_connection((host, port)) as sock:
        with context.wrap_socket(sock, server_hostname=host) as ssock:
            ssock.sendall(request.encode())
            response = b""
            while True:
                chunk = ssock.recv(4096)
                if not chunk:
                    break
                response += chunk
            return response.decode(errors="ignore")

def parse_raw_http_response(response):
    headers_part, body = response.split("\r\n\r\n", 1)
    headers_str = headers_part.split('\r\n')
    first_line = headers_str.pop(0)
    headers = []
    for header in headers_str:
        splitted = header.split(': ')
        key = splitted[0]
        value = ': '.join(splitted[1:])
        headers.append((key,value))
    return first_line, headers, body