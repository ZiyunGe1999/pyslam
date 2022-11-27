FROM python:3.6.9

RUN apt update
RUN apt install -y nano vim cmake libglew-dev
RUN pip3 install -U pysdl2
RUN echo "deb http://security.ubuntu.com/ubuntu bionic-security main" | tee -a /etc/apt/sources.list
RUN apt-key adv --keyserver keyserver.ubuntu.com --recv-keys 3B4FE6ACC0B21F32
RUN apt update
RUN apt install -y python3.6-dev
RUN rm /usr/bin/python3.7*
RUN apt install -y x11-apps

ADD . /pyslam
RUN cd /pyslam && ./clean.sh && ./install_all.sh

RUN pip3 install kapture