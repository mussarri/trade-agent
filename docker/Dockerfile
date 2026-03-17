FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y gcc && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .
COPY core ./core
COPY scenarios ./scenarios
COPY scoring ./scoring
COPY risk ./risk
COPY alerts ./alerts
COPY api ./api
COPY config ./config
COPY backtest ./backtest
COPY tests ./tests
COPY main.py ./main.py

RUN pip install --no-cache-dir -e .[dev]
RUN python -m pytest -q

VOLUME ["/app/config"]

EXPOSE 8000

CMD ["python", "main.py"]
