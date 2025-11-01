FROM ubuntu:24.04

# Install Node.js version manager
RUN apt update -y && apt install -y curl
RUN curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.3/install.sh | bash
RUN ["/bin/bash", "-ic", "nvm install --lts && corepack enable pnpm"]
RUN ["/bin/bash", "-ic", "node -v && pnpm -v"]
# Use /bin/bash as the entrypoint
ENTRYPOINT ["/bin/bash"]
