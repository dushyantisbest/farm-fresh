FROM python:3.11-slim
WORKDIR /app
RUN useradd --create-home --uid 10001 inventory && mkdir /data && chown inventory /data
COPY app.py inventory.py forecast.py festival_history.csv ./
COPY static ./static
USER inventory
ENV HOST=0.0.0.0 PORT=8000 INVENTORY_DB=/data/inventory.db PYTHONDONTWRITEBYTECODE=1
EXPOSE 8000
VOLUME ["/data"]
HEALTHCHECK --interval=30s --timeout=4s CMD python -c "from urllib.request import urlopen; urlopen('http://127.0.0.1:8000/health', timeout=3).close()"
CMD ["python", "app.py"]
