#!/bin/bash



# recurse into a folder, looking at each file
# filter files by mime type/extension -> images and videos
# determine actual timestamp
  # 1. in the filename ex. IMG_YYYYMMDD_HHMMSS.JPG
  # 2. in the exif metadata
  # 3. in other metadata
# if the file's chain of containing folders has a datestamp folder and that datestamp is incorrect
  # then create a datestamp folder sibling to the existing (incorrect) datestamp folder
  # recreate any subfolders beneath that up to the file in question
  # move the file over
  # move any related files (.xmp, etc.)

#-t timestamps bugs:
# -- stat shows UTC, meta shows local
# -- also, year/date folders aren't being worked out of the "details" folder name component
# Processing /media/storage/pics/2015/2015-06-26/IMG_2823.jpg..
#     stat (2015-08-09) does not match calculated (2015-08-08)
#     fixing /media/storage/pics/2015/2015-06-26/IMG_2823.jpg timestamp from Modify: 2015-08-09 01:52:30.549122000 -0400 to 2015-08-08 21:52:27 -0400..
#     either stat (2015-08-09) or folder date (2015-06-26) does not match calculated (2015-08-08)
#     moving /media/storage/pics/2015/2015-06-26/IMG_2823.jpg to /media/storage/pics/2015/2015-08-08_2015_2015_06_26..
#
#   Processing /media/storage/pics/2015/2015-12-30/IMG_20151230_023635.jpg..
#       stat (2015-12-30) does not match calculated (2015-12-29)
#       fixing /media/storage/pics/2015/2015-12-30/IMG_20151230_023635.jpg timestamp from Modify: 2015-12-30 02:36:35.000000000 -0500 to 2015-12-29 21:36:35 -0500..
#       either stat (2015-12-30) or folder date (2015-12-30) does not match calculated (2015-12-29)
#       moving /media/storage/pics/2015/2015-12-30/IMG_20151230_023635.jpg to /media/storage/pics/2015/2015-12-29_2015_2015_12_30..

#-c copy bugs
# Processing /sdcard/Pictures/Image Editor/Downloads..
# ls: /sdcard/Pictures/Image: No such file or directory
# ls: Editor/Downloads: No such file or directory
#   Found 0 files..


#SOURCES=( "/mnt/sdcard/DCIM/baconreader" "/mnt/sdcard/Download" )
#
# - adb pull is recursive, but there are other things in /mnt/sdcard/DCIM we don't want (thumbnails)
SOURCES=( "/mnt/sdcard/DCIM/Camera" "/mnt/sdcard/DCIM/baconreader" "/mnt/sdcard/Download" "/sdcard/Pictures/Screenshots" "/sdcard/Pictures/Image Editor" "/sdcard/Pictures/Image Editor/Downloads" "sdcard/panoramas" )
# - granular by date - copies done on the same date will overwrite existing/missing files
TARGET=/media/storage/pics/mobile_inbox/$(date +%Y%m%d)
DRYRUN=0

if [[ $# -gt 0 ]]
then
  action="$1"
  case $action in
    -t|--timestamps)
    ACTION="timestamps"
    shift
    ;;
    -c|--copy)
    ACTION="copy"
    shift
    ;;
  esac
fi

if [[ -z ${ACTION+x} ]]
then
  echo "Valid action not supplied."
  exit 1
else
  echo "Running -> $ACTION"
fi

# - flag parsing
while [[ $# -gt 0 ]]
do
  key="$1"

  case $key in
    -i|--inputfile)
    INPUTFILE="$2"
    shift
    shift
    ;;
    -s|--source)
    SOURCE="$2"
    shift
    shift
    ;;
    -w|--workfolder)
    WORKFOLDER="$2"
    shift
    shift
    ;;
    -d|--dryrun)
    DRYRUN=1
    shift
    shift
    ;;
  esac

done

# - flag/input validation
if [[ "$ACTION" = "copy" ]]
then
  if [[ (-z ${INPUTFILE+x} && -n ${SOURCE+x}) || (-n ${INPUTFILE+x} && -z ${SOURCE+x}) ]]
  then
    echo "Both source and input file must be provided if either is provided."
    exit 1
  fi
  # -- SOURCES is always expected to be an array, so if SOURCE is supplied, make SOURCES an array of this one
  if [[ -n ${SOURCE+x} ]]
  then
    SOURCES=(${SOURCES[SOURCE]})
  fi
