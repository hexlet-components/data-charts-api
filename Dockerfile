FROM python:3.12-slim

RUN apt-get update && \
    apt-get install -y make && \
    pip install uv

ENV UV_COMPILE_BYTECODE=1

WORKDIR /app
COPY . .
RUN make install

CMD ["make", "run"]
