FROM alpine:3.12.1

WORKDIR /app

RUN apk add python3 python3-dev musl-dev py3-pip linux-headers gcc
RUN pip install \
  certifi==2020.6.20 \
  chardet==3.0.4 \
  evdev==1.3.0 \
  idna==2.10 \
  python-dotenv==0.14.0 \
  python-musicpd==0.4.4 \
  requests==2.24.0 \
  six==1.15.0 \
  spotipy==2.16.0 \
  urllib3==1.25.10 

COPY . /app

CMD python3 rfidmc.py /etc/rfidmc/config.toml



