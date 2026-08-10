class AppError(Exception):
    def __init__(self, code: str, message: str, status_code: int) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class InvalidYouTubeUrlError(AppError):
    def __init__(self, message: str = "Could not extract a valid YouTube video ID from the URL.") -> None:
        super().__init__("invalid_youtube_url", message, 400)


class VideoNotFoundError(AppError):
    def __init__(self, message: str = "Video is unavailable or inaccessible.") -> None:
        super().__init__("video_not_found", message, 404)


class YouTubeQuotaExceededError(AppError):
    def __init__(self, message: str = "YouTube API quota limit has been reached.") -> None:
        super().__init__("youtube_quota_exceeded", message, 429)


class GeminiGenerationFailedError(AppError):
    def __init__(self, message: str = "Could not generate discovery concepts.") -> None:
        super().__init__("gemini_generation_failed", message, 502)


class IntegrationUnavailableError(AppError):
    def __init__(self, message: str = "An external service is temporarily unavailable.") -> None:
        super().__init__("integration_unavailable", message, 503)
