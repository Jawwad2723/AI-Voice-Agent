import asyncio
import socket
import struct
import logging
import random
from typing import Dict, Optional, Callable

logger = logging.getLogger(__name__)

class RTPSession:
    def __init__(self, call_id: str, local_port: int, sock: socket.socket):
        self.call_id = call_id
        self.local_port = local_port
        self.socket = sock
        self.remote_host: Optional[str] = None
        self.remote_port: Optional[int] = None
        self.ssrc: Optional[int] = None
        self.outbound_ssrc: Optional[int] = None
        self.sequence_number = random.randint(0, 0xFFFF)
        self.timestamp = random.randint(0, 0xFFFFFFFF)
        self.receiver_task: Optional[asyncio.Task] = None

class RTPServer:
    def __init__(self, host: str, port_range_start: int, port_range_end: int):
        self.host = host
        self.port_range_start = port_range_start
        self.port_range_end = port_range_end
        self.sessions: Dict[str, RTPSession] = {}
        self.port_allocation: Dict[int, str] = {}
        self.running = False
        self.audio_callbacks: Dict[str, Callable[[bytes], None]] = {}

    def set_audio_callback(self, call_id: str, callback: Callable[[bytes], None]):
        self.audio_callbacks[call_id] = callback

    def remove_audio_callback(self, call_id: str):
        self.audio_callbacks.pop(call_id, None)

    def set_remote_endpoint(self, call_id: str, host: str, port: int):
        session = self.sessions.get(call_id)
        if session:
            session.remote_host = host
            session.remote_port = port
            if session.outbound_ssrc is None:
                session.outbound_ssrc = random.randint(0, 0xFFFFFFFF)
            logger.info(f"RTP remote endpoint pre-established for {call_id}: {host}:{port}")

    async def start(self):
        self.running = True
        logger.info(f"RTP Server initialized on {self.host} ({self.port_range_start}-{self.port_range_end})")

    async def stop(self):
        self.running = False
        for call_id in list(self.sessions.keys()):
            await self.cleanup_session(call_id)
        logger.info("RTP Server stopped")

    async def allocate_session(self, call_id: str) -> int:
        if call_id in self.sessions:
            return self.sessions[call_id].local_port

        port = self._reserve_port(call_id)
        if port is None:
            raise RuntimeError("No free RTP ports available")

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind((self.host, port))
        sock.setblocking(False)

        session = RTPSession(call_id, port, sock)
        self.sessions[call_id] = session

        loop = asyncio.get_running_loop()
        session.receiver_task = loop.create_task(self._receiver_loop(session))

        logger.info(f"Allocated RTP session for {call_id} on port {port}")
        return port

    async def cleanup_session(self, call_id: str):
        session = self.sessions.pop(call_id, None)
        if not session:
            return

        if session.receiver_task:
            session.receiver_task.cancel()
            try:
                await session.receiver_task
            except asyncio.CancelledError:
                pass

        if session.socket:
            session.socket.close()

        self.port_allocation.pop(session.local_port, None)
        self.audio_callbacks.pop(call_id, None)
        logger.info(f"Cleaned up RTP session for {call_id} on port {session.local_port}")

    def _reserve_port(self, call_id: str) -> Optional[int]:
        for port in range(self.port_range_start, self.port_range_end + 1):
            if port not in self.port_allocation:
                self.port_allocation[port] = call_id
                return port
        return None

    async def _receiver_loop(self, session: RTPSession):
        loop = asyncio.get_running_loop()
        logger.info(f"RTP receiver loop started for {session.call_id} on port {session.local_port}")
        
        def handle_read():
            while True:
                try:
                    data, addr = session.socket.recvfrom(1500)
                    if not data:
                        break
                    if len(data) < 12:
                        continue

                    # Parse RTP Header
                    version = data[0] >> 6
                    if version != 2:
                        continue

                    payload_type = data[1] & 0x7F
                    sequence = struct.unpack("!H", data[2:4])[0]
                    timestamp = struct.unpack("!I", data[4:8])[0]
                    ssrc = struct.unpack("!I", data[8:12])[0]
                    payload = data[12:]

                    # Filter echo (our own outbound SSRC)
                    if session.outbound_ssrc is not None and ssrc == session.outbound_ssrc:
                        continue

                    # Learn remote SSRC and address details
                    if session.ssrc is None or session.remote_host is None:
                        if session.remote_host is None:
                            session.remote_host, session.remote_port = addr[0], addr[1]
                        session.ssrc = ssrc
                        session.outbound_ssrc = (ssrc ^ 0xFFFFFFFF) & 0xFFFFFFFF
                        logger.info(f"RTP remote established/learned: {session.remote_host}:{session.remote_port}, Inbound SSRC: {ssrc}, Outbound SSRC: {session.outbound_ssrc}")

                    # Send payload to callback
                    callback = self.audio_callbacks.get(session.call_id)
                    if callback:
                        callback(payload)
                except BlockingIOError:
                    break
                except Exception as e:
                    if self.running:
                        logger.exception(f"RTP read error on port {session.local_port}")
                    break

        # Register non-blocking read listener on socket file descriptor
        loop.add_reader(session.socket.fileno(), handle_read)
        
        try:
            # Keep task alive while session runs
            while self.running and session.call_id in self.sessions:
                await asyncio.sleep(0.05)
        except asyncio.CancelledError:
            pass
        finally:
            # Unregister reader safely
            try:
                loop.remove_reader(session.socket.fileno())
            except Exception:
                pass

    def _send_rtp_chunk(self, session: RTPSession, chunk: bytes):
        """Build and send a single RTP packet for the given ulaw chunk."""
        header = struct.pack(
            "!BBHII",
            0x80,  # Version 2
            0,     # Payload type 0 (PCMU / ulaw)
            session.sequence_number & 0xFFFF,
            session.timestamp & 0xFFFFFFFF,
            session.outbound_ssrc & 0xFFFFFFFF
        )
        packet = header + chunk
        try:
            session.socket.sendto(packet, (session.remote_host, session.remote_port))
        except Exception as e:
            logger.error(f"Error sending RTP packet: {e}")
        session.sequence_number += 1
        session.timestamp += len(chunk)

    async def send_audio(self, call_id: str, payload: bytes):
        """Send a complete audio buffer, split into 20ms RTP frames with real-time pacing."""
        session = self.sessions.get(call_id)
        if not session or not session.remote_host or not session.remote_port:
            logger.warning(f"Cannot send audio to {call_id}: remote endpoint not established yet")
            return

        if session.outbound_ssrc is None:
            session.outbound_ssrc = random.randint(0, 0xFFFFFFFF)

        chunk_size = 160  # 20ms of ulaw @ 8kHz
        for i in range(0, len(payload), chunk_size):
            chunk = payload[i:i + chunk_size]
            if not chunk:
                break
            self._send_rtp_chunk(session, chunk)
            await asyncio.sleep(0.02)

    async def stream_audio(self, call_id: str, audio_generator):
        """Stream audio to RTP using a producer-consumer pattern with precise timing.

        A dedicated downloader task fills a frame queue from ElevenLabs.
        The sender drains the queue at exactly 20ms intervals using wall-clock
        timing (not fixed asyncio.sleep(0.02)) to avoid drift and bursts.
        A 300ms pre-buffer ensures a cushion of frames is ready before playback
        starts, preventing gaps when HTTP chunks arrive unevenly.
        """
        session = self.sessions.get(call_id)
        if not session or not session.remote_host or not session.remote_port:
            logger.warning(f"Cannot stream audio to {call_id}: remote endpoint not established yet")
            return

        if session.outbound_ssrc is None:
            session.outbound_ssrc = random.randint(0, 0xFFFFFFFF)

        CHUNK_SIZE = 160        # 20ms of ulaw @ 8kHz
        PRE_BUFFER_FRAMES = 15  # 300ms pre-buffer before starting playback

        frame_queue: asyncio.Queue = asyncio.Queue()
        download_done = asyncio.Event()

        async def _download():
            """Download audio from ElevenLabs and chop into 160-byte frames."""
            buf = b""
            try:
                async for data in audio_generator:
                    if not data:
                        continue
                    buf += data
                    while len(buf) >= CHUNK_SIZE:
                        await frame_queue.put(buf[:CHUNK_SIZE])
                        buf = buf[CHUNK_SIZE:]
                # Flush remaining partial frame
                if buf:
                    await frame_queue.put(buf)
            except asyncio.CancelledError:
                pass
            except Exception as e:
                logger.error(f"TTS download error: {e}")
            finally:
                download_done.set()

        download_task = asyncio.create_task(_download())

        try:
            # Wait for pre-buffer to fill OR for download to complete
            while frame_queue.qsize() < PRE_BUFFER_FRAMES and not download_done.is_set():
                await asyncio.sleep(0.005)

            # Send frames at precise 20ms intervals using wall-clock timing
            loop = asyncio.get_event_loop()
            next_send_time = loop.time()

            while True:
                try:
                    frame = frame_queue.get_nowait()
                except asyncio.QueueEmpty:
                    if download_done.is_set():
                        break
                    # Buffer temporarily dry — wait briefly without busy-looping
                    await asyncio.sleep(0.001)
                    continue

                self._send_rtp_chunk(session, frame)

                next_send_time += 0.02
                sleep_time = next_send_time - loop.time()
                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)
                # If sleep_time <= 0 we're behind — send next frame immediately to catch up

        except asyncio.CancelledError:
            download_task.cancel()
            raise
        finally:
            download_task.cancel()
            try:
                await download_task
            except (asyncio.CancelledError, Exception):
                pass
