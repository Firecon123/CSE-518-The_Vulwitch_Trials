# Local Environment for Attacking

In order to facilitate testing and attacking the target messaging system, we
have investigated about how to set up a local instance of the target system.
Ultimately, we have bring up such an instance. This document serves as a
tutorial to set it up.

## Check out source code

We have made some changes to the source code of the target system. Changes are
provided as a patch file ([local.patch](./local.patch)). You can follow the
following steps to get source code and apply the patch.

```shell
$ cd $HOME && git clone git@github.com:Firecon123/CSE-518-The_Vulwitch_Trials.git vulwitch
$ cd $HOME && git clone git@github.com:BrendanDupuis/CSE418-Project.git webapp
$ cd $HOME/webapp
$ git checkout e4109b0729aa624dc6b2e2664133e395c4c60076
$ git apply $HOME/vulwitch/attack/local/local.patch
```

## Docker container

We are running our local instance in a Docker container.

```shell
$ cd $HOME/vulwitch
$ docker build --file attack/local/Dockerfile -t attack-local-env ./
$ docker run -v $HOME/webapp:/root/webapp -p 8080:80 -it --name local-attack attack-local-env:latest
```

## Set up a local instance

A CA-issued or self-assigned SSL certificate is required to run the code. We are
running the local instance on a personal computer, and accessing it via VPN
functionalities provided by [Tailscale](https://tailscale.com). Thus, we are
using an SSL certificate issued by [Let's Encrypt](https://letsencrypt.org).
The certificate and the private key are generated via Tailscale's commond-line
tool.

```shell
$ cd $HOME/webapp
$ sudo tailscale cert linux-server-1.tailf2c50.ts.net
```

```shell
$ pnpm install
$ pnpm run dev -p 80 \
    --experimental-https \
    --experimental-https-key ./linux-server-1.tailf2c50.ts.net.key \
    --experimental-https-cert ./linux-server-1.tailf2c50.ts.net.crt
```

For devices with [Tailscale clients](https://tailscale.com/download) and
connected to our internal network, you can access our local instance at
`https://linux-server-1.tailf2c50.ts.net:8080`. A local instance should look
like the following one.

![local instance][./img/local_instance.png]

Our local instance have some features disabled:

1. Our local instance does not send emails containing verification code to users
when they are logging into the system. Instead, verification code is static and
always 666666.

2. To facilitate testing and attacking, rate limiting is disabled.
