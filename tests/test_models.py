# -*- coding: utf-8 -*-
# vim: set ts=4
#
# Copyright 2019 Linaro Limited
#
# Author: Rémi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: MIT

import pytest
import time

from kiss_cache.models import Resource


def test_resource_parse_ttl():
    assert Resource.parse_ttl("1d") == 60 * 60 * 24
    assert Resource.parse_ttl("18d") == 60 * 60 * 24 * 18
    assert Resource.parse_ttl("5h") == 60 * 60 * 5
    assert Resource.parse_ttl("34m") == 60 * 34
    assert Resource.parse_ttl("500s") == 500
    assert Resource.parse_ttl("42s") == 42

    with pytest.raises(NotImplementedError, match="Unknow TTL value"):
        Resource.parse_ttl("42t")
    with pytest.raises(Exception, match="The TTL should be positive"):
        Resource.parse_ttl("-1s")


def test_resource_compute_path():
    assert (
        Resource.compute_path("https://example.com/kernel")
        == "76/66828e5a43fe3e8c06c2e62ad216cc354c91da92f093d6d8a7c3dc9d1baa82"
    )


def test_resource_total_size(db):
    assert Resource.total_size() == 0

    Resource.objects.create(url="http://example.com", content_length=4212)
    Resource.objects.create(url="http://example.org", content_length=5379)
    Resource.objects.create(url="http://example.net", content_length=2)
    assert Resource.total_size() == 4212 + 5379 + 2


def test_resource_total_size(db, settings):
    settings.RESOURCE_QUOTA = 12
    assert Resource.is_over_quota() is False

    Resource.objects.create(url="http://example.com", content_length=4212)
    Resource.objects.create(url="http://example.org", content_length=5379)
    Resource.objects.create(url="http://example.net", content_length=2)
    assert Resource.is_over_quota() is True

    settings.RESOURCE_QUOTA = 4212 + 5379 + 2 - 1
    assert Resource.is_over_quota() is True

    settings.RESOURCE_QUOTA = 4212 + 5379 + 2 + 1
    assert Resource.is_over_quota() is False

    settings.RESOURCE_QUOTA = 0
    assert Resource.is_over_quota() is False


def test_resource_progress(db, settings, tmpdir):
    settings.DOWNLOAD_PATH = str(tmpdir)
    res = Resource.objects.create(url="https://example.com/kernel")
    res.path = Resource.compute_path(res.url)
    assert res.progress() == "??"
    res.content_length = 56
    assert res.progress() == 0

    (tmpdir / "76").mkdir()
    (
        tmpdir / "76/66828e5a43fe3e8c06c2e62ad216cc354c91da92f093d6d8a7c3dc9d1baa82"
    ).write_text("hello", encoding="utf-8")
    assert res.progress() == 8


def test_resource_stream(db, monkeypatch, settings, tmpdir):
    monkeypatch.setattr(time, "sleep", lambda d: d)

    settings.DOWNLOAD_PATH = str(tmpdir)
    res = Resource.objects.create(url="https://example.com/kernel")
    res.path = Resource.compute_path(res.url)
    res.save()
    (tmpdir / "76").mkdir()
    with (
        tmpdir / "76/66828e5a43fe3e8c06c2e62ad216cc354c91da92f093d6d8a7c3dc9d1baa82"
    ).open("wb") as f_out:
        f_out.write(b"hello")
        f_out.flush()
        it = res.stream()
        assert next(it) == b"hello"
        f_out.write(b" world")
        f_out.flush()
        assert next(it) == b" world"

        res.status_code = 200
        res.state = Resource.STATE_FINISHED
        res.save()
        f_out.write(b"!")
        f_out.flush()
        assert next(it) == b"!"
    with pytest.raises(StopIteration):
        next(it)


def test_resource_stream_errors(db, monkeypatch, settings, tmpdir):
    monkeypatch.setattr(time, "sleep", lambda d: d)

    settings.DOWNLOAD_PATH = str(tmpdir)
    res = Resource.objects.create(url="https://example.com/kernel")
    res.path = Resource.compute_path(res.url)
    res.save()
    (tmpdir / "76").mkdir()
    with (
        tmpdir / "76/66828e5a43fe3e8c06c2e62ad216cc354c91da92f093d6d8a7c3dc9d1baa82"
    ).open("wb") as f_out:
        f_out.write(b"hello")
        f_out.flush()
        it = res.stream()
        assert next(it) == b"hello"
        f_out.write(b" world")
        f_out.flush()
        assert next(it) == b" world"

        res.status_code = 403
        res.state = Resource.STATE_FINISHED
        res.save()
    with pytest.raises(Exception, match="status-code is not 200: 403"):
        next(it)


def test_resource_stream_errors_2(db, monkeypatch, settings, tmpdir):
    monkeypatch.setattr(time, "sleep", lambda d: d)

    settings.DOWNLOAD_PATH = str(tmpdir)
    res = Resource.objects.create(url="https://example.com/kernel")
    res.path = Resource.compute_path(res.url)
    res.save()
    (tmpdir / "76").mkdir()
    with (
        tmpdir / "76/66828e5a43fe3e8c06c2e62ad216cc354c91da92f093d6d8a7c3dc9d1baa82"
    ).open("wb") as f_out:
        f_out.write(b"hello")
        f_out.flush()
        it = res.stream()
        assert next(it) == b"hello"
        f_out.write(b" world")
        f_out.flush()
        assert next(it) == b" world"

        res.delete()
    with pytest.raises(Exception, match="status-code is not 200: 404"):
        next(it)
