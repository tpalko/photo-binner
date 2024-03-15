#!/bin/bash

if [[ $# -lt 2 ]]
then
    echo "Usage: "
    echo "$0 <path to expected dupes> <path to find matches>"
    exit 1
fi

mkdir -p $1/checked
for filepath in $1/*
do
    echo
    filename=$(basename $filepath)
    thissize=$(stat $filepath | grep Size | awk '{ print $2 }')
    foundpath=$(find $2 -name "$filename")
    echo "Looking for $filename: ($thissize)"
    for f in $(find $2 -name "$filename")
    do
	size=$(stat "$f" | grep Size | awk '{ print $2 }')
        [[ $thissize -eq $size ]] && match=1 || match=0
        echo "$f: $size $([[ $match -eq 1 ]] && echo "match")"
	if [[ $match -eq 1 ]]
	then
	    mv -v $filepath $1/checked/
	fi
    done
done

