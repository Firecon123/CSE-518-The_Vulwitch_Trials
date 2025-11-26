```shell
$ mkdir linux-kernel
$ cd linux-kernel
$ curl -LO https://cdn.kernel.org/pub/linux/kernel/v6.x/linux-6.17.8.tar.xz
$ tar -xf linux-6.17.8
$ docker run -v $PWD/linux-6.17.8:/root/linux-6.17.8 -it \
    --name linux-kernel-builder ubuntu:24.04
```

```shell
$ apt update
$ apt install -y libncurses-dev make git exuberant-ctags bc libssl-dev \
    flex bison libelf-dev build-essential \
    cpio unzip rsync vim wget file xz-utils \
    bear
$ cd /root/linux-6.17.8
$ mkdir build-dir
$ cd build-dir
$ make defconfig
$ bear -- make -j$(nproc)
```
