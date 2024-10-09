FROM $BASE_IMAGE

ENV PYTHONUNBUFFERED 1
WORKDIR /app

COPY requirements/* .
RUN pip install --no-cache-dir -r requirements.txt
ENV PROJECT_NAME $PROJECT_NAME

EXPOSE 8080
CMD ["weave", "serve", "$MODEL_REF", "--port=8080", "--method=$MODEL_METHOD", "--auth-entity=$AUTH_ENTITY"]
