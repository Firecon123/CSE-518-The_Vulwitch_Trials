```bash
$ mkdir redis
$ cd redis
$ curl -o redis-8.4.0.tar.gz -L https://github.com/redis/redis/archive/refs/tags/8.4.0.tar.gz
$ tar -xf redis-8.4.0.tar.gz
$ docker run -v $PWD/redis-8.4.0:/root/redis-8.4.0 -it \
    --name redis-builder ubuntu:24.04
```

```bash
$ apt-get update
$ apt-get install -y --no-install-recommends \
    ca-certificates wget dpkg-dev gcc g++ libc6-dev libssl-dev make git cmake \
    python3 python3-pip python3-venv python3-dev unzip rsync clang automake \
    autoconf libtool bear
$ cd /root/redis-8.4.0
$ export BUILD_TLS=yes BUILD_WITH_MODULES=yes INSTALL_RUST_TOOLCHAIN=yes DISABLE_WERRORS=yes
$ mkdir redis-build-dir && cd redis-build-dir
$ bear -- make -C ../ -j "$(nproc)" all
```
