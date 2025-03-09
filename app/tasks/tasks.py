import os
import ffmpeg
from app.tasks.celery_app import app as celery_app
from minio import Minio
import openai
import glob
from dotenv import load_dotenv

# Docker 환경인지 확인
IS_DOCKER = os.getenv("IS_DOCKER", "false").lower() == "true"

if not IS_DOCKER:
    load_dotenv()  # 로컬 개발 환경에서는 .env 파일 로드

# MinIO 설정
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY")
MINIO_BUCKET_NAME = os.getenv("MINIO_BUCKET_NAME")

minio_client = Minio(
    MINIO_ENDPOINT,
    access_key=MINIO_ACCESS_KEY,
    secret_key=MINIO_SECRET_KEY,
    secure=False
)

# OpenAI API Key 설정
openai.api_key = os.getenv("OPENAI_API_KEY")

@celery_app.task
def convert_and_transcribe(file_name):
    """
    MinIO에서 WebM 파일을 가져와 WAV로 변환 후 Whisper API로 텍스트 변환하는 Celery Task
    긴 오디오는 일정한 길이로 나눈 후 개별적으로 Whisper API에 전송.
    """
    webm_path = f"./recordings/{file_name}.webm"
    wav_path = f"./recordings/{file_name}.wav"
    output_dir = f"./recordings/{file_name}_chunks/"

    # MinIO에서 WebM 다운로드
    minio_client.fget_object(MINIO_BUCKET_NAME, f"{file_name}.webm", webm_path)

    # WebM -> WAV 변환 (ffmpeg-python 사용)
    ffmpeg.input(webm_path).output(
        wav_path, 
        acodec="pcm_s16le", ac=1, ar="44100"
    ).run(overwrite_output=True)

    # WAV 파일을 일정 길이(예: 30초)로 나누기
    os.makedirs(output_dir, exist_ok=True)
    chunk_pattern = os.path.join(output_dir, f"{file_name}_%03d.wav")
    ffmpeg.input(wav_path).output(
        chunk_pattern, f="segment", segment_time="30", c="copy"
    ).run(overwrite_output=True)

    # 생성된 청크 파일 리스트 가져오기
    chunk_files = sorted(glob.glob(os.path.join(output_dir, "*.wav")))

    # Whisper API로 각 오디오 청크를 변환
    full_transcription = ""
    for chunk in chunk_files:
        try:
            with open(chunk, "rb") as audio_file:
                response = openai.Audio.transcribe(
                    model="whisper-1",
                    file=audio_file
                )
            transcript = response.get("text", "")
            full_transcription += transcript + " "

        except Exception as e:
            print(f"❌ Error transcribing chunk {chunk}: {e}")

    return full_transcription.strip()
