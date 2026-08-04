from unittest.mock import patch

from app.ingestion.translate import translate_title_to_english


def test_translate_title_to_english_returns_translated_text():
    with patch("app.ingestion.translate._translate_with_google") as mock_google:
        mock_google.return_value = "City Hall inaugurates new school"
        result = translate_title_to_english("Prefeitura inaugura nova escola")

    assert result == "City Hall inaugurates new school"
    mock_google.assert_called_once_with("Prefeitura inaugura nova escola")


def test_translate_title_to_english_uses_mymemory_when_google_fails():
    with patch("app.ingestion.translate._translate_with_google") as mock_google, patch(
        "app.ingestion.translate._translate_with_mymemory"
    ) as mock_mymemory:
        mock_google.return_value = None
        mock_mymemory.return_value = "City Hall opens new school"
        result = translate_title_to_english("Prefeitura inaugura nova escola")

    assert result == "City Hall opens new school"


def test_translate_title_to_english_falls_back_on_failure():
    with patch("app.ingestion.translate._translate_with_google") as mock_google, patch(
        "app.ingestion.translate._translate_with_mymemory"
    ) as mock_mymemory:
        mock_google.side_effect = RuntimeError("network error")
        mock_mymemory.return_value = None
        result = translate_title_to_english("Prefeitura inaugura nova escola")

    assert result == "Prefeitura inaugura nova escola"


def test_translate_title_to_english_handles_empty_title():
    assert translate_title_to_english("") == ""
    assert translate_title_to_english("   ") == ""
