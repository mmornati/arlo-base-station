import av
import time
import os

time.sleep(5)

for attempt in range(5):
    print(f"Attempt {attempt+1}:")
    try:
        container = av.open("rtsp://192.168.2.X:554/live", options={"rtsp_transport":"tcp","stimeout":"8000000"})
        for stream in container.streams:
            if stream.type == "video":
                for frame in container.decode(stream):
                    print(f"  got frame: {frame.width}x{frame.height}")
                    path = "/tmp/test_snapshot.jpg"
                    frame.to_image().save(path)
                    print(f"  saved {os.path.getsize(path)} bytes")
                    break
                break
        container.close()
        break
    except Exception as e:
        print(f"  failed: {e}")
        time.sleep(2)