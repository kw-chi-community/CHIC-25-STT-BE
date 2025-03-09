from fastapi import APIRouter, WebSocket
from starlette.websockets import WebSocketState
import os
import openai
import uuid
import subprocess
from dotenv import load_dotenv
from minio import Minio
from celery_app import celery_app
from celery import shared_task

# Docker 환경인지 확인
IS_DOCKER = os.getenv("IS_DOCKER", "false").lower() == "true"

if not IS_DOCKER:
    load_dotenv()  # 로컬 개발 환경에서는 .env 파일 로드

# APIRouter 생성
audio_router = APIRouter()

# 저장 경로 설정
SAVE_PATH = "./recordings"
os.makedirs(SAVE_PATH, exist_ok=True)

# OpenAI API 키 설정 (환경 변수에서 로드)
openai.api_key = os.getenv("OPENAI_API_KEY")

# MinIO 설정
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY")
MINIO_BUCKET_NAME = os.getenv("MINIO_BUCKET_NAME")

minio_client = Minio(
    MINIO_ENDPOINT.replace("http://", "").replace("https://", ""),  # 프로토콜 제거
    access_key=MINIO_ACCESS_KEY,
    secret_key=MINIO_SECRET_KEY,
    secure=False
)

# MinIO 버킷 존재 확인 및 생성
if not minio_client.bucket_exists(MINIO_BUCKET_NAME):
    minio_client.make_bucket(MINIO_BUCKET_NAME)

def convert_webm_to_wav(input_path, output_path):
    """
    ffmpeg를 사용하여 WebM 파일을 PCM 16bit 44.1kHz WAV 파일로 변환
    """
    command = [
        "ffmpeg", "-y", "-i", input_path, "-acodec", "pcm_s16le", "-ac", "1", "-ar", "44100", output_path
    ]
    try:
        subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        print(f"✅ Converted WebM to WAV: {output_path}")
    except subprocess.CalledProcessError as e:
        print(f"❌ Error converting WebM to WAV: {e}")

def transcribe_audio(audio_path):
    """
    Whisper API를 사용해 오디오 파일을 텍스트로 변환
    """
    try:
        with open(audio_path, "rb") as audio_file:
            response = openai.Audio.transcribe(
                model="whisper-1",
                file=audio_file
            )
        return response.get("text", "")
    except Exception as e:
        print(f"❌ Error during transcription: {e}")
        return "Transcription failed."

def upload_to_minio(file_path, file_name):
    """
    MinIO에 파일 업로드 후 로컬 파일 삭제
    """
    try:
        minio_client.fput_object(MINIO_BUCKET_NAME, file_name, file_path)
        print(f"✅ Uploaded {file_name} to MinIO")
        os.remove(file_path)
        print(f"🗑️ Deleted local file: {file_path}")
    except Exception as e:
        print(f"❌ Error uploading to MinIO: {e}")

@shared_task
def process_audio_task(file_id):
    webm_file_path = os.path.join(SAVE_PATH, f"{file_id}.webm")
    wav_file_path = os.path.join(SAVE_PATH, f"{file_id}.wav")

    # WebM -> WAV 변환
    convert_webm_to_wav(webm_file_path, wav_file_path)

    # Whisper API를 사용해 오디오를 텍스트로 변환
    transcription = transcribe_audio(wav_file_path)
    print(f"📝 Transcription: {transcription}")

    # WAV 파일 MinIO 업로드 및 삭제
    upload_to_minio(wav_file_path, f"{file_id}.wav")

    # WebM 파일 삭제
    if os.path.exists(webm_file_path):
        os.remove(webm_file_path)
        print(f"🗑️ Deleted local file: {webm_file_path}")

    return transcription

@audio_router.websocket("/ws/audio")
async def audio_stream(websocket: WebSocket):
    """
    WebSocket을 통해 실시간 오디오 데이터를 수신하고 MinIO에 저장 후 Celery 작업 큐에 추가
    """
    await websocket.accept()
    print("✅ WebSocket connection established.")

    file_id = str(uuid.uuid4())
    webm_file_path = os.path.join(SAVE_PATH, f"{file_id}.webm")

    frames = []
    total_bytes_received = 0

    try:
        while True:
            try:
                data = await websocket.receive_bytes()
                if not data:
                    print("⚠️ Received empty audio data. Stopping recording.")
                    break
                
                frames.append(data)
                total_bytes_received += len(data)
                print(f"📡 Received {len(data)} bytes (Total: {total_bytes_received} bytes).")

            except Exception as e:
                print(f"❌ Connection closed unexpectedly: {e}")
                break  # WebSocket 종료 시 루프 탈출

        if total_bytes_received == 0:
            print("❌ No valid audio data received. File will not be saved.")
            return

        # WebM 파일 저장
        with open(webm_file_path, "wb") as webm_file:
            webm_file.write(b''.join(frames))
        print(f"✅ WebM file saved: {webm_file_path}")

        # MinIO에 WebM 파일 업로드
        minio_client.fput_object(MINIO_BUCKET_NAME, f"{file_id}.webm", webm_file_path)

        # Celery Task 실행
        task = process_audio_task.delay(file_id)
        await websocket.send_text(f"Task submitted: {task.id}")
        print(f"📤 Task {task.id} submitted to Celery.")

    finally:
        if websocket.client_state == WebSocketState.CONNECTED:
            await websocket.close()
            print("🔌 WebSocket connection closed successfully.")
