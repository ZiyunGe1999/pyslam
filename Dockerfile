FROM nvidia/cudagl:11.2.0-devel-ubuntu18.04

RUN apt update; exit 0
RUN rm /etc/apt/sources.list.d/cuda.list /etc/apt/sources.list.d/nvidia-ml.list && \
    apt-key del 7fa2af80 && \
    apt install -y wget && \
    wget https://developer.download.nvidia.com/compute/cuda/repos/ubuntu1804/x86_64/cuda-keyring_1.0-1_all.deb && \
    dpkg -i cuda-keyring_1.0-1_all.deb && \
    apt update
RUN apt install -y python3 python3-pip
RUN apt install -y nano vim cmake libglew-dev
RUN pip3 install -U pysdl2
RUN echo "deb http://security.ubuntu.com/ubuntu bionic-security main" | tee -a /etc/apt/sources.list
RUN apt-key adv --keyserver keyserver.ubuntu.com --recv-keys 3B4FE6ACC0B21F32
RUN apt update
RUN apt install -y python3.6-dev
RUN apt install -y x11-apps

ENV TZ=US/Pacific
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone
RUN apt install -y git
ADD . /pyslam
RUN cd /pyslam && ./clean.sh && ./install_all.sh