#!/usr/bin/env bash
# Coursebook submission film — built from real captures of module 98400108 (build c4fe2d63).
# 1920x1080, 30 fps, H.264, yuv420p, faststart. Silent by design: X autoplays muted and every
# beat is legible without sound. Captions sit below the capture card, never over it.
set -euo pipefail
OUT=~/Projects/hermes-classroom/docs/launch/captures/freeze
WORK=$OUT/_final; rm -rf "$WORK"; mkdir -p "$WORK"
C=$OUT/captures-src
FB=/usr/share/fonts/liberation/LiberationSans-Bold.ttf
F=/usr/share/fonts/liberation/LiberationSans-Regular.ttf
BG=0x16261D
INK=0xF3EDDF
SUB=0xC9BFA8
SECS=8

beat() { # src crop headline subline out
  local src="$1" crop="$2" head="$3" sub="$4" out="$5"
  ffmpeg -y -loglevel error -loop 1 -framerate 30 -i "$src" \
    -f lavfi -i "color=c=$BG:s=1920x1080:r=30:d=$SECS" \
    -filter_complex "[0:v]crop=$crop,scale=-2:840[card];\
[card]pad=iw+4:ih+4:2:2:color=0x3B4B3F[cardb];\
[1:v][cardb]overlay=x=(W-w)/2:y=56:shortest=1[base];\
[base]drawtext=fontfile=$FB:text='$head':x=(w-tw)/2:y=946:fontsize=46:fontcolor=$INK,\
drawtext=fontfile=$F:text='$sub':x=(w-tw)/2:y=1010:fontsize=28:fontcolor=$SUB,\
fade=t=in:st=0:d=0.45,fade=t=out:st=7.55:d=0.45,\
format=yuv420p[v]" \
    -map "[v]" -t $SECS -r 30 -c:v libx264 -preset slow -crf 17 -pix_fmt yuv420p "$out"
}

beat "$C/home-1833-light.png"       "1634:995:0:0"  "Your field library."                  "Pick a course, or start a new expedition."      "$WORK/01.mp4"
beat "$C/courses-1833-light.png"    "1634:995:0:0"  "Every course keeps its own record."   "Sources, progress, and what is due."            "$WORK/02.mp4"
beat "$C/course-home-772-light.png" "688:985:0:0"    "The plan is the spine."               "Read it, then approve it so lessons can start." "$WORK/03.mp4"
beat "$C/04-lesson-top.png"         "784:856:38:36"  "One objective at a time."             "Four objectives, one trail, one next step."     "$WORK/04.mp4"
beat "$C/07-answer.png"             "784:856:38:36"  "A typed check, graded against the objective."         "Graded against what the lesson asked, not the chat."        "$WORK/05.mp4"

ffmpeg -y -loglevel error -f lavfi -i "color=c=$BG:s=1920x1080:r=30:d=7" \
  -vf "drawtext=fontfile=$FB:text='Coursebook':x=(w-tw)/2:y=(h/2)-150:fontsize=104:fontcolor=$INK,\
drawtext=fontfile=$F:text='a local-first study plugin for Hermes Agent':x=(w-tw)/2:y=(h/2)-30:fontsize=40:fontcolor=0xD9CFB8,\
drawtext=fontfile=$F:text='github.com/DeseretSaint/hermes-classroom':x=(w-tw)/2:y=(h/2)+70:fontsize=34:fontcolor=0xB9C7B4,\
drawtext=fontfile=$FB:text='MIT':x=(w-tw)/2:y=(h/2)+150:fontsize=30:fontcolor=0x8FA08C,\
drawtext=fontfile=$F:text='captured from the real plugin  -  build c4fe2d63':x=(w-tw)/2:y=(h/2)+212:fontsize=22:fontcolor=0x6F7F6B,\
fade=t=in:st=0:d=0.6,fade=t=out:st=6.4:d=0.6,format=yuv420p" \
  -t 7 -r 30 -c:v libx264 -preset slow -crf 17 -pix_fmt yuv420p "$WORK/06.mp4"

printf "file '%s'\n" "$WORK"/0{1,2,3,4,5,6}.mp4 > "$WORK/list.txt"
ffmpeg -y -loglevel error -f concat -safe 0 -i "$WORK/list.txt" \
  -c:v libx264 -preset slow -crf 18 -pix_fmt yuv420p -movflags +faststart "$OUT/coursebook-demo-90s.mp4"
echo "--- ffprobe ---"
ffprobe -v error -show_entries format=duration,size,format_name -show_entries stream=codec_name,width,height,r_frame_rate,pix_fmt -of default=noprint_wrappers=1 "$OUT/coursebook-demo-90s.mp4"
