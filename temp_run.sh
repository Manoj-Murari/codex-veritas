#!/bin/bash

mkdir tmp
cp user_profile.py tmp/
cp -r tests tmp/

cd tmp
docker build -t user-profile-test .
docker run -it --rm user-profile-test