fi

if [[ "$ACTION" = "timestamps" ]]
then
  if [[ -z ${WORKFOLDER+x} ]]
  then
    echo "A -w workfolder must be supplied for a -t timestamps action"
    exit 1
  fi
fi

_extract_date_from_path() {
  local path_year_and_date=$(echo "$path_to_file" | egrep -o '[[:digit:]]{4}/[[:digit:]]{4}-[[:digit:]]{2}-[[:digit:]]{2}')
  IFS='/' read -ra DATEPARTS <<< "$path_year_and_date"
  #folder_year=${DATEPARTS[0]}
  PATH_DATE=${DATEPARTS[1]}
}

_extract_descriptive_timestamp_folder() {
  # - try to extract other desriptive information from path
  # -- take off the base path
  local LAST="${path_to_file##$WORKFOLDER}"
  #echo LAST: $LAST
  # -- take off the filename
  local MIDDLE="${LAST%%$(basename "$path_to_file")}"
  #echo MIDDLE: $MIDDLE
  # -- take out the date and extract only alpha/num
  local alt_path_date=$(echo "$path_to_file" | egrep -o '[[:digit:]]{4}_[[:digit:]]{2}_[[:digit:]]{2}')
  local ALLBUTDATE=${MIDDLE/$alt_path_date/}
  ALLBUTDATE=$(echo "${ALLBUTDATE/$path_date/}" | egrep -o "[[:alnum:]]*")
  #echo ALLBUTDATE: $ALLBUTDATE
  # -- replace spaces with _
  local DESC="${ALLBUTDATE//[[:space:]]/_}"
  #echo DESC: $DESC
  #year=${CALCULATED_DATE:0:4}
  NEW_DIR=$WORKFOLDER/${CALCULATED_DATE:0:4}/$CALCULATED_DATE
  if [[ -n "${DESC+x}" ]]
  then
    NEW_DIR=${NEW_DIR}_${DESC}
  fi
}

_extract_timestamp_from_filename() {
  # - try to extract date info from filename
  date_string=$(echo "$filename" | egrep -o '[[:digit:]]{8}_[[:digit:]]{6}')
  year=${date_string:0:4}
  month=${date_string:4:2}
  dater=${date_string:6:2}
  hour=${date_string:9:2}
  minute=${date_string:11:2}
  second=${date_string:13:2}
  if [[ (-n ${year} && -n ${month} && -n ${dater} && -n ${hour} && -n ${minute} && -n ${second}) ]]
  then
    CALCULATED_TIMESTAMP="$year-$month-$dater $hour:$minute:$second"
    CALCULATED_DATE="$year-$month-$dater"
  fi
}

_cleanup() {
  unset NEW_DIR
  unset PATH_DATE
  unset CALCULATED_DATE
  unset CALCULATED_TIMESTAMP
}

# /mnt/shell/emulated/media
# /mnt/shell/emulated/DCIM

