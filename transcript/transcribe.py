"""
Transcribe a Chinese podcast MP3 to SRT using OpenAI's Whisper API.

Usage:
    # Basic
    python3 transcribe.py episodes/美轮美换_084_V2.mp3

    # Recommended for Chinese podcasts: natural-sentence prompt
    python3 transcribe.py episodes/foo.mp3 \\
        --prompt "这是一档名叫'美轮美换'的中文政治播客，主持人小华、王浩南、Tanish。"

    # Faster: parallel chunk uploads (default 6 workers)
    python3 transcribe.py episodes/foo.mp3 --workers 6

    # Higher subtitle quality: cut at silences instead of fixed intervals
    python3 transcribe.py episodes/foo.mp3 --silence-aware

Whisper API has a 25MB upload limit, so we split the audio into chunks,
transcribe each (concurrently by default), then stitch the SRTs back
together with offset timestamps.
"""

from __future__ import annotations

import argparse
import math
import os
import re
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path

from openai import OpenAI


# Whisper hard limit is 25MB. Default to 24MB; user can override via CLI.
DEFAULT_MAX_CHUNK_BYTES = 24 * 1024 * 1024
# whisper-1 is the only OpenAI transcription model that supports
# response_format="srt". The newer gpt-4o-*-transcribe models are
# text-only — no timestamps, no SRT.
MODEL = "whisper-1"


# --------------------------------------------------------------------------- #
# Audio inspection                                                            #
# --------------------------------------------------------------------------- #

def probe_duration_seconds(audio_path: Path) -> float:
    """Use ffprobe to get the duration of an audio file in seconds."""
    out = subprocess.check_output([
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=nokey=1:noprint_wrappers=1",
        str(audio_path),
    ])
    return float(out.strip())


@dataclass
class Chunk:
    """A slice of audio scheduled for transcription.

    `start_offset_s` is where this chunk begins in the *original* audio,
    in seconds. We need it later to shift the SRT timestamps Whisper
    returns (which are always relative to the chunk's own 0:00).
    """
    path: Path
    start_offset_s: float


# --------------------------------------------------------------------------- #
# Chunking strategies                                                         #
# --------------------------------------------------------------------------- #

def _ffmpeg_slice(audio_path: Path, out: Path, start_s: float, length_s: float) -> None:
    """Stream-copy a [start, start+length] slice into `out` as MP3."""
    subprocess.run([
        "ffmpeg", "-y", "-loglevel", "error",
        "-ss", f"{start_s:.3f}",
        "-i", str(audio_path),
        "-t", f"{length_s:.3f}",
        "-c", "copy",
        str(out),
    ], check=True)


def _plan_chunk_count(file_size: int, max_bytes: int) -> int:
    """How many chunks to produce so each is reliably below max_bytes.
    10% headroom protects against MP3 bitrate variance and ID3 tags.
    """
    target_bytes = int(max_bytes * 0.9)
    return math.ceil(file_size / target_bytes)


def chunk_audio_equal_time(
    audio_path: Path, work_dir: Path, max_bytes: int,
) -> list[Chunk]:
    """Split into equal-duration chunks. Fast and deterministic."""
    file_size = audio_path.stat().st_size
    if file_size <= max_bytes:
        return [Chunk(path=audio_path, start_offset_s=0.0)]

    duration = probe_duration_seconds(audio_path)
    n_chunks = _plan_chunk_count(file_size, max_bytes)
    chunk_seconds = duration / n_chunks

    chunks: list[Chunk] = []
    for i in range(n_chunks):
        offset = i * chunk_seconds
        out = work_dir / f"chunk_{i:03d}.mp3"
        _ffmpeg_slice(audio_path, out, offset, chunk_seconds)
        chunks.append(Chunk(path=out, start_offset_s=offset))
    return chunks


_SILENCE_START = re.compile(r"silence_start:\s*([\d.]+)")
_SILENCE_END = re.compile(
    r"silence_end:\s*([\d.]+)\s*\|\s*silence_duration:\s*([\d.]+)"
)


def detect_silence_intervals(
    audio_path: Path, noise_db: int = -30, min_dur: float = 0.5,
) -> list[tuple[float, float]]:
    """Run ffmpeg silencedetect, return [(silence_start_s, silence_end_s), ...].

    `noise_db`: anything quieter than this is considered silence.
    `min_dur`: minimum silence length to report (seconds).
    """
    proc = subprocess.run(
        [
            "ffmpeg", "-i", str(audio_path),
            "-af", f"silencedetect=n={noise_db}dB:d={min_dur}",
            "-f", "null", "-",
        ],
        capture_output=True, text=True,
    )
    log = proc.stderr  # silencedetect logs to stderr
    starts = [float(m.group(1)) for m in _SILENCE_START.finditer(log)]
    ends = [float(m.group(1)) for m in _SILENCE_END.finditer(log)]
    return list(zip(starts, ends))


