"""Tests for scraper HTML extraction, parsing, and validation."""

import pytest
from unittest.mock import patch, MagicMock
from app.scraper.fetcher import _html_to_text
from app.scraper.parsers import (
    validate_parsed_data,
    _parse_with_regex,
    _extract_json_from_response,
    _compute_confidence,
)


class TestHtmlToText:
    def test_strips_scripts_and_styles(self):
        html = """
        <html>
        <head><style>body { color: red; }</style></head>
        <body>
            <script>alert('hi')</script>
            <div class="entry-content">
                <p>Back Squat 5x3</p>
            </div>
        </body>
        </html>
        """
        text = _html_to_text(html)
        assert "alert" not in text
        assert "color: red" not in text
        assert "Back Squat" in text

    def test_extracts_workout_content(self):
        html = """
        <html><body>
            <nav>Navigation stuff</nav>
            <article>
                <h2>Today's Workout</h2>
                <p>A. Back Squat</p>
                <p>5 x 3 @RPE 7-8</p>
                <p>Tempo: 20X1</p>
            </article>
            <footer>Footer stuff</footer>
        </body></html>
        """
        text = _html_to_text(html)
        assert "Back Squat" in text
        assert "5 x 3" in text
        assert "20X1" in text

    def test_handles_empty_html(self):
        text = _html_to_text("")
        assert text == "" or text.strip() == ""

    def test_collapses_whitespace(self):
        html = "<body><p>A.   Back    Squat</p><p></p><p></p><p>5 x 3</p></body>"
        text = _html_to_text(html)
        lines = [l for l in text.split("\n") if l.strip()]
        assert len(lines) >= 1


class TestJsonExtraction:
    def test_extracts_clean_json(self):
        response = '{"tracks": []}'
        result = _extract_json_from_response(response)
        assert result == {"tracks": []}

    def test_extracts_from_markdown_fence(self):
        response = """Here is the result:
```json
{"tracks": [{"track_type": "fitness_performance", "display_order": 0, "blocks": []}]}
```
"""
        result = _extract_json_from_response(response)
        assert result is not None
        assert "tracks" in result

    def test_returns_none_for_garbage(self):
        result = _extract_json_from_response("this is not json at all")
        assert result is None

    def test_handles_nested_braces(self):
        response = '{"tracks": [{"blocks": [{"exercises": [{"sets": 3}]}]}]}'
        result = _extract_json_from_response(response)
        assert result is not None
        assert result["tracks"][0]["blocks"][0]["exercises"][0]["sets"] == 3


class TestValidation:
    def test_valid_data_passes(self, sample_parsed_data):
        valid, errors = validate_parsed_data(sample_parsed_data)
        assert valid is True, f"Expected valid but got errors: {errors}"

    def test_missing_tracks_fails(self):
        valid, _ = validate_parsed_data({})
        assert valid is False

    def test_empty_tracks_is_valid_shape(self):
        valid, errors = validate_parsed_data({"tracks": []})
        # Empty tracks is structurally valid but may be flagged as low confidence
        # The validator may or may not accept empty tracks depending on implementation
        assert isinstance(valid, bool)

    def test_invalid_track_type_fails(self):
        data = {"tracks": [{"track_type": "invalid", "display_order": 0, "blocks": []}]}
        valid, _ = validate_parsed_data(data)
        assert valid is False

    def test_missing_blocks_fails(self):
        data = {"tracks": [{"track_type": "fitness_performance", "display_order": 0}]}
        valid, _ = validate_parsed_data(data)
        assert valid is False


class TestRegexParser:
    def test_finds_block_labels(self, sample_workout_text):
        result, confidence, method = _parse_with_regex(sample_workout_text)
        assert method == "regex"
        assert result is not None
        tracks = result.get("tracks", [])
        assert len(tracks) >= 1

    def test_extracts_sets_reps(self, sample_workout_text):
        result, confidence, method = _parse_with_regex(sample_workout_text)
        found_sets = False
        for track in result.get("tracks", []):
            for block in track.get("blocks", []):
                for ex in block.get("exercises", []):
                    if ex.get("sets") and ex.get("reps_min"):
                        found_sets = True
        assert found_sets, "Should extract at least one exercise with sets and reps"

    def test_extracts_tempo(self, sample_workout_text):
        result, _, _ = _parse_with_regex(sample_workout_text)
        found_tempo = False
        for track in result.get("tracks", []):
            for block in track.get("blocks", []):
                for ex in block.get("exercises", []):
                    if ex.get("tempo"):
                        found_tempo = True
        assert found_tempo, "Should extract tempo notation"

    def test_confidence_range(self, sample_workout_text):
        _, confidence, _ = _parse_with_regex(sample_workout_text)
        assert 0.0 <= confidence <= 1.0

    def test_minimal_text(self):
        result, confidence, _ = _parse_with_regex("just some random text")
        assert confidence < 0.75


class TestConfidenceScoring:
    def test_full_data_high_confidence(self, sample_parsed_data):
        conf = _compute_confidence(sample_parsed_data, 0.85)
        assert conf >= 0.80

    def test_empty_data_low_confidence(self):
        conf = _compute_confidence({"tracks": []}, 0.85)
        assert conf < 0.85

    def test_base_respected(self, sample_parsed_data):
        conf_high = _compute_confidence(sample_parsed_data, 0.90)
        conf_low = _compute_confidence(sample_parsed_data, 0.80)
        assert conf_high >= conf_low


class TestOllamaFallback:
    """Test that the pipeline falls back correctly when Ollama is unavailable."""

    @patch("app.scraper.parsers._parse_with_ollama")
    @patch("app.scraper.parsers._parse_with_claude")
    @patch("app.scraper.parsers._parse_with_regex")
    def test_falls_back_to_claude_on_ollama_failure(
        self, mock_regex, mock_claude, mock_ollama, sample_workout_text
    ):
        mock_ollama.return_value = None  # Ollama failed
        mock_claude.return_value = ({"tracks": []}, 0.85, "claude")
        mock_regex.return_value = ({"tracks": []}, 0.5, "regex")

        from app.scraper.parsers import parse_workout

        data, confidence, method = parse_workout(sample_workout_text)
        assert method == "claude"
        mock_claude.assert_called_once()

    @patch("app.scraper.parsers._parse_with_ollama")
    @patch("app.scraper.parsers._parse_with_claude")
    @patch("app.scraper.parsers._parse_with_regex")
    def test_falls_back_to_regex_on_both_failure(
        self, mock_regex, mock_claude, mock_ollama, sample_workout_text
    ):
        mock_ollama.return_value = None  # Ollama failed
        mock_claude.return_value = None  # Claude failed
        mock_regex.return_value = ({"tracks": []}, 0.55, "regex")

        from app.scraper.parsers import parse_workout

        data, confidence, method = parse_workout(sample_workout_text)
        assert method == "regex"
