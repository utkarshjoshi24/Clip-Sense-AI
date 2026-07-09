"""
backend/tests/test_rbac.py — Role-based access control tests.

Verifies that plan limits and role requirements are enforced server-side.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestPlanLimits:
    """Verify free/pro plan limits are enforced at the API layer."""

    def test_free_plan_limits(self):
        from app.config import get_settings
        settings = get_settings()

        assert settings.FREE_MAX_VIDEOS_PER_MONTH == 3
        assert settings.FREE_MAX_VIDEO_DURATION_SEC == 900   # 15 min
        assert settings.FREE_MAX_FILE_SIZE_BYTES == 500 * 1024 * 1024

    def test_pro_plan_limits(self):
        from app.config import get_settings
        settings = get_settings()

        assert settings.PRO_MAX_VIDEO_DURATION_SEC == 7200   # 2 hr
        assert settings.PRO_MAX_FILE_SIZE_BYTES == 2 * 1024 * 1024 * 1024

    def test_get_plan_limits_returns_correct_values_for_free_user(self):
        from app.routers.videos import _get_plan_limits
        from app.models.user import User, UserRole

        mock_user = MagicMock(spec=User)
        mock_user.role = UserRole.FREE

        from app.config import get_settings
        settings = get_settings()

        max_bytes, max_dur = _get_plan_limits(mock_user)
        assert max_bytes == settings.FREE_MAX_FILE_SIZE_BYTES
        assert max_dur == settings.FREE_MAX_VIDEO_DURATION_SEC

    def test_get_plan_limits_returns_correct_values_for_pro_user(self):
        from app.routers.videos import _get_plan_limits
        from app.models.user import User, UserRole

        mock_user = MagicMock(spec=User)
        mock_user.role = UserRole.PRO

        from app.config import get_settings
        settings = get_settings()

        max_bytes, max_dur = _get_plan_limits(mock_user)
        assert max_bytes == settings.PRO_MAX_FILE_SIZE_BYTES
        assert max_dur == settings.PRO_MAX_VIDEO_DURATION_SEC


class TestMagicByteValidation:
    """Verify file type is validated via magic bytes, not extension."""

    def test_valid_mp4_accepted(self):
        from app.routers.videos import _validate_magic_bytes
        # MP4 magic bytes: ftyp box at offset 4
        # Use a real minimal MP4 header bytes
        import struct
        # Minimal FTYP atom: size(4) + 'ftyp' + 'mp42' + 0 + 'mp42'
        ftyp = struct.pack(">I", 20) + b"ftypisom" + b"\x00" * 4 + b"isom"
        with patch("app.routers.videos.magic.from_buffer", return_value="video/mp4"):
            mime = _validate_magic_bytes(ftyp)
            assert mime == "video/mp4"

    def test_text_file_rejected(self):
        from app.routers.videos import _validate_magic_bytes
        from fastapi import HTTPException

        with patch("app.routers.videos.magic.from_buffer", return_value="text/plain"):
            with pytest.raises(HTTPException) as exc_info:
                _validate_magic_bytes(b"This is not a video")
            assert exc_info.value.status_code == 400

    def test_renamed_text_file_rejected(self):
        """A .mp4 extension on a text file should still be rejected."""
        from app.routers.videos import _validate_magic_bytes
        from fastapi import HTTPException

        with patch("app.routers.videos.magic.from_buffer", return_value="text/plain"):
            with pytest.raises(HTTPException):
                _validate_magic_bytes(b"I am secretly a text file named video.mp4")


class TestDependencies:
    """Verify auth dependencies behave correctly."""

    def test_require_role_raises_for_wrong_role(self):
        from app.dependencies import require_role
        from app.models.user import User, UserRole
        from fastapi import HTTPException

        mock_user = MagicMock(spec=User)
        mock_user.email_verified = True
        mock_user.role = UserRole.FREE

        checker = require_role(UserRole.PRO)

        with pytest.raises(HTTPException) as exc_info:
            checker(current_user=mock_user)
        assert exc_info.value.status_code == 403

    def test_require_verified_email_raises_for_unverified(self):
        from app.dependencies import require_verified_email
        from app.models.user import User
        from fastapi import HTTPException

        mock_user = MagicMock(spec=User)
        mock_user.email_verified = False

        with pytest.raises(HTTPException) as exc_info:
            require_verified_email(current_user=mock_user)
        assert exc_info.value.status_code == 403