# -- checks an image file's "true" (embedded or filename-given) timestamp against the 'modify' or 'created' timestamp as given by `stat`
# -- could also check the "true" date against that which is suggested by the file's folder structure
correct_timestamp() {
  local path_to_file="$1"
  local ext="${path_to_file##*.}"
  case $ext in
    jpg|JPG|mov|MOV|mp4|MP4|CR2)
      #echo "Processing $path_to_file.."
      ;;
    *) echo "$path_to_file -> skipped"; _cleanup; return;;
  esac
  stat_date=$(stat "$path_to_file" | grep -i modify | awk '{ print $2 }')
  _extract_date_from_path
  _extract_timestamp_from_filename
  if [[ (-z ${CALCULATED_TIMESTAMP+x} || ${CALCULATED_TIMESTAMP} = "-- ::") && -z ${CALCULATED_DATE+x} ]]
  then
    CALCULATED_TIMESTAMP=$(./get_image_time.py "$path_to_file" full)
    CALCULATED_DATE=$(./get_image_time.py "$path_to_file")
  fi
  if [[ (-z ${CALCULATED_TIMESTAMP} || ${CALCULATED_TIMESTAMP} = "-- ::") ]]
  then
    echo "Processing $path_to_file.."
    echo "    Could not determine the timestamp of this image.."
    _cleanup
    return
  fi

  # -- both stat and get_image_time.py will return local time w/ tz offset
  # -- filename-extracted time is also tz local

  if [[ (-n ${PATH_DATE+x} && "$PATH_DATE" != "$CALCULATED_DATE") || "$stat_date" != "$CALCULATED_DATE" ]]
  then
    echo "Processing $path_to_file.."
    _extract_descriptive_timestamp_folder
    if [[ "$stat_date" != "$CALCULATED_DATE" ]]
    then
      echo "    stat ($stat_date) does not match calculated ($CALCULATED_DATE)"
      echo "    fixing $path_to_file timestamp from $(stat "$path_to_file" | grep -i modify) to $CALCULATED_TIMESTAMP.."
      echo "touch -d $CALCULATED_TIMESTAMP $path_to_file" >> $TIMESTAMP_FIX_SCRIPT
    fi
    echo "    either stat ($stat_date) or folder date ($PATH_DATE) does not match calculated ($CALCULATED_DATE)"
    echo "    moving $path_to_file to $NEW_DIR.."
    echo "mkdir -p $NEW_DIR && mv $path_to_file $NEW_DIR" >> $TIMESTAMP_FIX_SCRIPT
  fi
  #rm -f /tmp/placeholder

  _cleanup
}

copy_from_remote_sources() {

  echo "filename: $INPUTFILE"
  echo "source: $SOURCE"
  echo "sources: ${SOURCES[@]}"

  for s in "${!SOURCES[@]}"
  do
      remote_path=${SOURCES[$s]}

      echo
      echo "Processing $remote_path.."

      # - if a file-of-files isn't provided, generate one for the source
      if [[ -z "$INPUTFILE" ]]
      then
        INPUTFILE=files_to_copy_$s.txt
        # - TODO: can we redirect the output of adb shell directly into the while read statement below?
        adb shell ls \"$remote_path\" > files_to_copy_$s.txt
        echo "  Found $(cat $INPUTFILE | wc -l) files.."
        dos2unix files_to_copy_$s.txt
      fi

      while read filename
      do
          path_to_file="$TARGET/$filename"
          if [[ ! -a "$path_to_file" ]]
          then
            # - NOTE: touch -r would be great if we could reference the actual file
            # - but it needs to be accessible within the shell
            # - and copying it manipulates the date info
            # - parse out timestamp info from filename
            echo "    Copying $remote_path/$filename.."
            # - copy file to local drive
            adb pull "$remote_path/$filename" $TARGET
          else
            echo "    $filename already exists"
          fi
          if [ $? -eq 0 ]
          then
            correct_timestamp "$path_to_file"
          fi
      done < $(echo "$INPUTFILE")

      unset INPUTFILE
      rm -f files_to_copy_$s.txt
  done
}

fix_timestamps() {
  TIMESTAMP_FIX_SCRIPT=/media/storage/pics_timestamp_fix_$(date +%Y%m%d%H%M%S).sh
  find "$WORKFOLDER" -type f > files_to_fix.txt
  echo "Writing fix commands to $TIMESTAMP_FIX_SCRIPT"
  echo "# - RUN DATE:    $(date +%Y/%m/%d %H:%M:%S)" >> $TIMESTAMP_FIX_SCRIPT
  echo "# - WORK FOLDER: $WORKFOLDER" >> $TIMESTAMP_FIX_SCRIPT
  echo "# - FILE COUNT:  $(cat files_to_fix.txt | wc -l)" >> $TIMESTAMP_FIX_SCRIPT
  echo "#" >> $TIMESTAMP_FIX_SCRIPT
  while read path_to_file
  do
    correct_timestamp "$path_to_file"
  done < $(echo files_to_fix.txt)
  rm -f files_to_fix.txt
}

if [ "$ACTION" = "copy" ]
then
  echo "Copying from remote sources.."
  mkdir -p $TARGET
  copy_from_remote_sources
  exit 0
elif [ "$ACTION" = "timestamps" ]
then
  echo "Processing folder $WORKFOLDER.."
  echo "DRY RUN: $DRYRUN"
  fix_timestamps
  exit 0
else
  echo "No action"
fi
