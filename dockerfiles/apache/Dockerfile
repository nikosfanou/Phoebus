FROM httpd

# Install required packages
RUN apt-get update
RUN apt-get install -y php8.2 libapache2-mod-php
RUN cp /usr/lib/apache2/modules/libphp8.2.so /usr/local/apache2/modules/libphp8.2.so
RUN apt-get install -y python3.11
# CMD ["bash"]

# execute:
# docker build -t custom-httpd-image -f ./dockerfiles/apache/Dockerfile .
