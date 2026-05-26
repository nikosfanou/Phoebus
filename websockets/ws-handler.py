import asyncio
import ssl
import websockets
from argparse import ArgumentParser

async def websocket_handler(websocket):
    async for message in websocket:
        print(f"Received message: {message}")
        response = f"Server received: {message}"
        await websocket.send(response)

def setup_ssl(CA, crt, key):
    ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ssl_context.load_cert_chain(crt, key)
    ssl_context.load_verify_locations(CA)
    return ssl_context

def get_args():
    parser = ArgumentParser()
    parser.add_argument("-d", "--inDocker", action = 'store_const', default = False, const=True, dest = "inDocker", help = "Indicates if this script is running inside a docker container. Default value is False (runs in host).")
    parser.add_argument("-H", "--host", dest = "host", nargs = 1, required=True, type=str, help = "The host (IP address) where the websocket server is listening.")
    parser.add_argument("-sp", "--sslPort", default = 8000, const = 8000, dest = "sslPort", nargs = '?', type=int, help = "The port where the server listens for secure websocket connections. Default value is 8000.")
    parser.add_argument("-p", "--port", default = 8001, const = 8001, dest = "port", nargs = '?', type=int, help = "The port where the server listens for insecure websocket connections. Default value is 8001.")
    parser.add_argument("-c", "--CA", dest = "CA", nargs = 1, required=True, type=str, help = "The Certificate Authority used to sign the server's certificates and keys.")

    return parser.parse_args()

# Outside docker run `python3 ws-handler.py --host localhost --CA phoebusCA`
if __name__ == "__main__":
    args = get_args()
    print(args)
    ca_name = args.CA[0]
    host = args.host[0]
    # localhost needs different certificates from 172.100.1.1 so we run different servers for 172.100.1.1 (inside docker
    # container, used for wss://example.com/) and for localhost (outside docker containers, used for wss://localhost)
    ca = f"/{ca_name}.pem" if args.inDocker else f"./certs/{ca_name}.pem"
    crt = "/certs/server.crt" if args.inDocker else f"./certs/{host}/server.crt"
    key = "/certs/server.key" if args.inDocker else f"./certs/{host}/server.key"
    ssl_context = setup_ssl(ca, crt, key)

    async def main():
        await asyncio.gather(
            websockets.serve(websocket_handler, host, args.sslPort, ssl=ssl_context),
            websockets.serve(websocket_handler, host, args.port),
        )
        await asyncio.Future()  
    asyncio.run(main())
