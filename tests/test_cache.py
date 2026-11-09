"""Unit tests for disk-backed response cache and CachedLLMProvider."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel

from emc.llm import (
    CachedLLMProvider,
    DiskCache,
    FakeProvider,
    TokenUsage,
)


class SampleSchema(BaseModel):
    title: str
    points: int


def test_disk_cache_set_get_and_clear(tmp_path: Path) -> None:
    """Verify DiskCache persists entries, retrieves by key, and clears cleanly."""
    cache = DiskCache(cache_dir=tmp_path / "cache")
    diff_hash = "diff123"
    prompt = "Explain this diff"
    model = "claude-3-7-sonnet-latest"

    # Initially cache misses
    assert cache.has(diff_hash, prompt, model) is False
    assert cache.get(diff_hash, prompt, model) is None

    # Write entry
    usage = TokenUsage(prompt_tokens=50, completion_tokens=25, total_tokens=75)
    saved_file = cache.set(
        diff_hash=diff_hash,
        prompt=prompt,
        model=model,
        content="Cached text explanation",
        structured_data={"title": "Test", "points": 10},
        usage=usage,
        cost_usd=0.001,
    )
    assert saved_file.is_file()

    # Now cache hits
    assert cache.has(diff_hash, prompt, model) is True
    entry = cache.get(diff_hash, prompt, model)
    assert entry is not None
    assert entry["content"] == "Cached text explanation"
    assert entry["structured"]["title"] == "Test"
    assert entry["usage"]["total_tokens"] == 75

    # Clear cache
    cleared = cache.clear()
    assert cleared == 1
    assert cache.has(diff_hash, prompt, model) is False


def test_cached_llm_provider_hit_avoids_duplicate_call(tmp_path: Path) -> None:
    """Verify CachedLLMProvider returns cached result with 0 cost and no provider calls."""
    fake = FakeProvider(model="claude-3-7-sonnet-latest")
    fake.enqueue_text("First generated answer")
    cache = DiskCache(cache_dir=tmp_path / "cache")

    cached_p = CachedLLMProvider(
        provider=fake,
        cache=cache,
        diff_hash="hash_abc",
    )

    # Call 1: Cache Miss
    res1 = cached_p.generate_text("Prompt 1")
    assert res1.content == "First generated answer"
    assert res1.cached is False
    assert len(fake.recorded_calls) == 1

    # Call 2: Identical prompt and diff_hash -> Cache Hit!
    res2 = cached_p.generate_text("Prompt 1")
    assert res2.content == "First generated answer"
    assert res2.cached is True
    assert res2.cost_usd == 0.0
    # Crucial: Provider was NOT called a second time!
    assert len(fake.recorded_calls) == 1


def test_cached_llm_provider_structured_caching(tmp_path: Path) -> None:
    """Verify CachedLLMProvider stores and deserializes structured responses."""
    fake = FakeProvider()
    fake.enqueue_structured({"title": "Cached Struct", "points": 42})
    cache = DiskCache(cache_dir=tmp_path / "cache")

    cached_p = CachedLLMProvider(
        provider=fake,
        cache=cache,
        diff_hash="hash_xyz",
    )

    # Call 1: Miss and generate
    res1 = cached_p.generate_structured("Prompt struct", schema=SampleSchema)
    assert res1.structured is not None
    assert res1.structured.title == "Cached Struct"
    assert res1.structured.points == 42
    assert res1.cached is False

    # Call 2: Hit cache
    res2 = cached_p.generate_structured("Prompt struct", schema=SampleSchema)
    assert res2.structured is not None
    assert res2.structured.title == "Cached Struct"
    assert res2.structured.points == 42
    assert res2.cached is True
    assert len(fake.recorded_calls) == 1
