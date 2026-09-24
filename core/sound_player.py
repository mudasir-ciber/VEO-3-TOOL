"""Windows native sound generator and player for success and failure notifications."""
import sys
import threading
import math
import struct
import io
import wave
from typing import Optional

try:
    import winsound
    HAS_WINSOUND = True
except ImportError:
    HAS_WINSOUND = False


class SoundPlayer:
    """Non-blocking Windows native sound player."""

    @staticmethod
    def _create_wav(tones: list[tuple[float, float]], sample_rate: int = 44100) -> bytes:
        """
        Generate in-memory WAV bytes for given list of (freq_hz, duration_sec).
        Applies smooth attack and decay envelopes to prevent clicking.
        """
        raw_samples = []
        for freq, duration in tones:
            num_samples = int(sample_rate * duration)
            for i in range(num_samples):
                # Envelope: 5% attack, 10% decay
                envelope = 1.0
                attack_len = int(num_samples * 0.05)
                decay_len = int(num_samples * 0.15)
                if i < attack_len:
                    envelope = i / max(1, attack_len)
                elif i > num_samples - decay_len:
                    envelope = (num_samples - i) / max(1, decay_len)

                # Sine wave
                val = math.sin(2.0 * math.pi * freq * (i / sample_rate))
                sample = int(val * envelope * 24000)  # comfortable volume
                raw_samples.append(sample)

        buf = io.BytesIO()
        with wave.open(buf, 'wb') as wav:
            wav.setnchannels(1)  # Mono
            wav.setsampwidth(2)  # 16-bit
            wav.setframerate(sample_rate)
            data = struct.pack(f"<{len(raw_samples)}h", *raw_samples)
            wav.writeframes(data)
        return buf.getvalue()

    @classmethod
    def play_success(cls):
        """
        Pleasant ascending celebratory chime (C5 -> E5 -> G5 -> C6).
        Played asynchronously so it does not block the application.
        """
        if not HAS_WINSOUND:
            return

        def _play():
            try:
                # C5 (523Hz), E5 (659Hz), G5 (784Hz), C6 (1046Hz)
                tones = [
                    (523.25, 0.12),
                    (659.25, 0.12),
                    (783.99, 0.15),
                    (1046.50, 0.35)
                ]
                wav_bytes = cls._create_wav(tones)
                winsound.PlaySound(wav_bytes, winsound.SND_MEMORY)
            except Exception:
                # Fallback to beep if wave play fails
                try:
                    for freq, dur in [(523, 100), (659, 100), (784, 120), (1046, 300)]:
                        winsound.Beep(freq, dur)
                except Exception:
                    pass

        threading.Thread(target=_play, daemon=True).start()

    @classmethod
    def play_failure(cls):
        """
        Distinct descending alert chime (F#4 -> D4 -> C4).
        Played asynchronously.
        """
        if not HAS_WINSOUND:
            return

        def _play():
            try:
                tones = [
                    (370.0, 0.18),
                    (293.6, 0.18),
                    (220.0, 0.40)
                ]
                wav_bytes = cls._create_wav(tones)
                winsound.PlaySound(wav_bytes, winsound.SND_MEMORY)
            except Exception:
                try:
                    for freq, dur in [(370, 180), (294, 180), (220, 400)]:
                        winsound.Beep(freq, dur)
                except Exception:
                    pass

        threading.Thread(target=_play, daemon=True).start()


if __name__ == "__main__":
    import time
    print("Testing Success sound...")
    SoundPlayer.play_success()
    time.sleep(1.5)
    print("Testing Failure sound...")
    SoundPlayer.play_failure()
    time.sleep(1.5)
    print("Sound tests completed.")
