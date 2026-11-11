#!/usr/bin/env bash
set -euo pipefail
OUT=~/.hermes/cache/scratch/ship/docs/launch/captures/freeze
WORK=$OUT/_final4; rm -rf "$WORK"; mkdir -p "$WORK"
C=$OUT/captures-src
FB=/usr/share/fonts/liberation/LiberationSans-Bold.ttf
F=/usr/share/fonts/liberation/LiberationSans-Regular.ttf
C0=0x1C3126
C1=0x0A1310
INK=0xF6F0E2
SUB=0xCFC5AE

beat() { # src crop head sub secs fadestart out
  local src="$1" crop="$2" head="$3" sub="$4" secs="$5" fs="$6" out="$7"
  ffmpeg -y -loglevel error -loop 1 -framerate 30 -i "$src" \
    -f lavfi -i "gradients=s=1920x1080:c0=$C0:c1=$C1:x0=260:y0=0:x1=1660:y1=1160:speed=0.006:d=$secs:r=30" \
    -filter_complex "[0:v]crop=$crop,scale=-2:820[card];[card]pad=iw+6:ih+6:3:3:color=0x40564A[cardb];[1:v][cardb]overlay=x=(W-w)/2:y=64:shortest=1,scale=3840:2160,zoompan=z='min(1.025,1.0+0.00035*on)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s=1920x1080:fps=30[base];[base]drawtext=fontfile=$FB:text='$head':x=(w-tw)/2:y=930:fontsize=48:fontcolor=$INK,drawtext=fontfile=$F:text='$sub':x=(w-tw)/2:y=996:fontsize=29:fontcolor=$SUB,fade=t=in:st=0:d=0.4,fade=t=out:st=$fs:d=0.4,format=yuv420p[v]" \
    -map "[v]" -t "$secs" -r 30 -c:v libx264 -preset medium -crf 17 -pix_fmt yuv420p "$out"
}

ffmpeg -y -loglevel error -f lavfi -i "gradients=s=1920x1080:c0=$C0:c1=$C1:x0=200:y0=0:x1=1700:y1=1100:speed=0.02:d=3.5:r=30" \
  -vf "drawtext=fontfile=$FB:text='Learn anything.':x=(w-tw)/2:y=(h/2)-30:fontsize=96:fontcolor=$INK,drawtext=fontfile=$F:text='Coursebook for Hermes Desktop':x=(w-tw)/2:y=(h/2)+90:fontsize=38:fontcolor=$SUB,fade=t=in:st=0:d=0.45,fade=t=out:st=2.95:d=0.55,format=yuv420p" \
  -t 3.5 -r 30 -c:v libx264 -preset medium -crf 17 -pix_fmt yuv420p "$WORK/00.mp4"

beat "$C/f-home.png"                "1920:900:0:0"  "Your field library."            "Every course keeps its own sources and progress."       7.0 6.6 "$WORK/01.mp4"
beat "$C/f-workshop.png"            "1920:1070:0:0" "Turn any topic into a course."  "Generated inside Hermes, with real research behind it." 7.0 6.6 "$WORK/02.mp4"
beat "$C/course-home-772-light.png" "688:972:0:0"   "A plan before a lesson."        "Read it, approve it, and the course begins."            7.0 6.6 "$WORK/03.mp4"
beat "$C/04-lesson-top.png"         "784:838:38:36" "A tutor beside the lesson."     "Ask anything; the answer cites the page you are reading."      7.0 6.6 "$WORK/04.mp4"
beat "$C/07-answer.png"             "784:520:38:36" "Graded against what it taught." "One answer, one transition, one durable row."           6.5 6.1 "$WORK/05.mp4"
beat "$C/parent-guide.png"          "1190:1684:0:0" "Parent mode."                   "Printables and activities, ready to hand over."         6.0 5.6 "$WORK/06.mp4"

ffmpeg -y -loglevel error -f lavfi -i "gradients=s=1920x1080:c0=$C0:c1=$C1:x0=1400:y0=0:x1=300:y1=1080:speed=0.015:d=7:r=30" \
  -vf "drawtext=fontfile=$FB:text='Coursebook':x=(w-tw)/2:y=(h/2)-190:fontsize=108:fontcolor=$INK,drawtext=fontfile=$F:text='textbook, game and parent modes':x=(w-tw)/2:y=(h/2)-76:fontsize=38:fontcolor=0xD9CFB8,drawtext=fontfile=$F:text='export a course as a pack; a storefront is on the way':x=(w-tw)/2:y=(h/2)-10:fontsize=30:fontcolor=0xA9B8A4,drawtext=fontfile=$F:text='github.com/DeseretSaint/hermes-classroom':x=(w-tw)/2:y=(h/2)+74:fontsize=34:fontcolor=0xB9C7B4,drawtext=fontfile=$FB:text='MIT':x=(w-tw)/2:y=(h/2)+150:fontsize=30:fontcolor=0x8FA08C,drawtext=fontfile=$F:text='rendered from the real plugin':x=(w-tw)/2:y=(h/2)+216:fontsize=23:fontcolor=0x72856D,fade=t=in:st=0:d=0.55,fade=t=out:st=6.45:d=0.55,format=yuv420p" \
  -t 7 -r 30 -c:v libx264 -preset medium -crf 17 -pix_fmt yuv420p "$WORK/07.mp4"

printf "file '%s'\n" "$WORK"/0{0,1,2,3,4,5,6,7}.mp4 > "$WORK/list.txt"
ffmpeg -y -loglevel error -f concat -safe 0 -i "$WORK/list.txt" \
  -c:v libx264 -preset medium -crf 18 -pix_fmt yuv420p -movflags +faststart "$OUT/coursebook-demo-v3.mp4"
ffprobe -v error -show_entries format=duration,size -show_entries stream=width,height,r_frame_rate -of default=noprint_wrappers=1 "$OUT/coursebook-demo-v3.mp4"
