from pathlib import Path

import yt_dlp

from app.lib.youtube.video_info import VideoInfo

FORMAT = ("bv*[height<=1080][vcodec^=avc1]+ba[ext=m4a]/bv*[height<=1080][ext=mp4]+ba[ext=m4a]"
          "/bv*[height<=1080]+ba/b[height<=1080]/b")


class DownloadVideo:
    def __init__(self, cookies_file: str = ""):
        self.cookies_file = cookies_file

    def execute(self, url: str, directory: Path) -> VideoInfo:
        directory.mkdir(parents=True, exist_ok=True)
        options = {"quiet": True, "no_warnings": True, "noprogress": True, "format": FORMAT,
                   "merge_output_format": "mp4", "outtmpl": str(directory / "source.%(ext)s")}
        if self.cookies_file:
            options["cookiefile"] = self.cookies_file
        with yt_dlp.YoutubeDL(options) as ydl:
            info = ydl.sanitize_info(ydl.extract_info(url, download=True))
        path = next(directory.glob("source.mp4"), None) or next(directory.glob("source.*"))
        return VideoInfo(id=info.get("id", ""), title=info.get("title", ""),
                         channel=info.get("channel") or info.get("uploader") or "",
                         duration_s=float(info.get("duration") or 0), language=info.get("language"), path=path,
                         automatic_captions=info.get("automatic_captions") or {},
                         subtitles=info.get("subtitles") or {})
