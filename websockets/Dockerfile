FROM python:3.10
ADD ws-handler.py ws-handler.py
RUN pip3 install websockets
ARG CA_NAME
ARG HOST
ARG PORT
ARG SSL_PORT
ENTRYPOINT python3 ws-handler.py --inDocker --host $HOST --CA $CA_NAME --port $PORT --sslPort $SSL_PORT

# docker build -f ./websockets/Dockerfile -t ws-server ./websockets
# NOTE: also mount certificates on docker run!
# docker run -e HOST=172.100.1.1 -e CA_NAME=phoebusCA -e PORT=8001 -e SSL_PORT=8000 -p 8000:8000 -p 8001:8001 -itd --network my-net --ip 172.100.1.1 --name ws-server ws-server