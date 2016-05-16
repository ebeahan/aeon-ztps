#!/bin/sh

sudo apt-get update

sudo apt-get install -y build-essential python-dev
sudo apt-get install -y python-pip
sudo apt-get install libxml2-dev libxslt-dev zlib1g-dev

sudo pip install Flask
sudo pip install Celery
sudo pip install pyscopg2
sudo pip install lxml

sudo apt-get -y install rabbitmq-server
sudo apt-get -y install postgresql postgresql-contrib
