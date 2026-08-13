FROM python:3.14-slim

RUN apt-get update && apt-get install -yq make

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app
COPY . .
RUN make install

CMD ["make", "run"]
