FROM docker.1panel.live/seele0oo/buildenvironment:pyinstaller-centos7-py3.6
# 设置代理（如果有）
# ENV http_proxy=http://192.168.30.254:7890
# ENV https_proxy=http://192.168.30.254:7890

COPY requirements.txt /app/
RUN pip3 install -r /app/requirements.txt
# 将你的代码复制到 Docker 容器中
COPY . /app/

# 在 Docker 中执行 PyInstaller 打包
WORKDIR /app
#RUN pyinstaller --onefile --add-data "config.json:." --add-data "plugins/*:plugins" main.py
RUN pyinstaller --onefile \
    --add-data "config.json:." \
    --add-data "plugins/*:plugins" \
    --collect-submodules core \
    --collect-submodules utils \
    --collect-submodules plugins \
    main.py