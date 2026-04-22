from enum import Enum


class DownloadFormat(str, Enum):
    TXT = "txt"
    SRT = "srt"
    VTT = "vtt"
