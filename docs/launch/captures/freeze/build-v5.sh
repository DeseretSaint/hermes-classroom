#!/usr/bin/env bash
# Walkthrough v5 — slide transitions between screens, blurred stills behind the title and end cards.
set -euo pipefail
OUT=~/.hermes/cache/scratch/ship/docs/launch/captures/freeze
WORK=$OUT/_final5; rm -rf "$WORK"; mkdir -p "$WORK"
C=$OUT/captures-src
FB=/usr/share/fonts/liberation/LiberationSans-Bold.ttf
F=/usr/share/fonts/liberation/LiberationSans-Regular.ttf
INK=0xF6F0E2
SUB=0xE0D6BF
D=6.0          # clip length
X=0.8          # xfade length
OFF=5.2        # 6.0 - 0.8

# 1. Title card over a blurred Home still
ffmpeg -y -loglevel error -loop 1 -framerate 30 -i "$C/f-home.png" \
  -filter_complex "[0:v]crop=1920:806:0:94,scale=1920:1080,boxblur=40:2,eq=brightness=-0.28:saturation=0.75,scale=1920:1080[bg];[bg]drawtext=fontfile=$FB:text='Coursebook, learn anything.':x=(w-tw)/2:y=(h/2)-40:fontsize=82:fontcolor=$INK,drawtext=fontfile=$F:text='learn anything you want, and finish it':x=(w-tw)/2:y=(h/2)+60:fontsize=36:fontcolor=$SUB,format=yuv420p[v]" \
  -map "[v]" -t $D -r 30 -c:v libx264 -preset medium -crf 17 -pix_fmt yuv420p "$WORK/00.mp4"

beat() { # src crop head sub out
  local src="$1" crop="$2" head="$3" sub="$4" out="$5"
  ffmpeg -y -loglevel error -loop 1 -framerate 30 -i "$src" \
    -filter_complex "[0:v]crop=$crop,scale=-2:840[card];[card]pad=iw+8:ih+8:4:4:color=0x2A3A31[cardb];color=c=0x141F19:s=1920x1080:r=30[bg];[bg][cardb]overlay=x=(W-w)/2:y=60[base];[base]drawtext=fontfile=$FB:text='$head':x=(w-tw)/2:y=952:fontsize=52:fontcolor=$INK,drawtext=fontfile=$F:text='$sub':x=(w-tw)/2:y=1020:fontsize=30:fontcolor=$SUB,format=yuv420p[v]" \
    -map "[v]" -t $D -r 30 -c:v libx264 -preset medium -crf 17 -pix_fmt yuv420p "$out"
}

beat "$C/f-home.png"                "1920:806:0:94"  "Your courses, ready to open."      "One tap back to where you left off."                "$WORK/01.mp4"
beat "$C/f-workshop.png"            "1920:1070:0:0"  "Learn anything."                   "Astronomy. Japanese. Repairs. Whatever you pick."   "$WORK/02.mp4"
beat "$C/course-home-772-light.png" "688:972:0:0"    "A whole course, built for you."    "Lessons, practice and a clear next step."           "$WORK/03.mp4"
beat "$C/04-lesson-top.png"         "784:838:38:36"  "A tutor who knows the lesson."     "Ask anything, right where you are reading."         "$WORK/04.mp4"
beat "$C/07-answer.png"             "784:520:38:36"  "Short checks that make it stick."  "Answer, and keep moving."                           "$WORK/05.mp4"
beat "$C/parent-guide.png"          "1190:1684:0:0"  "Printables for your kids."         "Parent mode turns a lesson into real work."         "$WORK/06.mp4"

# 7. End card over a blurred lesson still
ffmpeg -y -loglevel error -loop 1 -framerate 30 -i "$C/04-lesson-top.png" \
  -filter_complex "[0:v]crop=784:838:38:36,scale=1920:1080,boxblur=40:2,eq=brightness=-0.3:saturation=0.7[bg];[bg]drawtext=fontfile=$FB:text='Coursebook, learn anything.':x=(w-tw)/2:y=(h/2)-150:fontsize=84:fontcolor=$INK,drawtext=fontfile=$F:text='textbook, game and parent modes':x=(w-tw)/2:y=(h/2)-40:fontsize=36:fontcolor=$SUB,drawtext=fontfile=$F:text='export a course as a pack; a storefront is coming':x=(w-tw)/2:y=(h/2)+20:fontsize=28:fontcolor=0xB9C7B4,drawtext=fontfile=$F:text='github.com/DeseretSaint/hermes-classroom':x=(w-tw)/2:y=(h/2)+92:fontsize=32:fontcolor=0xB9C7B4,drawtext=fontfile=$FB:text='MIT':x=(w-tw)/2:y=(h/2)+158:fontsize=28:fontcolor=0x8FA08C,format=yuv420p[v]" \
  -map "[v]" -t $D -r 30 -c:v libx264 -preset medium -crf 17 -pix_fmt yuv420p "$WORK/07.mp4"

# Chain with slide-left transitions
ffmpeg -y -loglevel error \
  -i "$WORK/00.mp4" -i "$WORK/01.mp4" -i "$WORK/02.mp4" -i "$WORK/03.mp4" \
  -i "$WORK/04.mp4" -i "$WORK/05.mp4" -i "$WORK/06.mp4" -i "$WORK/07.mp4" \
  -filter_complex "[0][1]xfade=transition=slideleft:duration=$X:offset=$OFF[a];[a][2]xfade=transition=slideleft:duration=$X:offset=10.4[b];[b][3]xfade=transition=slideleft:duration=$X:offset=15.6[c];[c][4]xfade=transition=slideleft:duration=$X:offset=20.8[d];[d][5]xfade=transition=slideleft:duration=$X:offset=26.0[e];[e][6]xfade=transition=slideleft:duration=$X:offset=31.2[f];[f][7]xfade=transition=slideleft:duration=$X:offset=36.4,format=yuv420p[v]" \
  -map "[v]" -r 30 -c:v libx264 -preset medium -crf 18 -pix_fmt yuv420p -movflags +faststart "$OUT/coursebook-demo-v5.mp4"
ffprobe -v error -show_entries format=duration,size -show_entries stream=width,height,r_frame_rate -of default=noprint_wrappers=1 "$OUT/coursebook-demo-v5.mp4"
