import {Config} from '@remotion/cli/config';

// §7: H.264 High, yuv420p, deterministic frames. PNG frames keep display type
// and 1–2 px rules crisp instead of letting JPEG ringing smear them.
Config.setVideoImageFormat('png');
Config.setCodec('h264');
Config.setPixelFormat('yuv420p');
Config.setOverwriteOutput(true);
Config.setConcurrency(8);
