FROM python:3.7-alpine
WORKDIR /redclay
EXPOSE 6666

RUN pip install pipenv
COPY . /redclay
RUN pipenv install

ENTRYPOINT ["pipenv", "run"]
CMD ["python", "-m", "redclay", "run_server"]
