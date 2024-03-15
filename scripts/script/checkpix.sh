#!/bin/bash

while read f;
do
	IFS='/' read -ra pathparts <<< "$f"
	datepart=${pathparts[1]}	
	filename=${pathparts[2]}	
	IFS='_' read -ra dateparts <<< "$datepart"
	year=${dateparts[0]}
	fullpath="/media/storage_old/${pathparts[0]}/$year/$datepart/$filename"
	if [ ! -f $fullpath ];
	then
		echo "missing $fullpath"
	fi
done < frankenputer_pics.txt

