#!/bin/bash 

WORK_FOLDER=$1

echo "Work folder: $WORK_FOLDER"

for filename in $(find $WORK_FOLDER)
do
	date_string=$(echo $filename | egrep -o '[[:digit:]]{8}_[[:digit:]]{6}')
	year=${date_string:0:4}
	month=${date_string:4:2}
	dater=${date_string:6:2}
	hour=${date_string:9:2}
	minute=${date_string:11:2}
	second=${date_string:13:2}
	echo "$filename -> $year-$month-$dater $hour:$minute:$second"
	touch -d "$year-$month-$dater $hour:$minute:$second" placeholder
	touch -r $WORK_FOLDER/placeholder $filename
done