def chunk_audio_silence_aware(
    audio_path: Path, work_dir: Path, max_bytes: int, snap_window_s: float = 60.0,
) -> list[Chunk]:
    """Cut at the silence midpoint nearest each target boundary.

    Falls back to the exact target time if no silence sits within
    `snap_window_s` of it. Each resulting chunk is still bounded by
    `max_bytes` because we only shift cuts, not extend regions — but
    we re-validate sizes and warn if a chunk is over-budget.
    """
    file_size = audio_path.stat().st_size
    if file_size <= max_bytes:
        return [Chunk(path=audio_path, start_offset_s=0.0)]

    duration = probe_duration_seconds(audio_path)
    n_chunks = _plan_chunk_count(file_size, max_bytes)

    # Targets: evenly-spaced interior boundaries between 0 and duration.
    target_boundaries = [i * duration / n_chunks for i in range(1, n_chunks)]

    silences = detect_silence_intervals(audio_path)
    silence_midpoints = [(s + e) / 2 for s, e in silences]

    cut_points: list[float] = [0.0]
    for target in target_boundaries:
        # Find silence midpoints within snap_window_s of the target.
        candidates = [
            m for m in silence_midpoints if abs(m - target) <= snap_window_s
        ]
        if candidates:
            cut_points.append(min(candidates, key=lambda m: abs(m - target)))
        else:
            # No nearby silence; fall back to the exact target time.
            cut_points.append(target)
    cut_points.append(duration)

    chunks: list[Chunk] = []
    for i in range(len(cut_points) - 1):
        start = cut_points[i]
        length = cut_points[i + 1] - start
        out = work_dir / f"chunk_{i:03d}.mp3"
        _ffmpeg_slice(audio_path, out, start, length)
        # Sanity check: warn if a snapped chunk exceeds budget.
        if out.stat().st_size > max_bytes:
            print(
                f"[warn] chunk {i:03d} is {out.stat().st_size/1024/1024:.1f}MB "
                f"(> {max_bytes/1024/1024:.1f}MB budget) — silence shift "
                "made it too big. Whisper may reject it.",
                file=sys.stderr,
            )
        chunks.append(Chunk(path=out, start_offset_s=start))
    return chunks


# --------------------------------------------------------------------------- #
# Whisper transcription                                                       #
# --------------------------------------------------------------------------- #

def transcribe_chunk(client: OpenAI, chunk: Chunk, prompt: str | None) -> str:
    """Send one chunk to Whisper, return raw SRT text."""
    with chunk.path.open("rb") as f:
        kwargs = {
            "model": MODEL,
            "file": f,
            "response_format": "srt",
            "language": "zh",
        }
        if prompt:
            kwargs["prompt"] = prompt
        return client.audio.transcriptions.create(**kwargs)


def transcribe_concurrently(
    client: OpenAI,
    chunks: list[Chunk],
    prompt: str | None,
    max_workers: int,
) -> list[tuple[str, float]]:
    """Fan chunks out to a thread pool, return parts in original chunk order."""
    parts: list[tuple[str, float] | None] = [None] * len(chunks)
    workers = min(max_workers, len(chunks))

    if workers <= 1 or len(chunks) == 1:
        for i, ch in enumerate(chunks):
            print(f"[whisper] chunk {i+1}/{len(chunks)} → API")
            parts[i] = (transcribe_chunk(client, ch, prompt), ch.start_offset_s)
        return parts  # type: ignore[return-value]

    print(f"[whisper] {len(chunks)} chunks × {workers} workers")
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = {
            ex.submit(transcribe_chunk, client, ch, prompt): i
            for i, ch in enumerate(chunks)
        }
        completed = 0
        for fut in as_completed(futures):
            i = futures[fut]
            parts[i] = (fut.result(), chunks[i].start_offset_s)
            completed += 1
            print(f"[whisper] {completed}/{len(chunks)} done (chunk {i+1})")
    return parts  # type: ignore[return-value]


# --------------------------------------------------------------------------- #
# SRT stitching                                                               #
# --------------------------------------------------------------------------- #

# SRT timestamp regex: 00:01:23,456 --> 00:01:27,890
_TIMESTAMP_LINE = re.compile(
    r"(\d{2}):(\d{2}):(\d{2}),(\d{3})\s+-->\s+(\d{2}):(\d{2}):(\d{2}),(\d{3})"
)


