#! /bin/bash

gunicorn -w 1 --bind 0.0.0.0:8000 main:app 
