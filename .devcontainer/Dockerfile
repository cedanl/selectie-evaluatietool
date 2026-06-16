FROM mcr.microsoft.com/devcontainers/base:bookworm

# System libraries that kaleido's headless Chromium needs to render charts for the PDF report.
RUN apt-get update && export DEBIAN_FRONTEND=noninteractive && \
    apt-get install -y --no-install-recommends \
        ca-certificates \
        fonts-liberation \
        libasound2 \
        libatk-bridge2.0-0 \
        libatk1.0-0 \
        libatspi2.0-0 \
        libcups2 \
        libdbus-1-3 \
        libdrm2 \
        libgbm1 \
        libgtk-3-0 \
        libnspr4 \
        libnss3 \
        libx11-6 \
        libxcomposite1 \
        libxdamage1 \
        libxext6 \
        libxfixes3 \
        libxkbcommon0 \
        libxrandr2 \
        xdg-utils && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Standard CLI tools: gh (GitHub CLI), jq, ripgrep. git is already in the base image.
RUN apt-get update && export DEBIAN_FRONTEND=noninteractive && \
    apt-get install -y --no-install-recommends jq ripgrep && \
    mkdir -p -m 755 /etc/apt/keyrings && \
    curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg -o /etc/apt/keyrings/githubcli-archive-keyring.gpg && \
    chmod go+r /etc/apt/keyrings/githubcli-archive-keyring.gpg && \
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" > /etc/apt/sources.list.d/github-cli.list && \
    apt-get update && apt-get install -y --no-install-recommends gh && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# uv for Python dependency management (matches how the project is run).
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Node LTS for the Claude Code CLI.
RUN su vscode -c "curl -fsSL https://deb.nodesource.com/setup_lts.x | sudo -E bash -" && \
    apt-get install -y --no-install-recommends nodejs && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Claude Code, available inside the isolated container.
RUN npm install -g @anthropic-ai/claude-code

# Pre-create ~/.claude owned by vscode so the read-only instruction-file mounts
# land inside a writable parent. Without this, Docker creates the mount target
# as root and Claude Code can't write session-env / sessions into it.
RUN mkdir -p /home/vscode/.claude && chown -R vscode:vscode /home/vscode/.claude

# Inside this isolated container, default `claude` to skip permission prompts
# and use Opus. Safe here because the container can't touch the host.
RUN echo "alias claude='claude --dangerously-skip-permissions --model opus'" >> /home/vscode/.bashrc

ENV UV_LINK_MODE=copy
