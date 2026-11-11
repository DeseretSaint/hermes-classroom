#!/usr/bin/env bash
# Compose the submission film from stamped frames only (pane captures, module 98400108).
set -euo pipefail
cd "$(dirname "$0")"
WORK=./_film2
rm -rf "$WORK"; mkdir -p "$WORK"
F=/usr/share/fonts/liberation/LiberationSans-Regular.ttf
FB=/usr/share/fonts/liberation/LiberationSans-Bold.ttf

beat() { # img title subtitle out
  local img="$1" title="$2" sub="$3" out="$4"
  ffmpeg -y -loglevel error -loop 1 -i "$img" \
    -f lavfi -i "color=c=0x1E2A24:s=1920x1080:d=9:r=30" \
    -filter_complex "\
[0:v]scale=-2:960[shot];\
[1:v][shot]overlay=x=980:y=(H-h)/2[base];\
[base]drawtext=fontfile=$FB:text='$title':x=110:y=430:fontsize=62:fontcolor=0xF3EDDF,\
drawtext=fontfile=$F:text='$sub':x=112:y=520:fontsize=34:fontcolor=0xC9BFa8,\
drawtext=fontfile=$F:text='Coursebook':x=112:y=120:fontsize=26:fontcolor=0x8FA08C,\
fade=t=in:st=0:d=0.45" \
    -t 9 -r 30 -pix_fmt yuv420p -c:v libx264 -preset medium -crf 18 "$out"
}

beat pane/home-pane-light.png     "Home"        "Pick a course, or start a new expedition"      "$WORK/01.mp4"
beat pane/courses-pane-light.png  "Courses"     "Your field library, with real progress"         "$WORK/02.mp4"
beat pane/workshop-pane-light.png "Workshop"    "Packs on this device, previewed first"          "$WORK/03.mp4"
beat course-home-772-light.png    "Course home" "The plan, then the next real step"              "$WORK/04.mp4"
beat pane/studio-pane-light.png   "Parent Studio" "The lesson a parent prepares"                 "$WORK/05.mp4"

ffmpeg -y -loglevel error -f lavfi -i "color=c=0x1E2A24:s=1920x1080:d=7:r=30" \
  -vf "drawtext=fontfile=$FB:text='Coursebook':x=(w-tw)/2:y=(h/2)-120:fontsize=104:fontcolor=0xF3EDDF,\
drawtext=fontfile=$F:text='a local-first study plugin for Hermes Agent':x=(w-tw)/2:y=(h/2)-10:fontsize=40:fontcolor=0xD9CFB8,\
drawtext=fontfile=$F:text='github.com/DeseretSaint/hermes-classroom':x=(w-tw)/2:y=(h/2)+90:fontsize=34:fontcolor=0xB9C7B4,\
drawtext=fontfile=$F:text='build 172b61aa  -  module 98400108':x=(w-tw)/2:y=(h/2)+155:fontsize=26:fontcolor=0x8FA08C,\
fade=t=in:st=0:d=0.6" -pix_fmt yuv420p -c:v libx264 -preset medium -crf 18 "$WORK/06.mp4"

printf "file '%s'\n" "$(pwd)"/_film2/0{1,2,3,4,5,6}.mp4 > "$WORK/list.txt"
ffmpeg -y -loglevel error -f concat -safe 0 -i "$WORK/list.txt" -c:v libx264 -preset medium -crf 20 -pix_fmt yuv420p -movflags +faststart coursebook-demo.mp4
ffprobe -v error -show_entries format=duration,size -show_entries stream=width,height -of default=noprint_wrappers=1 coursebook-demo.mp4
