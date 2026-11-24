FROM coady/pylucene@sha256:4a37ca24019a9f1d2d94196323ccc8d7b465174d9229b2328429749989d4d05e
USER root
RUN pip install --no-cache-dir pyspark==4.0.1
WORKDIR /app
ENV PYTHONPATH=/app PYTHONUNBUFFERED=1 SPARK_LOCAL_IP=127.0.0.1
CMD ["python", "search.py"]
