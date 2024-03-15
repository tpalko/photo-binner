#!/bin/bash 

for PATH in ~/.local/bin /usr/local/bin /usr/local/lib/python2.7 /usr/local/lib/python3.5 /usr/local/lib/python3.7; do
  #echo "${PATH}"
  /usr/bin/find ${PATH} -name "photobinner*"
  /usr/bin/find ${PATH} -name "pb"
done 
