#!/bin/bash

create_desc() {
  echo "top: $test"
  local test="local"
  echo "create_desc \$1: \"$1\""
  LAST="${SUBJECT##$BASE}"
  echo LAST: $LAST
  MIDDLE="${LAST%%$(basename "$SUBJECT")}"
  echo MIDDLE: $MIDDLE
  DATE="$(echo "$MIDDLE" | egrep -o "/[[:digit:]]{4}/[[:digit:]]{4}-[[:digit:]]{2}-[[:digit:]]{2}")"
  echo DATE: $DATE
  ALLBUTDATE="$(echo ${MIDDLE/$DATE/} | egrep -o "[[:alnum:]]*")"
  echo ALLBUTDATE: $ALLBUTDATE
  DESC="${ALLBUTDATE//[[:space:]]/_}"
  echo DESC: $DESC
}

SUBJECT="$1"
BASE=/media/storage/pics

create_desc "YOOHOO"
create_desc "WOWO"

echo "back out \$1: \"$1\""

echo $DESC