def _ts_to_ms(h: str, m: str, s: str, ms: str) -> int:
    return ((int(h) * 60 + int(m)) * 60 + int(s)) * 1000 + int(ms)


def _ms_to_ts(total_ms: int) -> str:
    ms = total_ms % 1000
    s = (total_ms // 1000) % 60
    m = (total_ms // 60_000) % 60
    h = total_ms // 3_600_000
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def stitch_srt(parts: list[tuple[str, float]]) -> str:
    """Merge per-chunk SRT outputs into one re-numbered SRT.

    `parts` is a list of (srt_text, start_offset_seconds) tuples in order.
    """
    out_lines: list[str] = []
    cue_index = 1

    for srt_text, offset_s in parts:
        offset_ms = int(round(offset_s * 1000))

        # Split into cue blocks (separated by blank lines), drop the original
        # cue numbers, shift timestamps, renumber.
        for block in re.split(r"\n\s*\n", srt_text.strip()):
            lines = block.splitlines()
            if len(lines) < 2:
                continue
            # First line is the original cue number — discard. Find timestamp.
            ts_idx = 1 if _TIMESTAMP_LINE.match(lines[1] or "") else 0
            ts_match = _TIMESTAMP_LINE.match(lines[ts_idx])
            if not ts_match:
                continue
            start_ms = _ts_to_ms(*ts_match.group(1, 2, 3, 4)) + offset_ms
            end_ms = _ts_to_ms(*ts_match.group(5, 6, 7, 8)) + offset_ms
            text_lines = lines[ts_idx + 1:]

            out_lines.append(str(cue_index))
            out_lines.append(f"{_ms_to_ts(start_ms)} --> {_ms_to_ts(end_ms)}")
            out_lines.extend(text_lines)
            out_lines.append("")
            cue_index += 1

    return "\n".join(out_lines).rstrip() + "\n"


# --------------------------------------------------------------------------- #
# Entry point                                                                 #
# --------------------------------------------------------------------------- #

def load_api_key() -> str:
    if key := os.environ.get("OPENAI_API_KEY"):
        return key
    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if line.startswith("OPENAI_API_KEY="):
                return line.split("=", 1)[1].strip()
    sys.exit("OPENAI_API_KEY not set (env or transcript/.env)")


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("audio", type=Path, help="Path to MP3 audio file")
    parser.add_argument(
        "--out", type=Path, default=None,
        help="Output SRT path (default: alongside input, .srt)",
    )
    parser.add_argument(
        "--prompt", default=None,
        help="Whisper prompt. A natural-sentence prompt (with proper nouns "
             "in context) biases output far better than a bare keyword list.",
    )
    parser.add_argument(
        "--workers", type=int, default=6,
        help="Concurrent chunk uploads (default: 6)",
    )
    parser.add_argument(
        "--silence-aware", action="store_true",
        help="Cut at silence midpoints near each chunk boundary instead of "
             "at fixed intervals. Higher subtitle quality, +1 ffmpeg pass.",
    )
    parser.add_argument(
        "--max-chunk-mb", type=float, default=24.0,
        help="Max chunk size in MB (default: 24, Whisper limit is 25)",
    )
    args = parser.parse_args()

    if not args.audio.exists():
        sys.exit(f"Audio file not found: {args.audio}")

    out_path = args.out or args.audio.with_suffix(".srt")
    max_bytes = int(args.max_chunk_mb * 1024 * 1024)
    client = OpenAI(api_key=load_api_key())

    duration = probe_duration_seconds(args.audio)
    print(f"[info] {args.audio.name}: {duration/60:.1f} min, "
          f"{args.audio.stat().st_size / 1024 / 1024:.1f} MB")

    chunker = chunk_audio_silence_aware if args.silence_aware else chunk_audio_equal_time
    mode_name = "silence-aware" if args.silence_aware else "equal-time"

    with tempfile.TemporaryDirectory(prefix="transcribe_") as tmp:
        work_dir = Path(tmp)
        chunks = chunker(args.audio, work_dir, max_bytes)
        print(f"[info] {mode_name} split → {len(chunks)} chunk(s)")
        for i, ch in enumerate(chunks):
            size_mb = ch.path.stat().st_size / 1024 / 1024
            print(f"       chunk {i:03d}: {size_mb:5.1f} MB, "
                  f"starts at {ch.start_offset_s/60:6.2f} min")

        parts = transcribe_concurrently(client, chunks, args.prompt, args.workers)

    out_path.write_text(stitch_srt(parts), encoding="utf-8")
    print(f"[done] wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
