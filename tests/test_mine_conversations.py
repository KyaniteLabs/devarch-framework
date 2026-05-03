"""Tests for scripts/data/mine_conversations.py timestamp parsing."""

from pathlib import Path

from scripts.data.mine_conversations import mine_chatgpt_export


def test_timestamp_parsing_with_numeric_timestamp():
    """Test timestamp parsing with numeric Unix timestamps."""
    # Create a mock ChatGPT export with numeric timestamps
    import tempfile
    import json

    mock_conversations = [
        {
            "title": "Test Conversation",
            "create_time": 1704067200,  # 2024-01-01 00:00:00 UTC
            "mapping": {
                "msg1": {
                    "message": {
                        "author": {"role": "user"},
                        "content": {
                            "content_type": "text",
                            "parts": ["This is a reflection on learning something new today"]
                        },
                        "create_time": 1704067200
                    }
                }
            }
        }
    ]

    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(mock_conversations, f)
        temp_path = Path(f.name)

    try:
        output_dir = Path(tempfile.mkdtemp())
        result = mine_chatgpt_export(
            input_path=temp_path,
            output_dir=output_dir,
            dry_run=True
        )
        # Should successfully parse numeric timestamp
        assert result["conversations"] == 1
    finally:
        temp_path.unlink(missing_ok=True)


def test_timestamp_parsing_with_string_timestamp():
    """Test timestamp parsing with string timestamps (should return None, not crash)."""
    import tempfile
    import json

    mock_conversations = [
        {
            "title": "Test Conversation",
            "create_time": "2024-01-01T00:00:00Z",  # String timestamp
            "mapping": {
                "msg1": {
                    "message": {
                        "author": {"role": "user"},
                        "content": {
                            "content_type": "text",
                            "parts": ["This is a reflection on learning something new today"]
                        },
                        "create_time": "2024-01-01T00:00:00Z"  # String timestamp
                    }
                }
            }
        }
    ]

    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(mock_conversations, f)
        temp_path = Path(f.name)

    try:
        output_dir = Path(tempfile.mkdtemp())
        # Should not crash with string timestamps
        result = mine_chatgpt_export(
            input_path=temp_path,
            output_dir=output_dir,
            dry_run=True
        )
        # String timestamps are not converted, so timestamp will be None
        assert result["conversations"] == 1
    finally:
        temp_path.unlink(missing_ok=True)


def test_timestamp_parsing_with_none_timestamp():
    """Test timestamp parsing with None timestamps (should return None, not crash)."""
    import tempfile
    import json

    mock_conversations = [
        {
            "title": "Test Conversation",
            "create_time": None,
            "mapping": {
                "msg1": {
                    "message": {
                        "author": {"role": "user"},
                        "content": {
                            "content_type": "text",
                            "parts": ["This is a reflection on learning something new today"]
                        },
                        "create_time": None
                    }
                }
            }
        }
    ]

    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(mock_conversations, f)
        temp_path = Path(f.name)

    try:
        output_dir = Path(tempfile.mkdtemp())
        # Should not crash with None timestamps
        result = mine_chatgpt_export(
            input_path=temp_path,
            output_dir=output_dir,
            dry_run=True
        )
        assert result["conversations"] == 1
    finally:
        temp_path.unlink(missing_ok=True)


def test_timestamp_parsing_with_float_timestamp():
    """Test timestamp parsing with float Unix timestamps."""
    import tempfile
    import json

    mock_conversations = [
        {
            "title": "Test Conversation",
            "create_time": 1704067200.5,  # Float timestamp
            "mapping": {
                "msg1": {
                    "message": {
                        "author": {"role": "user"},
                        "content": {
                            "content_type": "text",
                            "parts": ["This is a reflection on learning something new today"]
                        },
                        "create_time": 1704067200.5
                    }
                }
            }
        }
    ]

    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(mock_conversations, f)
        temp_path = Path(f.name)

    try:
        output_dir = Path(tempfile.mkdtemp())
        result = mine_chatgpt_export(
            input_path=temp_path,
            output_dir=output_dir,
            dry_run=True
        )
        # Should successfully parse float timestamp
        assert result["conversations"] == 1
    finally:
        temp_path.unlink(missing_ok=True)
