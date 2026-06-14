FROM python:3.12

RUN pip install pdm

WORKDIR /workspace
VOLUME ["/workspace/bots", "/workspace/logs"]
COPY pyproject.toml .
COPY pdm.lock .
COPY README.md .
RUN pdm sync

COPY . .
RUN pdm install

CMD ["pdm", "run", "nekobox", "run"]
