"""
Tests for the screenshot validator, with Gemini and C2PA stubbed out.
"""

import asyncio

import pytest

from utils import image_validator


class FakeModels:
    def __init__(self, text=None, error=None):
        self.text, self.error = text, error

    async def generate_content(self, **kwargs):
        if self.error:
            raise self.error
        return type('Result', (), {'text': self.text})()


def stub_gemini(monkeypatch, **kwargs):
    models = FakeModels(**kwargs)
    client = type('Client', (), {'aio': type('Aio', (), {'models': models})()})()
    monkeypatch.setattr(image_validator.genai, 'Client', lambda api_key: client)


@pytest.fixture(autouse=True)
def no_c2pa(monkeypatch):
    monkeypatch.setattr(image_validator, 'check_provenance', lambda b, t: 'UNKNOWN')


@pytest.mark.parametrize('text,expected', [('VALID', True), ('INVALID', False), (None, False)])
def test_verdict(monkeypatch, text, expected):
    stub_gemini(monkeypatch, text=text)
    is_valid, _ = asyncio.run(image_validator.validate_aim_screenshot(b'img', 'image/png'))
    assert is_valid is expected


def test_gemini_error_fails_open(monkeypatch):
    stub_gemini(monkeypatch, error=RuntimeError('down'))
    is_valid, reason = asyncio.run(image_validator.validate_aim_screenshot(b'img', 'image/png'))
    assert is_valid and 'unavailable' in reason


def test_ai_generated_rejected_before_gemini(monkeypatch):
    monkeypatch.setattr(image_validator, 'check_provenance', lambda b, t: 'AI_GENERATED')
    stub_gemini(monkeypatch, error=AssertionError('Gemini should not be called'))
    is_valid, _ = asyncio.run(image_validator.validate_aim_screenshot(b'img', 'image/png'))
    assert not is_valid
