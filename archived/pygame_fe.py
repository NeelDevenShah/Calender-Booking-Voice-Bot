import sounddevice as sd
import numpy as np
import wave
import requests
import pygame
import time
from scipy.io.wavfile import write

# API endpoint
API_URL = "http://127.0.0.1:5001/api/voice"

# Audio settings
SAMPLE_RATE = 44100
CHANNELS = 1
dtype = np.int16
SILENCE_THRESHOLD = 70  # Adjust based on environment
SILENCE_DURATION = 0.4  # Seconds of silence to stop recording
MIN_SPEECH_THRESHOLD = 100  # Initial value, will be calibrated
MIN_AUDIO_DURATION = .15  # Minimum duration in seconds for valid speech

def calibrate_noise_threshold(duration=3):
    """
    Calibrates the noise threshold by listening to the background noise.
    Returns an appropriate threshold for speech detection.
    """
    print("Calibrating microphone... Please remain silent for", duration, "seconds.")
    
    # Record ambient noise
    frames = []
    chunk_size = int(SAMPLE_RATE * 0.1)  # 100ms chunks
    for _ in range(int(duration / 0.1)):
        chunk = sd.rec(chunk_size, samplerate=SAMPLE_RATE, channels=CHANNELS, dtype=dtype)
        sd.wait()
        frames.append(chunk)
    
    # Calculate noise statistics
    audio_data = np.concatenate(frames, axis=0)
    mean_noise = np.abs(audio_data).mean()
    max_noise = np.abs(audio_data).max()
    std_noise = np.abs(audio_data).std()
    
    # Set thresholds based on noise statistics
    global SILENCE_THRESHOLD, MIN_SPEECH_THRESHOLD
    SILENCE_THRESHOLD = mean_noise * 1.2  # 20% above mean noise level
    MIN_SPEECH_THRESHOLD = mean_noise * 2.5  # 2.5x mean noise level
    
    print(f"Calibration complete:")
    print(f"Background noise level: mean={mean_noise:.2f}, max={max_noise:.2f}, std={std_noise:.2f}")
    print(f"SILENCE_THRESHOLD set to: {SILENCE_THRESHOLD:.2f}")
    print(f"MIN_SPEECH_THRESHOLD set to: {MIN_SPEECH_THRESHOLD:.2f}")
    print("\n--- Ready! You can start talking now ---\n")
    
    return SILENCE_THRESHOLD, MIN_SPEECH_THRESHOLD


def record_audio(filename="input.wav", max_duration=10):
    """Records audio and stops automatically when silence is detected."""
    print("Recording...")
    buffer = []
    silent_chunks = 0
    chunk_size = int(SAMPLE_RATE * 0.1)  # 100ms chunks

    def is_silent(data):
        print(np.abs(data).mean())
        return np.abs(data).mean() < SILENCE_THRESHOLD

    for _ in range(int(max_duration / 0.1)):
        chunk = sd.rec(chunk_size, samplerate=SAMPLE_RATE, channels=CHANNELS, dtype=dtype)
        sd.wait()
        buffer.append(chunk)
        
        if is_silent(chunk):
            silent_chunks += 1
        else:
            silent_chunks = 0
        print(silent_chunks, SILENCE_DURATION / 0.1)
        if silent_chunks > (SILENCE_DURATION / 0.1):
            break
    
    print("Recording stopped.")
    audio_data = np.concatenate(buffer, axis=0)
    write(filename, SAMPLE_RATE, audio_data)
    return filename


def send_audio(file_path):
    """Sends recorded audio to API and returns response."""
    with open(file_path, "rb") as f:
        response = requests.post(API_URL, files={"file": f})
    
    if response.status_code == 200:
        print("Got successfull response")
        return response.json().get("audio_url")
    else:
        print("Error in API response:", response.text)
        return None

# For cloud based solution
# def play_audio(file_url):
#     """Downloads and plays the audio from the given URL."""
#     response = requests.get(file_url)
#     if response.status_code == 200:
#         with open("response.wav", "wb") as f:
#             f.write(response.content)
        
#         pygame.mixer.init()
#         pygame.mixer.music.load("response.wav")
#         pygame.mixer.music.play()
        
#         while pygame.mixer.music.get_busy():
#             time.sleep(0.1)
#     else:
#         print("Error downloading audio response.")

def play_audio(file_path):
    """Plays the audio from the given local file path."""
    print('Playing the audio')
    pygame.mixer.init()
    pygame.mixer.music.load(file_path)
    pygame.mixer.music.play()
    
    while pygame.mixer.music.get_busy():
        time.sleep(0.1)
    
    time.sleep(0.5)


def has_sufficient_content(file_path):
    """
    Checks if the audio file has enough content above the silence threshold.
    Returns True if sufficient speech is detected, False otherwise.
    """
    with wave.open(file_path, 'rb') as wf:
        n_frames = wf.getnframes()
        framerate = wf.getframerate()
        audio_data = np.frombuffer(wf.readframes(n_frames), dtype=np.int16)
        
        # Calculate audio duration in seconds
        duration = n_frames / framerate
        
        # Calculate percentage of audio above threshold
        above_threshold = np.sum(np.abs(audio_data) > SILENCE_THRESHOLD)
        total_samples = len(audio_data)
        
        if total_samples == 0:
            return False
            
        percentage_speech = (above_threshold / total_samples) * 100
        # mean_amplitude = np.abs(audio_data).mean()
        
        # Calculate frames with significant voice activity
        voice_frames = np.sum(np.abs(audio_data) > MIN_SPEECH_THRESHOLD)
        voice_duration = voice_frames / framerate
        
        # print(f"Speech percentage: {percentage_speech:.2f}%, Mean amplitude: {mean_amplitude:.2f}")
        print(f"Audio duration: {duration:.2f}s, Voice duration: {voice_duration:.2f}s")
        
        # Check for all criteria:
        # 1. Enough percentage of speech
        # 2. Sufficient mean amplitude
        # 3. Minimum duration of voice activity
        
        print('%%%%%%%%%%%%%%%%%%%%%%%%%%%%')
        print(voice_duration, MIN_AUDIO_DURATION)
        # print(mean_amplitude, MIN_SPEECH_THRESHOLD)
        print('%%%%%%%%%%%%%%%%%%%%%%%%%%%%')
        
        return (percentage_speech > 8 and voice_duration >= MIN_AUDIO_DURATION)


def voice_loop():
    """Runs the continuous voice-to-voice chatbot interaction."""
    while True:
        audio_file = record_audio()
        
        # Check if recorded audio has sufficient content before making API call
        if has_sufficient_content(audio_file):
            print("Sufficient speech detected, sending to API...")
            response_audio_url = send_audio(audio_file)
            if response_audio_url:
                play_audio(response_audio_url)
        else:
            print("Not enough speech detected, skipping API call.")
            # Optional: Play a notification sound or provide feedback


if __name__ == "__main__":
    # Calibrate microphone once at startup
    calibrate_noise_threshold()
    voice_loop()