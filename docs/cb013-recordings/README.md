# CB-013 recordings — what each file is, and what it is not

`01-live-route-navigation.mp4` — **a real live capture.** 124 frames taken from the isolated
window's renderer through CDP (`Page.captureScreenshot`, JPEG q72) at 5 fps for 24.8 s, assembled at
the same rate with ffmpeg, 944x688. It shows the window being driven toward the Coursebook route
(`#/coursebook` set, sidebar entry clicked, `pane-flow` start) and the shell returning the session
home instead of the Coursebook page. That is the mount flake filed as `t_bfe339b2`; the recording is
evidence of the defect, **not** of the five pane states.

`02-five-state-stills-sequence.mp4` — **not a screen recording.** It is a 2 s-per-slide sequence of
the seven stills captured live in run 52 (route, approved-plan section page, awaiting_input, graded
pass, needs_retry, overridden, detached). It exists so a reviewer can step through the captured
states in one file; each slide is the untouched PNG from `docs/cb013-shots/`.

The five-state movie the card asks for cannot be captured in this topology until the route mount is
deterministic again (`t_bfe339b2`). Capturing it against the operator's packaged window would be
wrong: that window runs the root profile and a different plugin tree.
