"""
Unit tests for the Sarvam Job-based STT flow.
Run: pytest backend/tests/test_sarvam_job_flow.py -v
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from pathlib import Path

# Ensure backend package is importable
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.sarvam_service import SarvamClient, SarvamAPIError


class TestBuildUploadUrl:
    """Test the URL derivation from job_id."""

    def setup_method(self):
        self.client = SarvamClient()

    def test_valid_job_id(self):
        url = self.client.build_upload_url(
            "20260303_2bee913d-1af2-4da7-b6e1-8667d36809c2", "audio.mp3"
        )
        assert "/jobs/20260303/" in url
        assert "/SPEECH_TO_TEXT_BULK/" in url
        assert "/2bee913d-1af2-4da7-b6e1-8667d36809c2/" in url
        assert url.endswith("/inputs/audio.mp3")

    def test_different_filename(self):
        url = self.client.build_upload_url(
            "20260101_abcdef12-3456-7890-abcd-ef1234567890", "test.wav"
        )
        assert url.endswith("/inputs/test.wav")
        assert "/jobs/20260101/" in url

    def test_invalid_job_id_raises(self):
        with pytest.raises(ValueError, match="Invalid Sarvam job_id"):
            self.client.build_upload_url("invalid-no-date-prefix", "audio.mp3")

    def test_invalid_job_id_no_underscore(self):
        with pytest.raises(ValueError):
            self.client.build_upload_url("nounderscore", "audio.mp3")


class TestExtractOutputFilenames:
    """Test output filename extraction from status responses."""

    def setup_method(self):
        self.client = SarvamClient()

    def test_single_output(self):
        status = {
            "job_state": "Completed",
            "job_details": [
                {
                    "inputs": [{"file_name": "audio.mp3"}],
                    "outputs": [{"file_name": "0.json"}],
                    "state": "Success",
                }
            ],
        }
        assert self.client.extract_output_filenames(status) == ["0.json"]

    def test_multiple_outputs(self):
        status = {
            "job_details": [
                {
                    "outputs": [
                        {"file_name": "0.json"},
                        {"file_name": "1.json"},
                    ],
                    "state": "Success",
                }
            ]
        }
        assert self.client.extract_output_filenames(status) == ["0.json", "1.json"]

    def test_empty_job_details(self):
        assert self.client.extract_output_filenames({"job_details": []}) == []

    def test_no_job_details_key(self):
        assert self.client.extract_output_filenames({}) == []

    def test_no_outputs(self):
        status = {
            "job_details": [
                {"outputs": [], "state": "Success"}
            ]
        }
        assert self.client.extract_output_filenames(status) == []


class TestGuessContentType:
    """Test MIME type guessing."""

    def test_mp3(self):
        assert SarvamClient._guess_content_type(Path("audio.mp3")) == "audio/mpeg"

    def test_wav(self):
        assert SarvamClient._guess_content_type(Path("audio.wav")) == "audio/wav"

    def test_webm(self):
        assert SarvamClient._guess_content_type(Path("audio.webm")) == "audio/webm"

    def test_unknown(self):
        assert SarvamClient._guess_content_type(Path("file.xyz")) == "application/octet-stream"

    def test_flac(self):
        assert SarvamClient._guess_content_type(Path("audio.flac")) == "audio/flac"


class TestWaitForCompletion:
    """Test the polling loop."""

    def setup_method(self):
        self.client = SarvamClient()

    @pytest.mark.asyncio
    async def test_immediate_completion(self):
        """Job already completed on first poll."""
        self.client.poll_sarvam_status = AsyncMock(
            return_value={"job_state": "Completed", "job_details": []}
        )
        result = await self.client.wait_for_completion(
            "test-id", initial_interval=0, max_backoff=0, timeout=10
        )
        assert result["job_state"] == "Completed"
        self.client.poll_sarvam_status.assert_called_once_with("test-id")

    @pytest.mark.asyncio
    async def test_completes_after_polling(self):
        """Job completes after a few Running polls."""
        responses = [
            {"job_state": "Running"},
            {"job_state": "Running"},
            {"job_state": "Completed", "job_details": []},
        ]
        call_idx = 0

        async def mock_poll(job_id):
            nonlocal call_idx
            resp = responses[min(call_idx, len(responses) - 1)]
            call_idx += 1
            return resp

        self.client.poll_sarvam_status = mock_poll

        result = await self.client.wait_for_completion(
            "test-id", initial_interval=0, max_backoff=0, timeout=10
        )
        assert result["job_state"] == "Completed"
        assert call_idx == 3

    @pytest.mark.asyncio
    async def test_failure_raises_runtime_error(self):
        """Job failure raises RuntimeError."""
        self.client.poll_sarvam_status = AsyncMock(
            return_value={"job_state": "Failed", "error": "bad audio"}
        )
        with pytest.raises(RuntimeError, match="failed"):
            await self.client.wait_for_completion(
                "test-id", initial_interval=0, max_backoff=0, timeout=10
            )

    @pytest.mark.asyncio
    async def test_timeout_raises(self):
        """Timeout raises TimeoutError."""
        self.client.poll_sarvam_status = AsyncMock(
            return_value={"job_state": "Running"}
        )
        with pytest.raises(TimeoutError, match="did not complete"):
            await self.client.wait_for_completion(
                "test-id", initial_interval=0, max_backoff=0, timeout=0
            )

    @pytest.mark.asyncio
    async def test_on_poll_callback(self):
        """on_poll callback is invoked for each poll."""
        responses = [
            {"job_state": "Running"},
            {"job_state": "Completed", "job_details": []},
        ]
        call_idx = 0

        async def mock_poll(job_id):
            nonlocal call_idx
            resp = responses[min(call_idx, len(responses) - 1)]
            call_idx += 1
            return resp

        self.client.poll_sarvam_status = mock_poll

        callback_calls = []

        async def on_poll(status):
            callback_calls.append(status)

        result = await self.client.wait_for_completion(
            "test-id",
            initial_interval=0,
            max_backoff=0,
            timeout=10,
            on_poll=on_poll,
        )
        assert len(callback_calls) == 2
        assert callback_calls[0]["job_state"] == "Running"
        assert callback_calls[1]["job_state"] == "Completed"


class TestCreateSarvamJob:
    """Test create_sarvam_job with mocked HTTP."""

    def setup_method(self):
        self.client = SarvamClient()

    @pytest.mark.asyncio
    async def test_success(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "job_id": "20260303_test-uuid",
            "job_state": "Accepted",
            "job_parameters": {"language_code": "en-IN"},
        }

        with patch("httpx.AsyncClient") as MockClient:
            mock_client_instance = AsyncMock()
            mock_client_instance.post.return_value = mock_response
            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = AsyncMock(return_value=None)
            MockClient.return_value = mock_client_instance

            result = await self.client.create_sarvam_job("en-IN")
            assert result["job_id"] == "20260303_test-uuid"
            assert result["job_state"] == "Accepted"

    @pytest.mark.asyncio
    async def test_rate_limit(self):
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.text = "Too Many Requests"

        with patch("httpx.AsyncClient") as MockClient:
            mock_client_instance = AsyncMock()
            mock_client_instance.post.return_value = mock_response
            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = AsyncMock(return_value=None)
            MockClient.return_value = mock_client_instance

            with pytest.raises(Exception):  # SarvamRateLimitError
                await self.client.create_sarvam_job("en-IN")


class TestJobStatusEnum:
    """Test that the new status enum values exist."""

    def test_new_statuses_exist(self):
        from app.models.transcription_job import JobStatus

        assert JobStatus.UPLOADING_TO_SARVAM.value == "uploading_to_sarvam"
        assert JobStatus.SARVAM_PROCESSING.value == "sarvam_processing"
        assert JobStatus.DOWNLOADING_RESULT.value == "downloading_result"

    def test_old_statuses_preserved(self):
        from app.models.transcription_job import JobStatus

        assert JobStatus.QUEUED.value == "queued"
        assert JobStatus.PROCESSING.value == "processing"
        assert JobStatus.STREAMING.value == "streaming"
        assert JobStatus.COMPLETED.value == "completed"
        assert JobStatus.FAILED.value == "failed"


class TestSchemaEnums:
    """Test that schema enums match model enums."""

    def test_schema_has_new_statuses(self):
        from app.routes.schemas.job import JobStatusEnum

        assert JobStatusEnum.UPLOADING_TO_SARVAM.value == "uploading_to_sarvam"
        assert JobStatusEnum.SARVAM_PROCESSING.value == "sarvam_processing"
        assert JobStatusEnum.DOWNLOADING_RESULT.value == "downloading_result"

    def test_job_response_has_sarvam_fields(self):
        from app.routes.schemas.job import JobResponse
        from datetime import datetime

        resp = JobResponse(
            id="test",
            language="en-IN",
            status="completed",
            mode="batch",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            sarvam_job_id="20260303_test",
            sarvam_state="Completed",
        )
        assert resp.sarvam_job_id == "20260303_test"
        assert resp.sarvam_state == "Completed"

    def test_job_status_response_has_sarvam_fields(self):
        from app.routes.schemas.job import JobStatusResponse

        resp = JobStatusResponse(
            id="test",
            status="sarvam_processing",
            sarvam_job_id="20260303_test",
            sarvam_state="Running",
            sarvam_poll_count=5,
        )
        assert resp.sarvam_poll_count == 5
