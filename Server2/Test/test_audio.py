import asyncio
from agents.audio_agent import AudioAgent
import os
import time
import wave
import tempfile


def split_audio(file_path, chunk_duration_ms=1000):
    """
    Splits the audio file into 1-second chunks.
    Returns a list of audio byte chunks with proper WAV headers.
    """
    with wave.open(file_path, 'rb') as wav:
        frame_rate = wav.getframerate()
        n_channels = wav.getnchannels()
        sampwidth = wav.getsampwidth()
        chunk_frames = int(frame_rate * (1))  # 1-second chunks

        audio_chunks = []
        while True:
            frames = wav.readframes(chunk_frames)
            if not frames:
                break

            # Write the chunk to a temporary WAV file
            with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as temp_wav:
                with wave.open(temp_wav, 'wb') as chunk_wav:
                    chunk_wav.setnchannels(n_channels)
                    chunk_wav.setsampwidth(sampwidth)
                    chunk_wav.setframerate(frame_rate)
                    chunk_wav.writeframes(frames)

                audio_chunks.append(temp_wav.name)

    return audio_chunks

async def test_audio_chunks():
    print("Starting Audio Agent Chunk Processing Test")

    # Initialize audio agent
    agent = AudioAgent()

    # Path to the test audio file
    audio_file_path = "test_audio.wav"  # Replace with your file path

    if not os.path.exists(audio_file_path):
        print(f"File test_audio.wav not found! Please add the test audio file.")
        return

    # Split audio into 1-second chunks with proper headers
    audio_chunks = split_audio(audio_file_path)
    print(f"\nSplit into {len(audio_chunks)} 1-second chunks")

    # Process each chunk
    for i, chunk_path in enumerate(audio_chunks, 1):
        print(f"\nProcessing Chunk {i}/{len(audio_chunks)}")

        try:
            # Read the chunk from the temporary file
            with open(chunk_path, 'rb') as audio_file:
                audio_bytes = audio_file.read()

            # Process the chunk
            chunk_start_time = time.time()
            results = await agent.process_chunk(audio_bytes)
            processing_time = time.time() - chunk_start_time

            # Print results for this chunk
            print(f"Results for chunk {i}:")
            print(f"Transcription: {results.get('transcription', '')}")
            print(f"Danger Detected: {results.get('danger_detected', False)}")
            print(f"Risk Analysis: {results.get('risk_analysis', '')}")
            print(f"Confidence: {results.get('confidence', 0.0)}")
            print(f"Processing Time: {processing_time:.2f} seconds")

            # Add a small delay between chunks to simulate real-time processing
            await asyncio.sleep(1)

        except Exception as e:
            print(f"Error processing chunk {i}: {str(e)}")

        finally:
            # Clean up temporary chunk file
            if os.path.exists(chunk_path):
                os.remove(chunk_path)

    # Print final statistics
    print("\nFinal Statistics:")
    stats = agent.get_stats()
    print(f"Total chunks processed: {stats['total_audio_processed']}")
    print(f"Total dangers detected: {stats['total_dangers_detected']}")
    print(f"Average processing time: {stats['average_processing_time']:.2f} seconds")

async def main():
    await test_audio_chunks()

if __name__ == "__main__":
    asyncio.run(main())
