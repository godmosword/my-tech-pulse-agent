"""Tests for Telegram message chunking and MarkdownV2 validation."""

from delivery.telegram_bot import TelegramBot


class TestSmartChunking:
    def test_short_text_no_chunking(self):
        """Text under max length should not be chunked."""
        text = "This is a short message"
        chunks = TelegramBot._smart_chunk_text(text, max_length=4096)
        assert len(chunks) == 1
        assert chunks[0] == text

    def test_theme_boundary_splitting(self):
        """Split at theme boundaries to keep sections intact."""
        text = "*Theme A*\nContent A\nMore content\n\n*Theme B*\nContent B"
        chunks = TelegramBot._smart_chunk_text(text, max_length=30)
        # Should split when exceeding max_length
        assert len(chunks) >= 2
        assert "*Theme A*" in chunks[0]
        # Verify no chunk exceeds max_length
        for chunk in chunks:
            assert len(chunk) <= 30

    def test_respects_max_length(self):
        """Chunks should not exceed max_length when possible.

        Note: A single line longer than max_length will not be split.
        """
        short_content = "x" * 30
        text = (
            f"*Theme 1*\n{short_content}\n\n"
            f"*Theme 2*\n{short_content}\n\n"
            f"*Theme 3*\n{short_content}"
        )
        chunks = TelegramBot._smart_chunk_text(text, max_length=80)
        for chunk in chunks:
            assert len(chunk) <= 80

    def test_empty_text(self):
        """Empty text should return a list with empty string."""
        chunks = TelegramBot._smart_chunk_text("", max_length=4096)
        assert chunks == [""]

    def test_preserves_newlines(self):
        """Chunks should be joined with newlines."""
        text = "Line 1\nLine 2\nLine 3"
        chunks = TelegramBot._smart_chunk_text(text, max_length=100)
        assert "\n" in chunks[0]


class TestMarkdownValidation:
    def test_balanced_backslashes(self):
        """Text with balanced backslashes should validate."""
        assert TelegramBot._validate_markdown_boundaries("test \\[escaped\\]") is True

    def test_unmatched_single_backslash(self):
        """Text ending with single backslash should fail validation."""
        assert TelegramBot._validate_markdown_boundaries("test \\[escaped\\") is False

    def test_unmatched_double_backslash(self):
        """Text ending with double backslash should validate (escaped backslash)."""
        assert TelegramBot._validate_markdown_boundaries("test \\\\") is True

    def test_empty_string(self):
        """Empty string should validate."""
        assert TelegramBot._validate_markdown_boundaries("") is True

    def test_no_backslashes(self):
        """Text without backslashes should validate."""
        assert TelegramBot._validate_markdown_boundaries("normal text") is True

    def test_unicode_with_balanced_escapes(self):
        """Unicode text with balanced escapes should validate."""
        assert TelegramBot._validate_markdown_boundaries("科技脈搏 \\[原文\\]") is True

    def test_unicode_with_unmatched_escape(self):
        """Unicode text ending with unmatched backslash should fail validation."""
        assert TelegramBot._validate_markdown_boundaries("科技脈搏 \\[原文\\") is False


class TestChunkingWithMarkdown:
    def test_chunks_preserve_markdown_validity(self):
        """Each chunk should have valid markdown boundaries."""
        text = (
            "*Theme A*\n"
            "Content with \\[escaped\\] brackets\n\n"
            "*Theme B*\n"
            "More \\(escaped\\) text"
        )
        chunks = TelegramBot._smart_chunk_text(text, max_length=50)
        for chunk in chunks:
            assert TelegramBot._validate_markdown_boundaries(chunk), f"Invalid chunk: {chunk}"

    def test_markdown_not_split_at_escape_sequence(self):
        """Escape sequences should not be split across chunks."""
        text = "*Item*\nText with \\[" + "x" * 100 + "\\] escaped"
        chunks = TelegramBot._smart_chunk_text(text, max_length=80)
        # The escape sequence should be kept together
        for chunk in chunks:
            assert TelegramBot._validate_markdown_boundaries(chunk)

    def test_digest_format_chunking(self):
        """Real digest format should chunk cleanly by theme."""
        text = (
            "*🧠 AI 基礎設施*\n"
            "⭐ 8.5 *NVIDIA H200 性能突破*\n"
            "詳細分析內容 " * 50 + "\n\n"
            "*🔗 雲端與企業軟體*\n"
            "⭐ 7.2 *AWS 推出新服務*\n"
            "更多詳細 " * 50
        )
        chunks = TelegramBot._smart_chunk_text(text, max_length=500)
        assert len(chunks) >= 2
        for chunk in chunks:
            assert TelegramBot._validate_markdown_boundaries(chunk)
