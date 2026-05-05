from io import BytesIO

from django.core.files.base import ContentFile


def ensure_song_thumbnail_from_video(song, force=False):
    """
    Generate a JPEG thumbnail from the uploaded video and store it in song.thumbnail.
    Returns True when a thumbnail was generated and saved.
    """
    if not song or not song.song:
        return False
    if song.thumbnail and not force:
        return False

    video_path = getattr(song.song, "path", None)
    if not video_path:
        return False

    try:
        import cv2
    except Exception:
        return False

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return False

    try:
        fps = cap.get(cv2.CAP_PROP_FPS)
        if not fps or fps <= 0:
            fps = 25.0
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(fps))
        ok, frame = cap.read()
        if not ok or frame is None:
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ok, frame = cap.read()
        if not ok or frame is None:
            return False

        ok, encoded = cv2.imencode(".jpg", frame)
        if not ok:
            return False

        buffer = BytesIO(encoded.tobytes())
        thumb_name = "video-thumb-{}.jpg".format(song.pk)
        song.thumbnail.save(thumb_name, ContentFile(buffer.getvalue()), save=False)
        song.save(update_fields=["thumbnail"])
        return True
    finally:
        cap.release()
