FROM docker.io/library/python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update \
 && apt-get install -y --no-install-recommends ffmpeg fontconfig curl unzip ca-certificates \
 && rm -rf /var/lib/apt/lists/*

# Fonte das legendas (Montserrat, OFL)
RUN mkdir -p /usr/share/fonts/truetype/montserrat \
 && curl -fsSL -o /usr/share/fonts/truetype/montserrat/Montserrat.ttf \
      "https://github.com/google/fonts/raw/main/ofl/montserrat/Montserrat%5Bwght%5D.ttf" \
 && fc-cache -f

# Deno: runtime JS que o yt-dlp usa para resolver os desafios do YouTube
RUN curl -fsSL https://deno.land/install.sh | DENO_INSTALL=/usr/local sh -s -- -y \
 && deno --version

# Claude Code CLI (LLM_PROVIDER=claude_code)
ARG CLAUDE_CODE_VERSION=2.1.330
RUN curl -fsSL https://claude.ai/install.sh | bash -s ${CLAUDE_CODE_VERSION} \
 && ln -sf /root/.local/bin/claude /usr/local/bin/claude \
 && claude --version

WORKDIR /app
COPY worker/requirements.txt .
RUN pip install -r requirements.txt

COPY worker/app ./app
COPY db/migrations ./migrations

EXPOSE 8080
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
